# Proton VPN Setup for NexusLB v3

This directory contains scripts to set up Proton VPN for bypassing upstream provider blocks.

## Overview

Your Azure VM IP is being blocked because datacenter IPs are blacklisted. This setup routes your upstream traffic through Proton VPN's residential IPs.

## Files

| File | Purpose |
|------|---------|
| `vpn-setup.sh` | Main installation script for Proton VPN |
| `vpn-split-routing.sh` | Routes only upstream traffic through VPN |
| `azure-nsg-setup.sh` | Configures Azure Network Security Group |
| `test-vpn-setup.sh` | Tests the entire setup |

## Quick Start

### 1. Azure Configuration (Run locally with Azure CLI)

```bash
# Update the RESOURCE_GROUP and NSG_NAME in azure-nsg-setup.sh
chmod +x azure-nsg-setup.sh
./azure-nsg-setup.sh
```

### 2. VM Setup (Run on Azure VM)

```bash
# SSH into your VM
ssh user@your-azure-vm-ip

# Clone or copy these scripts to the VM
# Then run the setup
chmod +x vpn-setup.sh
sudo ./vpn-setup.sh
```

### 3. Start VPN

```bash
# Connect to Netherlands (recommended for Europe)
sudo vpnctl start nl

# Or US
sudo vpnctl start us

# Or Japan
sudo vpnctl start jp
```

### 4. Verify

```bash
# Check VPN status
sudo vpnctl status

# Run tests
chmod +x test-vpn-setup.sh
./test-vpn-setup.sh
```

## Commands Reference

### VPN Management

```bash
# Start VPN
sudo vpnctl start nl|us|jp

# Stop VPN
sudo vpnctl stop

# Check status
sudo vpnctl status

# Restart VPN
sudo vpnctl restart nl
```

### Split Routing

```bash
# Setup split routing for upstream only
sudo vpn-split-routing.sh start

# Create systemd service for auto-start
sudo vpn-split-routing.sh create-service

# Stop split routing
sudo vpn-split-routing.sh stop
```

### Docker Services

```bash
# Start services (VPN should be running first)
docker-compose up -d

# Check logs
docker-compose logs -f

# Restart services
docker-compose restart
```

## Architecture

```
Incoming Traffic (Users)
        ↓
    Nginx (Port 80)
        ↓
    Panel + MediaFlow
        ↓
    VPN Tunnel (Outbound)
        ↓
Proton VPN Residential IP
        ↓
    Upstream Provider ← ALLOWED
```

## Important Notes

### Azure NSG
Make sure UDP port 1194 is allowed in your Azure Network Security Group.

### Free Tier Limitations
- 3 countries only (NL, US, JP)
- Medium speed
- One connection at a time

### Performance
The VPN will add some latency. Test if the speed meets your needs.

### Split Routing
By default, all traffic routes through VPN. Use split routing to route only upstream provider traffic.

## Troubleshooting

### VPN won't connect
```bash
# Check Azure NSG
az network nsg rule list -g NexusLB-RG --nsg-name NexusLB-NSG -o table

# Check firewall
sudo iptables -L
```

### Services not accessible
```bash
# Check Docker
docker-compose ps

# Check logs
docker-compose logs -f panel
```

### Upstream still blocked
```bash
# Verify IP change
curl ifconfig.co

# Check VPN status
sudo vpnctl status

# Test upstream directly
curl -v https://upstream-provider.com
```

## Security

- Credentials stored in `/etc/openvpn/protonvpn/auth.txt`
- File permissions: 600 (root only)
- Firewall rules prevent traffic leaks if VPN disconnects
