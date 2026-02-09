#!/bin/bash
#
# Split Routing Script for Proton VPN
# Routes only upstream provider traffic through VPN
# All other traffic goes directly
#

VPN_INTERFACE="tun0"
UPSTREAM_SERVERS=(
    "upstream-provider-1.com"
    "upstream-provider-2.com"
    "203.0.113.0/24"  # Example upstream IP range
    "198.51.100.0/24"  # Example upstream IP range
)

setup_split_routing() {
    echo "Setting up split routing for VPN..."
    
    # Wait for VPN to be ready
    sleep 5
    
    # Get VPN gateway
    VPN_GATEWAY=$(ip route show dev $VPN_INTERFACE 2>/dev/null | grep default | awk '{print $3}')
    
    if [ -z "$VPN_GATEWAY" ]; then
        echo "VPN not ready. Please connect VPN first."
        exit 1
    fi
    
    echo "VPN Gateway: $VPN_GATEWAY"
    
    # Remove any existing default route through VPN
    ip route del default via $VPN_GATEWAY dev $VPN_INTERFACE 2>/dev/null || true
    
    # Add routes for each upstream server
    for server in "${UPSTREAM_SERVERS[@]}"; do
        # Check if it's a domain or IP
        if [[ $server =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+ ]]; then
            # It's an IP range
            echo "Adding route for $server"
            ip route add $server via $VPN_GATEWAY dev $VPN_INTERFACE
        else
            # It's a domain - resolve to IPs
            echo "Resolving $server..."
            IPS=$(host $server 2>/dev/null | grep "has address" | awk '{print $4}')
            for ip in $IPS; do
                echo "Adding route for $ip"
                ip route add $ip via $VPN_GATEWAY dev $VPN_INTERFACE
            done
        fi
    done
    
    echo "Split routing setup complete!"
    echo ""
    echo "Routes added:"
    ip route show | grep $VPN_INTERFACE
}

remove_split_routing() {
    echo "Removing split routing..."
    for server in "${UPSTREAM_SERVERS[@]}"; do
        if [[ $server =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+ ]]; then
            ip route del $server 2>/dev/null || true
        else
            IPS=$(host $server 2>/dev/null | grep "has address" | awk '{print $4}')
            for ip in $IPS; do
                ip route del $ip 2>/dev/null || true
            done
        fi
    done
}

# Create systemd service for split routing
create_systemd_service() {
    cat > /etc/systemd/system/vpn-split-routing.service << 'EOF'
[Unit]
Description=Split Routing for Proton VPN
After=network.target openvpn@protonvpn.service
Requires=openvpn@protonvpn.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/vpn-split-routing.sh start
RemainAfterExit=yes
ExecStop=/usr/local/bin/vpn-split-routing.sh stop
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable vpn-split-routing.service
    echo "Systemd service created and enabled"
}

case "$1" in
    start)
        setup_split_routing
        ;;
    stop)
        remove_split_routing
        ;;
    restart)
        remove_split_routing
        sleep 2
        setup_split_routing
        ;;
    create-service)
        create_systemd_service
        ;;
    *)
        echo "Usage: vpn-split-routing.sh [start|stop|restart|create-service]"
        exit 1
        ;;
esac
