from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user
import psutil
import platform
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # Gather System Stats
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    system_info = {
        'os': platform.system(),
        'node': platform.node(),
        'release': platform.release(),
        'uptime': datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Placeholder, explicit uptime needs boot time calc
    }

    return render_template('dashboard.html', 
                         cpu_usage=cpu_percent,
                         memory_usage=memory.percent,
                         disk_usage=disk.percent,
                         system_info=system_info,
                         user=current_user)
