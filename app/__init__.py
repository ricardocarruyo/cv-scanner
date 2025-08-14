from flask import Flask
from .config import Config
from .extensions import db
from .routes.main import bp as main_bp
from .routes.auth import bp as auth_bp
from .routes.history import bp as history_bp
from .routes.admin import bp as admin_bp
from datetime import datetime

def create_app():
    app = Flask(__name__, static_folder="static")
    app.config.from_object(Config)

    # Inicializar extensiones
    db.init_app(app)

    # Registrar blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        from . import models  # asegura que las tablas se conozcan
        # db.create_all()  # mejor usar migraciones (Alembic)
    
    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.utcnow().year,
            "version": app.config.get("APP_VERSION", "v0")
        }

    return app
