import requests
import logging
from .. import db
from ..models import Settings, ProxyPool
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class WebshareService:
    BASE_URL = "https://proxy.webshare.io/api/v2"

    @staticmethod
    def get_api_keys():
        """Retrieve all stored API keys from Settings."""
        keys_json = Settings.query.filter_by(key='webshare_api_keys').first()
        if keys_json and keys_json.value:
            return json.loads(keys_json.value)
        return []

    @staticmethod
    def add_api_key(api_key):
        """Add a new API key to the list."""
        keys = WebshareService.get_api_keys()
        if api_key not in keys:
            keys.append(api_key)
            
            setting = Settings.query.filter_by(key='webshare_api_keys').first()
            if not setting:
                setting = Settings(key='webshare_api_keys')
                db.session.add(setting)
            
            setting.value = json.dumps(keys)
            db.session.commit()
            return True
        return False

    @staticmethod
    def remove_api_key(api_key):
        """Remove an API key."""
        keys = WebshareService.get_api_keys()
        if api_key in keys:
            keys.remove(api_key)
            setting = Settings.query.filter_by(key='webshare_api_keys').first()
            setting.value = json.dumps(keys)
            db.session.commit()
            return True
        return False

    @staticmethod
    def fetch_proxies_from_key(api_key):
        """Fetch proxy list from Webshare for a specific key."""
        try:
            response = requests.get(
                f"{WebshareService.BASE_URL}/proxy/list/",
                headers={"Authorization": f"Token {api_key}"},
                params={"mode": "direct", "page": 1, "page_size": 100}
            )
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching proxies for key {api_key[:5]}...: {str(e)}")
            return []

    @staticmethod
    def sync_proxies():
        """Sync proxies from all keys to ProxyPool."""
        keys = WebshareService.get_api_keys()
        total_synced = 0
        
        # Clear existing pool to respect daily rotations/replacements
        db.session.query(ProxyPool).delete()
        
        for key in keys:
            proxies = WebshareService.fetch_proxies_from_key(key)
            for p in proxies:
                if p.get('valid'):
                    new_proxy = ProxyPool(
                        ip=p.get('proxy_address'),
                        port=p.get('port'),
                        username=p.get('username'),
                        password=p.get('password'),
                        country_code=p.get('country_code'),
                        protocol='socks5',
                        status='active'
                    )
                    db.session.add(new_proxy)
                    total_synced += 1
        
        db.session.commit()
        logger.info(f"Synced {total_synced} proxies from Webshare.")
        return total_synced

    @staticmethod
    def get_best_proxy(country_code=None):
        """
        Get the best available proxy from the pool.
        Priority: 
        1. Requested Country (if active)
        2. UK (GB)
        3. EU (List of EU codes)
        4. Any Active
        """
        query = ProxyPool.query.filter_by(status='active')
        
        if country_code:
            proxy = query.filter_by(country_code=country_code).first()
            if proxy: return proxy

        # Default Preference: GB -> EU -> Any
        gb_proxy = query.filter_by(country_code='GB').first()
        if gb_proxy: return gb_proxy
        
        eu_codes = ['FR', 'DE', 'NL', 'IT', 'ES', 'SE', 'CH']
        eu_proxy = query.filter(ProxyPool.country_code.in_(eu_codes)).first()
        if eu_proxy: return eu_proxy
        
        return query.first()
