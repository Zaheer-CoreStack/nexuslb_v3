import os
import json

def get_transport_routes(config_path='/config/mfp_config.env'):
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r') as f:
            for line in f:
                if line.strip().startswith('TRANSPORT_ROUTES='):
                    # Extract the value part: TRANSPORT_ROUTES='...'
                    # We expect the value to be single-quoted JSON string
                    value = line.split('=', 1)[1].strip()
                    if (value.startswith("'") and value.endswith("'")) or \
                       (value.startswith('"') and value.endswith('"')):
                        value = value[1:-1]
                    
                    return json.loads(value)
    except Exception as e:
        print(f"Error reading transport routes: {e}")
        return {}
    
    return {}

def update_transport_routes(routes, config_path='/config/mfp_config.env'):
    # Read existing content to preserve other vars if any (though currently only transport routes)
    lines = []
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            lines = f.readlines()
            
    # Prepare new line
    routes_json = json.dumps(routes, separators=(',', ':')) # Compact JSON
    new_line = f"TRANSPORT_ROUTES='{routes_json}'\n"
    
    # Update or append
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith('TRANSPORT_ROUTES='):
            lines[i] = new_line
            updated = True
            break
            
    if not updated:
        lines.append(new_line)
        
    with open(config_path, 'w') as f:
        f.writelines(lines)
