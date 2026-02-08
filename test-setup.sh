#!/bin/bash

# NexusLB v3 - Verification & Testing Script
# This script tests the Load Balancer and MediaFlow Proxy setup

set -e

echo "╔════════════════════════════════════════════════════╗"
echo "║  NexusLB v3 - Service Verification & Test Suite  ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

# Helper function to run tests
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_text="$3"
    
    echo -ne "${BLUE}Testing:${NC} $test_name... "
    
    if output=$(eval "$command" 2>&1); then
        if [[ -z "$expected_text" ]] || echo "$output" | grep -q "$expected_text"; then
            echo -e "${GREEN}✓ PASSED${NC}"
            ((PASSED++))
        else
            echo -e "${RED}✗ FAILED${NC}"
            echo "  Output: $output"
            ((FAILED++))
        fi
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Error: $output"
        ((FAILED++))
    fi
}

echo "═══════════════════════════════════════════════════════"
echo "STEP 1: Docker Services Status"
echo "═══════════════════════════════════════════════════════"
echo ""

echo -e "${BLUE}Running Services:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "No containers running"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "STEP 2: Service Connectivity Tests"
echo "═══════════════════════════════════════════════════════"
echo ""

# Test Nginx Health Check (No Auth Required)
run_test "Nginx Health Endpoint (No Auth)" \
    "curl -s -I http://localhost:8080/health 2>/dev/null || echo 'Service not ready'" \
    "200"

# Test Nginx Without Credentials (Should Return 401)
run_test "Nginx Without Credentials" \
    "curl -s -o /dev/null -w '%{http_code}' http://localhost/ 2>/dev/null || echo '999'" \
    "401"

# Test Nginx With Valid Credentials (Should Return 200)
run_test "Nginx With Valid Credentials (admin)" \
    "curl -s -o /dev/null -w '%{http_code}' -u admin:admin123 http://localhost/ 2>/dev/null || echo '999'" \
    "200"

# Test MediaFlow Proxy Direct Access (No Auth Required)
run_test "MediaFlow Proxy Direct Access" \
    "curl -s -I http://localhost:8888/ 2>/dev/null | head -1 || echo 'Service not ready'" \
    "200"

# Test Proxying Through Load Balancer
run_test "Load Balancer Proxying to MFP" \
    "curl -s -u demo:demo123 http://localhost/ 2>/dev/null | head -20 | grep -q 'MediaFlow\\|DOCTYPE' && echo 'success' || echo 'failed'" \
    "success"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "STEP 3: Configuration Validation"
echo "═══════════════════════════════════════════════════════"
echo ""

echo -e "${BLUE}Checking Files:${NC}"

# Check if docker-compose.yml exists
if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓${NC} docker-compose.yml found"
else
    echo -e "${RED}✗${NC} docker-compose.yml not found"
    ((FAILED++))
fi

# Check if nginx.conf exists
if [ -f "nginx.conf" ]; then
    echo -e "${GREEN}✓${NC} nginx.conf found"
    # Verify basic structure
    if grep -q "auth_basic" nginx.conf; then
        echo -e "${GREEN}✓${NC} nginx.conf has auth_basic configured"
    fi
else
    echo -e "${RED}✗${NC} nginx.conf not found"
    ((FAILED++))
fi

# Check if .htpasswd exists
if [ -f ".htpasswd" ]; then
    echo -e "${GREEN}✓${NC} .htpasswd found"
    user_count=$(wc -l < .htpasswd)
    echo "  Users configured: $user_count"
else
    echo -e "${RED}✗${NC} .htpasswd not found"
    ((FAILED++))
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "STEP 4: Test Results Summary"
echo "═══════════════════════════════════════════════════════"
echo ""
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Your NexusLB setup is ready!"
    echo ""
    echo "Access Points:"
    echo "  - Nginx Load Balancer: http://localhost/ (with auth)"
    echo "  - MediaFlow Proxy Direct: http://localhost:8888/"
    echo "  - Health Check: http://localhost:8080/health"
    exit 0
else
    echo -e "${RED}✗ Some tests failed.${NC}"
    echo ""
    echo "Troubleshooting tips:"
    echo "  1. Ensure docker-compose containers are running:"
    echo "     docker-compose up -d"
    echo ""
    echo "  2. Check service logs:"
    echo "     docker-compose logs -f"
    echo ""
    echo "  3. Verify credentials in .htpasswd match your test"
    echo ""
    exit 1
fi
