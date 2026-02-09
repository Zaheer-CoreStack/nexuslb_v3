#!/bin/bash
#
# Azure Network Security Group Setup for Proton VPN
# Run this on your local machine with Azure CLI installed
#

echo "======================================"
echo "Azure NSG Configuration for Proton VPN"
echo "======================================"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Please install it first:"
    echo "curl -sL https://aka.ms/InstallAzureCLIDeb | bash"
    exit 1
fi

# Configuration
RESOURCE_GROUP="NexusLB-RG"  # Update with your resource group name
NSG_NAME="NexusLB-NSG"       # Update with your NSG name
LOCATION="eastus"            # Update with your Azure region

echo "Resource Group: $RESOURCE_GROUP"
echo "NSG Name: $NSG_NAME"
echo ""

# Step 1: Add inbound rule for SSH (already exists usually)
echo "[1/4] Ensuring SSH port is open..."
az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name $NSG_NAME \
    --name AllowSSH \
    --priority 100 \
    --destination-port-ranges 22 \
    --access Allow \
    --protocol Tcp \
    --description "Allow SSH" 2>/dev/null || echo "SSH rule already exists"

# Step 2: Add inbound rule for HTTP/HTTPS
echo "[2/4] Ensuring HTTP/HTTPS ports are open..."
az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name $NSG_NAME \
    --name AllowHTTP \
    --priority 110 \
    --destination-port-ranges 80 443 \
    --access Allow \
    --protocol Tcp \
    --description "Allow HTTP/HTTPS" 2>/dev/null || echo "HTTP rule already exists"

# Step 3: Add outbound rule for VPN (UDP 1194)
echo "[3/4] Adding outbound rule for VPN (UDP 1194)..."
az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name $NSG_NAME \
    --name AllowVPN \
    --priority 100 \
    --destination-port-ranges 1194 \
    --access Allow \
    --protocol Udp \
    --direction Outbound \
    --description "Allow Proton VPN" 2>/dev/null || echo "VPN rule already exists"

# Step 4: Allow DNS for VPN DNS resolution
echo "[4/4] Adding outbound rule for DNS..."
az network nsg rule create \
    --resource-group $RESOURCE_GROUP \
    --nsg-name $NSG_NAME \
    --name AllowDNS \
    --priority 101 \
    --destination-port-ranges 53 \
    --access Allow \
    --protocol Udp \
    --direction Outbound \
    --description "Allow DNS" 2>/dev/null || echo "DNS rule already exists"

echo ""
echo "======================================"
echo "Azure NSG Configuration Complete!"
echo "======================================"
echo ""
echo "Current NSG rules:"
az network nsg show --resource-group $RESOURCE_GROUP --name $NSG_NAME --query "securityRules" -o table 2>/dev/null || echo "Could not display rules"

echo ""
echo "IMPORTANT: Make sure your VM's network interface is associated with this NSG"
echo "Check with: az network nic list --resource-group $RESOURCE_GROUP -o table"
