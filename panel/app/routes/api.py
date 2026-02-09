from flask import Blueprint, request, Response, stream_with_context, abort
from ..models import StreamUser, Playlist, ProxyPool
from ..services.webshare import WebshareService
from .. import db
import requests
import base64
import urllib.parse
from passlib.hash import bcrypt
import logging
from datetime import datetime, timedelta
import hashlib

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# Simple in-memory cache (replace with Redis for production)
_playlist_cache = {}

def check_auth(username, password):
    user = StreamUser.query.filter_by(username=username).first()
    if user:
        # Check password hash (htpasswd bcrypt format)
        try:
            return bcrypt.verify(password, user.password_hash)
        except Exception:
            return False
    return False

def get_cache_key(username):
    """Generate cache key for playlist"""
    return f"playlist_{hashlib.md5(username.encode()).hexdigest()}"

def get_cached_playlist(username, max_age_seconds=3600):
    """Get cached playlist if available and fresh"""
    cache_key = get_cache_key(username)
    if cache_key in _playlist_cache:
        cached_data = _playlist_cache[cache_key]
        age = (datetime.utcnow() - cached_data['timestamp']).total_seconds()
        if age < max_age_seconds:
            logger.info(f"✓ Cache hit for {username} (age: {age:.0f}s)")
            return cached_data['content']
    return None

def cache_playlist(username, content):
    """Cache playlist content"""
    cache_key = get_cache_key(username)
    _playlist_cache[cache_key] = {
        'content': content,
        'timestamp': datetime.utcnow()
    }
    logger.info(f"✓ Cached playlist for {username}")

def fetch_from_upstream(upstream_url, headers=None, timeout=8):
    """
    Fetch playlist from upstream with comprehensive headers (direct only, no proxy).
    
    Args:
        upstream_url: URL to fetch from
        headers: Optional headers dict
        timeout: Request timeout in seconds (short to avoid blocking)
    
    Returns:
        M3U content string or None
    """
    if headers is None:
        # Extract host from URL
        from urllib.parse import urlparse
        parsed = urlparse(upstream_url)
        host = parsed.netloc
        
        headers = {
            # Essential headers
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/vnd.apple.mpegurl, application/x-mpegurl, audio/x-mpegurl, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': host,
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            
            # Additional headers that avoid blocking
            'Referer': upstream_url,
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'X-Requested-With': 'XMLHttpRequest',
            
            # IPTV/Streaming specific
            'X-Client-ID': 'NexusLB/1.0',
            'X-Device-Model': 'GenericIPTVPlayer',
            'X-Device-Vendor': 'NexusLB',
        }
    
    proxies = {}
    proxy_msg = ""
    
    # Strategy 1: Try direct first (fastest)
    try:
        logger.info(f"  → Direct fetch with {len(headers)} headers...")
        resp = requests.get(upstream_url, headers=headers, proxies={}, timeout=timeout)
        
        if 200 <= resp.status_code < 300:
            logger.info(f"  ✓ Returned {resp.status_code} - GOT DATA!")
            return resp.text
        else:
            logger.warning(f"  ⚠ Returned {resp.status_code}")
    except requests.Timeout:
        logger.warning(f"  ⚠ Direct timeout ({timeout}s)")
    except Exception as e:
        logger.warning(f"  ⚠ Direct error: {str(e)[:40]}")
    
    # Direct-only; proxies/VPN disabled
    return None

def combine_playlists(playlist_dict):
    """
    Combine multiple M3U playlists into one.

    Args:
        playlist_dict: {"source_name": "m3u_content", ...}

    Returns:
        Combined M3U string
    """
    combined = "#EXTM3U\n"
    seen_urls = set()

    for source_name, content in playlist_dict.items():
        if not content:
            continue

        logger.info(f"Processing {source_name}...")
        lines = content.splitlines()

        for line in lines:
            line = line.strip()
            if not line or line == "#EXTM3U":
                continue

            # Check for duplicates (only dedupe URLs)
            if line and not line.startswith('#'):
                if line in seen_urls:
                    logger.debug(f"Skipping duplicate URL from {source_name}")
                    continue
                seen_urls.add(line)

            combined += f"{line}\n"

    extinf_count = combined.count("#EXTINF")
    logger.info(f"✓ Combined playlist has {extinf_count} channels from {len(playlist_dict)} sources")
    return combined


