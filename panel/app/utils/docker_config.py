import yaml
import os

COMPOSE_FILE = '/app/docker-compose.yml'  # Path inside the container (mounted from host)
# Note: In our docker-compose, we mounted 'docker-compose.yml' to root? 
# Let's check. We actually haven't mounted it yet! We need to fix that.
# Assuming it WILL be mounted to /app/docker-compose.yml or similar.
# For now, let's assume we will mount it to /config/docker-compose.yml to avoid overwriting code.

def load_compose_config(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_compose_config(path, config):
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

def get_transport_routes(compose_path='/config/docker-compose.yml'):
    config = load_compose_config(compose_path)
    mfp_service = config.get('services', {}).get('mfp', {})
    env = mfp_service.get('environment', {})
    
    # Environment can be list or dict. We need to handle both.
    # But usually in our file it is a dict or list of strings.
    # The 'mediaflow-proxy' uses a JSON string for TRANSPORT_ROUTES.
    
    transport_routes_str = '{}'
    if isinstance(env, dict):
        transport_routes_str = env.get('TRANSPORT_ROUTES', '{}')
    elif isinstance(env, list):
        for item in env:
            if item.startswith('TRANSPORT_ROUTES='):
                transport_routes_str = item.split('=', 1)[1]
                break
                
    # It might be a string literal of a dict, need to parse carefully if it's not valid JSON
    # But PyYAML might handle it if it was loaded as an object? 
    # Actually, TRANSPORT_ROUTES in docker-compose is typically a string containing JSON.
    import json
    try:
        # It might be forced as a string in YAML, causing double escaping?
        # Let's try to parse it.
        return json.loads(transport_routes_str)
    except:
        return {}

def update_transport_routes(routes, compose_path='/config/docker-compose.yml'):
    config = load_compose_config(compose_path)
    
    # Ensure structure exists
    if 'services' not in config: config['services'] = {}
    if 'mfp' not in config['services']: config['services']['mfp'] = {}
    if 'environment' not in config['services']['mfp']: config['services']['mfp']['environment'] = {}
    
    env = config['services']['mfp']['environment']
    
    import json
    routes_json = json.dumps(routes, indent=None)
    
    if isinstance(env, dict):
        env['TRANSPORT_ROUTES'] = f"'{routes_json}'" # Wrap in quotes for YAML safety?
        # Actually yaml.dump will handle the quoting if it sees special chars.
        env['TRANSPORT_ROUTES'] = routes_json
    elif isinstance(env, list):
        # Remove existing
        new_env = [e for e in env if not e.startswith('TRANSPORT_ROUTES=')]
        new_env.append(f"TRANSPORT_ROUTES={routes_json}")
        config['services']['mfp']['environment'] = new_env
        
    save_compose_config(compose_path, config)
