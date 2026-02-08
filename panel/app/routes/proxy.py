from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..utils.docker_config import get_transport_routes, update_transport_routes
from .. import db
import docker

proxy_bp = Blueprint('proxy', __name__)
CONFIG_PATH = '/config/mfp_config.env' 


@proxy_bp.route('/proxy')
@login_required
def index():
    routes = get_transport_routes(CONFIG_PATH)
    
    # Webshare Data
    api_keys = WebshareService.get_api_keys()
    
    # Proxy Stats
    total_proxies = ProxyPool.query.count()
    active_proxies = ProxyPool.query.filter_by(status='active').count()
    
    # Group by Country
    from sqlalchemy import func
    country_stats = db.session.query(
        ProxyPool.country_code, func.count(ProxyPool.id)
    ).group_by(ProxyPool.country_code).all()
    
    return render_template('proxy.html', 
                         routes=routes, 
                         api_keys=api_keys, 
                         total_proxies=total_proxies,
                         active_proxies=active_proxies,
                         country_stats=country_stats)

@proxy_bp.route('/proxy/add', methods=['POST'])
@login_required
def add_route():
    pattern = request.form.get('pattern')
    proxy_url = request.form.get('proxy_url')
    verify_ssl = True if request.form.get('verify_ssl') else False
    
    if not pattern:
        flash('Pattern is required', 'error')
        return redirect(url_for('proxy.index'))
        
    routes = get_transport_routes(CONFIG_PATH)
    routes[pattern] = {
        "proxy_url": proxy_url if proxy_url else None,
        "verify_ssl": verify_ssl,
        "proxy": True
    }
    
    # Remove proxy_url if empty to fallback to default
    if not proxy_url:
        del routes[pattern]['proxy_url']
        
    update_transport_routes(routes, CONFIG_PATH)
    flash('Route added. Click Restart Proxy to apply.', 'success')
    return redirect(url_for('proxy.index'))

@proxy_bp.route('/proxy/delete', methods=['POST'])
@login_required
def delete_route():
    pattern = request.form.get('pattern')
    routes = get_transport_routes(CONFIG_PATH)
    
    if pattern in routes:
        del routes[pattern]
        update_transport_routes(routes, CONFIG_PATH)
        flash('Route deleted.', 'success')
    else:
        flash('Route not found.', 'error')
        
    return redirect(url_for('proxy.index'))

@proxy_bp.route('/proxy/restart', methods=['POST'])
@login_required
def restart_proxy():
    try:
        client = docker.from_env()
        container = client.containers.get('mfp')
        container.restart()
        flash('MediaFlow Proxy restarted successfully.', 'success')
    except Exception as e:
        flash(f'Error restarting proxy: {str(e)}', 'error')
    
    return redirect(url_for('proxy.index'))

# --- Webshare Integration Routes ---

from ..services.webshare import WebshareService
from ..models import ProxyPool

@proxy_bp.route('/proxy/webshare/keys', methods=['POST'])
@login_required
def manage_keys():
    action = request.form.get('action')
    key = request.form.get('key')
    
    if action == 'add' and key:
        if WebshareService.add_api_key(key):
            flash('API Key added.', 'success')
        else:
            flash('API Key already exists.', 'warning')
    elif action == 'remove' and key:
        WebshareService.remove_api_key(key)
        flash('API Key removed.', 'success')
        
    return redirect(url_for('proxy.index'))

@proxy_bp.route('/proxy/webshare/sync', methods=['POST'])
@login_required
def sync_proxies():
    try:
        count = WebshareService.sync_proxies()
        flash(f'Synced {count} proxies from Webshare.', 'success')
    except Exception as e:
        flash(f'Error syncing proxies: {str(e)}', 'error')
    return redirect(url_for('proxy.index'))

@proxy_bp.route('/proxy/webshare/get-best', methods=['GET'])
@login_required
def get_best_proxy():
    country = request.args.get('country')
    proxy = WebshareService.get_best_proxy(country)
    if proxy:
        return {
            'status': 'found',
            'url': proxy.to_proxy_url(), 
            'country': proxy.country_code
        }
    return {'status': 'none'}, 404
