from flask import Blueprint, request, Response, stream_with_context, abort
from ..models import StreamUser, Playlist, ProxyPool
from ..services.webshare import WebshareService
from .. import db
import requests
import base64
import urllib.parse
from passlib.hash import bcrypt
import logging

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

def check_auth(username, password):
    user = StreamUser.query.filter_by(username=username).first()
    if user:
        # Check password hash (htpasswd bcrypt format)
        try:
            return bcrypt.verify(password, user.password_hash)
        except Exception:
            return False
    return False

@api_bp.route('/get.php')
def get_playlist():
    username = request.args.get('username')
    password = request.args.get('password')
    
    if not username or not password or not check_auth(username, password):
        return Response("Auth Failed", status=401)
        
    # Generate M3U
    playlists = Playlist.query.filter_by(status='active').all()
    m3u_content = "#EXTM3U\n"
    
    host_url = request.host_url.rstrip('/') # e.g. https://xyz.app.github.dev
    
    for p in playlists:
        try:
            # Fetch upstream M3U
            # We use 'Best Proxy' for fetching the playlist itself too, to avoid blocks
            proxy_obj = WebshareService.get_best_proxy()
            proxies = {}
            if proxy_obj:
               proxies = {'http': proxy_obj.to_proxy_url(), 'https': proxy_obj.to_proxy_url()}
            
            resp = requests.get(p.url, proxies=proxies, timeout=10)
            if resp.status_code == 200:
                lines = resp.text.splitlines()
                for line in lines:
                    line = line.strip()
                    if line.startswith('#EXTINF'):
                        m3u_content += f"{line}\n"
                    elif line and not line.startswith('#'):
                        # Rewrite Stream URL
                        # Encode original URL
                        encoded_url = base64.urlsafe_b64encode(line.encode()).decode()
                        new_url = f"{host_url}/stream/{encoded_url}"
                        m3u_content += f"{new_url}\n"
        except Exception as e:
            logger.error(f"Error fetching playlist {p.name}: {e}")
            
    return Response(m3u_content, mimetype='audio/x-mpegurl')

@api_bp.route('/stream/<encoded_url>')
def proxy_stream(encoded_url):
    try:
        # Decode URL
        original_url = base64.urlsafe_b64decode(encoded_url).decode()
        
        # Get Proxy
        proxy_obj = WebshareService.get_best_proxy()
        proxies = {}
        if proxy_obj:
            proxies = {'http': proxy_obj.to_proxy_url(), 'https': proxy_obj.to_proxy_url()}
            
        # Stream Content
        req = requests.get(original_url, stream=True, proxies=proxies, timeout=10)
        
        return Response(stream_with_context(req.iter_content(chunk_size=1024)), 
                        content_type=req.headers.get('content-type'))
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return abort(500)
