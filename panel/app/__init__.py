from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, static_url_path='/panel/static')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-this')
    # Use /instance/panel.db for persistence (mounted volume)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////instance/panel.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .models import Admin
    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    # Blueprints
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.users import users_bp
    
    app.register_blueprint(auth_bp, url_prefix='/panel')
    app.register_blueprint(dashboard_bp, url_prefix='/panel')
    app.register_blueprint(users_bp, url_prefix='/panel')

    from .routes.proxy import proxy_bp
    app.register_blueprint(proxy_bp, url_prefix='/panel')

    from .routes.playlists import playlists_bp
    app.register_blueprint(playlists_bp, url_prefix='/panel')

    from .routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/') # Root prefix for get.php

    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        if not Admin.query.filter_by(username='admin').first():
            from werkzeug.security import generate_password_hash
            default_admin = Admin(
                username='admin', 
                password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123'))
            )
            db.session.add(default_admin)
            db.session.commit()

    # Scheduler for Webshare Sync
    from flask_apscheduler import APScheduler
    scheduler = APScheduler()
    app.config['SCHEDULER_API_ENABLED'] = True
    scheduler.init_app(app)
    
    from .services.webshare import WebshareService

    def run_proxy_sync():
        """Sync proxies from Webshare"""
        try:
            logger = __import__('logging').getLogger(__name__)
            count = WebshareService.sync_proxies()
            logger.info(f"Proxy sync completed: {count} proxies")
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.error(f"Proxy sync error: {e}")

    # Schedule proxy sync every 6 hours
    @scheduler.task('interval', id='sync_webshare_proxies', hours=6)
    def scheduled_proxy_sync():
        with app.app_context():
            run_proxy_sync()

    scheduler.start()
    
    # Run initial sync on startup
    with app.app_context():
        run_proxy_sync()

    return app
