#!/usr/bin/env python3
import requests
import sqlite3

api_key = 'f9kedo8kvodo2cfjf16r0t7coj2tuiky0un0rc96'
BASE_URL = "https://proxy.webshare.io/api/v2"
DB_PATH = "/instance/panel.db"

print("[*] Syncing proxies from Webshare...")
try:
    response = requests.get(
        f"{BASE_URL}/proxy/list/",
        headers={"Authorization": f"Token {api_key}"},
        params={"mode": "direct", "page": 1, "page_size": 100},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        proxies = data.get('results', [])
        print(f"[+] Found {len(proxies)} proxies from Webshare")
        
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Clear old proxies
        cursor.execute('DELETE FROM proxy_pool')
        deleted = cursor.rowcount
        print(f"[+] Cleared {deleted} old proxies")
        
        # Insert new proxies
        inserted = 0
        for p in proxies:
            if p.get('valid'):
                cursor.execute('''
                    INSERT INTO proxy_pool (ip, port, username, password, country_code, protocol, status, last_checked, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ''', (
                    p.get('proxy_address'),
                    p.get('port'),
                    p.get('username'),
                    p.get('password'),
                    p.get('country_code'),
                    'socks5',
                    'active'
                ))
                inserted += 1
        
        conn.commit()
        print(f"[+] Inserted {inserted} proxies into database")
        
        # Verify
        cursor.execute('SELECT COUNT(*) FROM proxy_pool')
        total = cursor.fetchone()[0]
        print(f"[✓] Total proxies in pool: {total}")
        
        if total > 0:
            cursor.execute('SELECT ip, port, country_code FROM proxy_pool LIMIT 3')
            for row in cursor.fetchall():
                print(f"    - {row[0]}:{row[1]} ({row[2]})")
        
        conn.close()
    else:
        print(f"[!] Error {response.status_code}: {response.text[:200]}")
except Exception as e:
    print(f"[!] Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
