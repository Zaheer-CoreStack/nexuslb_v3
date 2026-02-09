#!/bin/bash
#
# Test script to verify VPN and services are working correctly
#

echo "======================================"
echo "NexusLB v3 VPN Test Script"
echo "======================================"

PASS=0
FAIL=0

test_vpn_connection() {
    echo ""
    echo "[Test 1] VPN Connection"
    echo "----------------------"
    
    # Check if running in Codespaces/local environment
    # Check if running in Codespaces/local environment
    # if [ -f "/.dockerenv" ] || grep -q "codespaces" /proc/1/cgroup 2>/dev/null; then
    #     echo "⚠ Running in container/Codespaces - VPN not applicable"
    #     echo "  VPN will be configured when deployed to Azure VM"
    #     ((PASS++))
    #     return
    # fi
    
    if pgrep -f "openvpn.*protonvpn" > /dev/null; then
        echo "✓ VPN process is running"
        ((PASS++))
        
        # Check public IP
        PUBLIC_IP=$(curl -s --connect-timeout 5 ifconfig.co 2>/dev/null)
        if [ -n "$PUBLIC_IP" ]; then
            echo "✓ Public IP: $PUBLIC_IP"
            
            # Check if it looks like a residential IP (not Azure)
            if [[ $PUBLIC_IP =~ ^(23|40|52|104|137|138|157|168|168|172|191) ]]; then
                echo "⚠ Warning: IP range may indicate datacenter"
            else
                echo "✓ IP appears to be residential"
            fi
            ((PASS++))
        else
            echo "✗ Could not determine public IP"
            ((FAIL++))
        fi
    else
        echo "✗ VPN is NOT running"
        echo "  Start with: sudo vpnctl start nl"
        ((FAIL++))
    fi
}

test_docker_services() {
    echo ""
    echo "[Test 2] Docker Services"
    echo "----------------------"
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "✗ Docker is not running"
        ((FAIL++))
        return
    fi
    
    # Check each service
    for service in mfp lb panel; do
        if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
            STATUS=$(docker inspect --format='{{.State.Status}}' $service 2>/dev/null)
            if [ "$STATUS" = "running" ]; then
                echo "✓ $service is running"
                ((PASS++))
            else
                echo "✗ $service is $STATUS (not running)"
                ((FAIL++))
            fi
        else
            echo "✗ $service is not running"
            ((FAIL++))
        fi
    done
}

test_nginx_proxy() {
    echo ""
    echo "[Test 3] Nginx Load Balancer"
    echo "----------------------"
    
    # Test health endpoint (no auth)
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health | grep -q "200"; then
        echo "✓ Nginx health check passing"
        ((PASS++))
    else
        echo "✗ Nginx health check failing"
        ((FAIL++))
    fi
    
    # Test with auth
    if curl -s -o /dev/null -w "%{http_code}" -u admin:admin123 http://localhost/ | grep -q "200"; then
        echo "✓ Nginx with authentication working"
        ((PASS++))
    else
        echo "✗ Nginx with authentication failing"
        ((FAIL++))
    fi
}

test_panel_api() {
    echo ""
    echo "[Test 4] Panel API"
    echo "----------------------"
    
    # Test get.php endpoint
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/get.php 2>/dev/null)
    if [ "$RESPONSE" = "200" ] || [ "$RESPONSE" = "401" ]; then
        echo "✓ Panel API responding (HTTP $RESPONSE)"
        ((PASS++))
    else
        echo "✗ Panel API not responding (HTTP $RESPONSE)"
        ((FAIL++))
    fi
}

test_xc_endpoints() {
    echo ""
    echo "[Test 6] XC/Xtream Proxy Endpoints"
    echo "----------------------"
    
    # Test player_api.php
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/player_api.php 2>/dev/null)
    if [ "$RESPONSE" = "401" ] || [ "$RESPONSE" = "422" ]; then
        echo "✓ XC player_api.php responding (HTTP $RESPONSE - needs auth)"
        ((PASS++))
    else
        echo "✗ XC player_api.php error (HTTP $RESPONSE)"
        ((FAIL++))
    fi
    
    # Test get.php
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/get.php 2>/dev/null)
    if [ "$RESPONSE" = "401" ] || [ "$RESPONSE" = "422" ]; then
        echo "✓ XC get.php responding (HTTP $RESPONSE - needs auth)"
        ((PASS++))
    else
        echo "✗ XC get.php error (HTTP $RESPONSE)"
        ((FAIL++))
    fi
    
    # Test panel_api.php
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/panel_api.php 2>/dev/null)
    if [ "$RESPONSE" = "401" ] || [ "$RESPONSE" = "422" ]; then
        echo "✓ XC panel_api.php responding (HTTP $RESPONSE - needs auth)"
        ((PASS++))
    else
        echo "✗ XC panel_api.php error (HTTP $RESPONSE)"
        ((FAIL++))
    fi
}

test_upstream_connection() {
    echo ""
    echo "[Test 5] Upstream Connection"
    echo "----------------------"
    
    # Test connection to your upstream provider
    # Replace with your actual upstream URL
    UPSTREAM_TEST_URL="https://example.com"  # UPDATE THIS
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$UPSTREAM_TEST_URL" 2>/dev/null)
    if [ "$HTTP_CODE" != "000" ]; then
        echo "✓ Upstream connection successful (HTTP $HTTP_CODE)"
        ((PASS++))
    else
        echo "⚠ Upstream connection failed (timeout or refused)"
        echo "  This may be expected if VPN is not fully connected"
        ((FAIL++))
    fi
}

# Run all tests
test_vpn_connection
test_docker_services
test_nginx_proxy
test_panel_api
test_xc_endpoints
test_upstream_connection

# Summary
echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed. Please review the output above."
    exit 1
fi
