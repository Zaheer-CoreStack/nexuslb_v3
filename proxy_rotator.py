#!/usr/bin/env python3
"""
Free Proxy Rotator for NexusLB
- Fetches free proxies from public lists
- Tests them against upstream
- Automatically rotates unhealthy proxies
"""
import requests
import sqlite3
import re
import time
import subprocess
import os
from datetime import datetime

DB_PATH = "/instance/panel.db"
DOCKER_COMPOSE_PATH = "/workspaces/nexuslb_v3/docker-compose.yml"
UPSTREAM_URL = "http://cf.business-cdn-8k.su/get.php?username=Rizwan100&password=Rizwan100&type=m3u_plus&output=ts"
TEST_TIMEOUT = 5  # seconds

def fetch_free_proxies():
    """Fetch free proxies from public sources"""
    proxies = []
    
    # Source 1: free-proxy-list.net
    try:
        resp = requests.get("https://free-proxy-list.net/", timeout=10)
        if resp.status_code == 200:
            # Parse IP:Port pattern
            matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', resp.text)
            for ip, port in matches[:20]:
                proxies.append({"ip": ip, "port": int(port), "protocol": "socks5", "source": "free-proxy-list.net"})
    except Exception as e:
        print(f"[!] Error fetching from free-proxy-list.net: {e}")
    
    # Source 2: spys.me
    try:
        resp = requests.get("https://spys.me/proxy.txt", timeout=10)
        if resp.status_code == 200:
            matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', resp.text)
            for ip, port in matches[:20]:
                if int(port) in [1080, 1085, 3128, 8080]:
                    proxies.append({"ip": ip, "port": int(port), "protocol": "socks5", "source": "spys.me"})
    except Exception as e:
        print(f"[!] Error fetching from spys.me: {e}")
    
    # Source 3: github.com/schemasd/geoip (alternative)
    try:
        resp = requests.get("https://raw.githubusercontent.com/schemasd/geoip/main/free-proxy-list.txt", timeout=10)
        if resp.status_code == 200:
            matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', resp.text)
            for ip, port in matches[:10]:
                proxies.append({"ip": ip, "port": int(port), "protocol": "socks5", "source": "github"})
    except Exception as e:
        print(f"[!] Error fetching from github: {e}")
    
    print(f"[+] Fetched {len(proxies)} free proxies")
    return proxies

def test_proxy(proxy):
    """Test if proxy can reach the upstream"""
    try:
        proxy_url = f"socks5://{proxy['ip']}:{proxy['port']}"
        resp = requests.get(UPSTREAM_URL, proxies={"http": proxy_url, "https": proxy_url}, 
                          timeout=TEST_TIMEOUT)
        
        if resp.status_code == 200 and resp.text and '#EXTINF' in resp.text:
            channel_count = resp.text.count('#EXTINF')
            print(f"    ✓ {proxy['ip']}:{proxy['port']} - {channel_count} channels")
            return True, channel_count
        else:
            print(f"    ✗ {proxy['ip']}:{proxy['port']} - Status {resp.status_code}")
    except requests.Timeout:
        print(f"    ✗ {proxy['ip']}:{proxy['port']} - Timeout")
    except Exception as e:
        print(f"    ✗ {proxy['ip']}:{proxy['port']} - {str(e)[:30]}")
    return False, 0

def find_working_proxy():
    """Find a working proxy from free sources"""
    print("\n[*] Fetching free proxies...")
    proxies = fetch_free_proxies()
    
    if not proxies:
        print("[!] No free proxies found!")
        return None
    
    print(f"[*] Testing {len(proxies)} proxies against upstream...")
    
    for i, proxy in enumerate(proxies):
        print(f"  [{i+1}/{len(proxies)}] Testing {proxy['source']}...", end=" ")
        success, channels = test_proxy(proxy)
        if success:
            print(f"\n[✓] Found working proxy: {proxy['ip']}:{proxy['port']}")
            return proxy
    
    print("\n[!] No working proxies found!")
    return None

def update_docker_compose(proxy):
    """Update docker-compose.yml with new proxy"""
    if not proxy:
        print("[!] No proxy to update")
        return False
    
    proxy_url = f"socks5://{proxy['ip']}:{proxy['port']}"
    
    try:
        with open(DOCKER_COMPOSE_PATH, 'r') as f:
            content = f.read()
        
        # Replace the TRANSPORT_ROUTES line
        new_routes = f'TRANSPORT_ROUTES: \'{{"all://*": {{"proxy_url": "{proxy_url}", "verify_ssl": false, "proxy": true}}}}\''
        
        # Find and replace (simplified pattern matching)
        if 'TRANSPORT_ROUTES' in content:
            # Simple replacement - replace entire line
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if 'TRANSPORT_ROUTES' in line:
                    new_lines.append(new_routes)
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
        else:
            # Add after FORWARDED_ALLOW_IPS
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if 'FORWARDED_ALLOW_IPS' in line:
                    new_lines.append(f'      {new_routes}')
            content = '\n'.join(new_lines)
        
        with open(DOCKER_COMPOSE_PATH, 'w') as f:
            f.write(content)
        
        print(f"[✓] Updated docker-compose.yml with proxy {proxy_url}")
        return True
    except Exception as e:
        print(f"[!] Error updating docker-compose.yml: {e}")
        return False

def restart_containers():
    """Restart docker containers"""
    try:
        print("[*] Restarting containers...")
        result = subprocess.run(
            ["docker-compose", "down"],
            cwd=os.path.dirname(DOCKER_COMPOSE_PATH) or ".",
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"[!] Error stopping containers: {result.stderr}")
            return False
        
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=os.path.dirname(DOCKER_COMPOSE_PATH) or ".",
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"[!] Error starting containers: {result.stderr}")
            return False
        
        print("[✓] Containers restarted successfully")
        return True
    except Exception as e:
        print(f"[!] Error restarting containers: {e}")
        return False

def main():
    print("=" * 50)
    print("  NexusLB Free Proxy Rotator")
    print("=" * 50)
    print(f"  Upstream: {UPSTREAM_URL[:60]}...")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Find working proxy
    proxy = find_working_proxy()
    
    if proxy:
        # Update docker-compose
        if update_docker_compose(proxy):
            # Restart containers
            restart_containers()
            print("\n[✓] Proxy rotation complete!")
    else:
        print("\n[!] Failed to find working proxy")
        print("[*] Tip: Free proxies are often unreliable. Consider using:")
        print("   - Paid VPN services (NordVPN, ExpressVPN)")
        print("   - Residential proxy services")
        print("   - Webshare API (already configured in sync_proxies.py)")

if __name__ == "__main__":
    main()