@api_bp.route('/get.php')
def get_playlist():
    """
    OPTION B: Full Combining with Smart Proxy Selection

    1. Authenticates user
    2. Fetches M3U content from ALL upstreams (with comprehensive headers)
    3. Combines all streams into single M3U
    4. Caches for 1 hour
    5. Returns combined M3U to TV app
    """
    username = request.args.get('username')
    password = request.args.get('password')

    # Step 1: Authenticate
    if not username or not password or not check_auth(username, password):
        return Response("Auth Failed", status=401)

    logger.info(f"✓ AUTH: {username} authenticated")

    # Step 2: Check cache
    cached = get_cached_playlist(username, max_age_seconds=3600)
    if cached:
        channels = cached.count('#EXTINF')
        logger.info(f"✓ CACHE HIT: {channels} channels from cache")
        return Response(cached, mimetype='audio/x-mpegurl')

    # Step 3: Get all active upstreams
    playlists = Playlist.query.filter_by(status='active').all()

    if not playlists:
        logger.warning(f"⚠ No active upstreams configured")
        return Response("#EXTM3U\n", mimetype='audio/x-mpegurl')

    logger.info(f"→ FETCH: {len(playlists)} upstream(s) to fetch")

    # Step 4: Fetch from each upstream (direct only)
    upstream_contents = {}

    for playlist in playlists:
        logger.info(f"\n→ {playlist.name}")

        # Direct fetch only (VPN/proxy disabled)
        content = fetch_from_upstream(playlist.url)

        if content:
            upstream_contents[playlist.name] = content
            channels = content.count('#EXTINF')
            logger.info(f"  ✓ Got {channels} channels")
        else:
            logger.error(f"  ✗ Fetch failed")

    # Step 5: Combine all playlists
    if not upstream_contents:
        logger.warning(f"⚠ No content retrieved (upstreams offline?)")
        return Response("#EXTM3U\n", mimetype='audio/x-mpegurl')

    logger.info(f"\n→ COMBINE: {len(upstream_contents)} source(s)")
    combined_m3u = combine_playlists(upstream_contents)

    # Step 6: Cache the combined result
    cache_playlist(username, combined_m3u)

    # Step 7: Return to TV app
    total_channels = combined_m3u.count('#EXTINF')
    logger.info(f"✓ RETURN: {total_channels} total channels\n")

    return Response(combined_m3u, mimetype='audio/x-mpegurl')


@api_bp.route('/stream/<encoded_url>')
def proxy_stream(encoded_url):
    try:
        # Decode URL
        original_url = base64.urlsafe_b64decode(encoded_url).decode()

        # Stream Content (direct access, no proxy)
        req = requests.get(original_url, stream=True, timeout=10)

        return Response(stream_with_context(req.iter_content(chunk_size=1024)),
                        content_type=req.headers.get('content-type'))
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return abort(500)


def parse_m3u_playlist(content):
    """
    Parse M3U playlist and return structured data.
    
    Returns:
        dict with 'categories', 'channels', 'total' count
    """
    categories = {}
    channels = []
    
    lines = content.splitlines()
    current_channel = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('#EXTINF:'):
            # Parse channel info
            current_channel = {'raw': line}
            
            # Extract tvg-id
            tvg_id = ''
            if 'tvg-id="' in line:
                start = line.find('tvg-id="') + 8
                end = line.find('"', start)
                tvg_id = line[start:end] if end > start else ''
            
            # Extract tvg-logo
            tvg_logo = ''
            if 'tvg-logo="' in line:
                start = line.find('tvg-logo="') + 10
                end = line.find('"', start)
                tvg_logo = line[start:end] if end > start else ''
            
            # Extract group-title (category)
            category = 'Uncategorized'
            if 'group-title="' in line:
                start = line.find('group-title="') + 13
                end = line.find('"', start)
                category = line[start:end] if end > start else 'Uncategorized'
            
            # Extract channel name (after last comma)
            name = line.split(',')[-1].strip() if ',' in line else 'Unknown'
            
            current_channel.update({
                'tvg_id': tvg_id,
                'tvg_logo': tvg_logo,
                'category': category,
                'name': name
            })
            
        elif line and not line.startswith('#') and current_channel:
            # This is the stream URL
            current_channel['url'] = line
            channels.append(current_channel)
            
            # Add to category
            cat = current_channel['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(current_channel)
            current_channel = None
    
    return {
        'categories': categories,
        'channels': channels,
        'total': len(channels)
    }


@api_bp.route('/api/playlist')
def api_playlist():
    """
    Return playlist as JSON with categories for the browser UI.
    
    Query params:
        - username: required
        - password: required
        - category: optional filter by category
    """
    username = request.args.get('username')
    password = request.args.get('password')
    category_filter = request.args.get('category')
    
    # Authenticate
    if not username or not password or not check_auth(username, password):
        return {'error': 'Authentication failed'}, 401
    
    # Get or fetch playlist
    cached = get_cached_playlist(username, max_age_seconds=3600)
    if not cached:
        playlists = Playlist.query.filter_by(status='active').all()
        upstream_contents = {}
        
        for playlist in playlists:
            content = fetch_from_upstream(playlist.url)
            if content:
                upstream_contents[playlist.name] = content
        
        if not upstream_contents:
            return {'error': 'No content available', 'channels': [], 'categories': {}}, 503
        
        cached = combine_playlists(upstream_contents)
        cache_playlist(username, cached)
    
    # Parse and return
    parsed = parse_m3u_playlist(cached)
    
    # Filter by category if requested
    if category_filter:
        cat_channels = parsed['categories'].get(category_filter, [])
        return {
            'category': category_filter,
            'channels': cat_channels,
            'total': len(cat_channels),
            'all_categories': list(parsed['categories'].keys())
        }
    
    return {
        'total': parsed['total'],
        'categories': parsed['categories'],
        'all_categories': list(parsed['categories'].keys())
    }


