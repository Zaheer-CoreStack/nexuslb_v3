from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..utils.docker_config import get_transport_routes, update_transport_routes
import docker

proxy_bp = Blueprint('proxy', __name__)
COMPOSE_PATH = '/config/docker-compose.yml' # We need to mount this!

@proxy_bp.route('/proxy')
@login_required
def index():
    routes = get_transport_routes(COMPOSE_PATH)
    return render_template('proxy.html', routes=routes)

@proxy_bp.route('/proxy/add', methods=['POST'])
@login_required
def add_route():
    pattern = request.form.get('pattern')
    proxy_url = request.form.get('proxy_url')
    verify_ssl = True if request.form.get('verify_ssl') else False
    
    if not pattern:
        flash('Pattern is required', 'error')
        return redirect(url_for('proxy.index'))
        
    routes = get_transport_routes(COMPOSE_PATH)
    routes[pattern] = {
        "proxy_url": proxy_url if proxy_url else None,
        "verify_ssl": verify_ssl,
        "proxy": True
    }
    
    # Remove proxy_url if empty to fallback to default
    if not proxy_url:
        del routes[pattern]['proxy_url']
        
    update_transport_routes(routes, COMPOSE_PATH)
    flash('Route added. Click Restart Proxy to apply.', 'success')
    return redirect(url_for('proxy.index'))

@proxy_bp.route('/proxy/delete', methods=['POST'])
@login_required
def delete_route():
    pattern = request.form.get('pattern')
    routes = get_transport_routes(COMPOSE_PATH)
    
    if pattern in routes:
        del routes[pattern]
        update_transport_routes(routes, COMPOSE_PATH)
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
