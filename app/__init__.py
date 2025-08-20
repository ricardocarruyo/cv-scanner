from flask import Flask, session
from datetime import datetime
import os

from .config import Config
from .extensions import db            # <-- usa el db único aquí
from flask_migrate import Migrate
from .i18n import tr

# Blueprints
from .routes.main import bp as main_bp
from .routes.auth import bp as auth_bp
from .routes.history import bp as history_bp
from .routes.admin import bp as admin_bp

migrate = Migrate()  # no crees otro SQLAlchemy aquí

def create_app():
    app = Flask(__name__, static_folder="static")

    # 1) Carga config base desde tu clase
    app.config.from_object(Config)

    # 2) Completa/fallback desde variables de entorno si algo falta
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", os.getenv("DATABASE_URL", "sqlite:///local.db"))
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "dev"))
    app.config.setdefault("APP_VERSION", os.getenv("APP_VERSION", "v0"))

    # 3) Inicializa extensiones (un ÚNICO db)
    db.init_app(app)
    migrate.init_app(app, db)

    # 4) Registra blueprints una sola vez
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(admin_bp)

    # 5) Asegura que los modelos se importen (para migraciones)
    with app.app_context():
        from . import models  # noqa: F401
        # NO hagas db.create_all(); usa flask db upgrade

    # 6) Inyecta helpers/vars globales para las plantillas
    @app.context_processor
    def inject_globals():
        lang = (session.get("lang") or "es").lower()
        def t(key, **kwargs):
            return tr(lang, key, **kwargs)
        return {
            "current_year": datetime.utcnow().year,
            "version": app.config.get("APP_VERSION", "v0"),
            "is_en": (lang == "en"),
            "t": t,
        }

    return app
