# app/__init__.py
from flask import Flask, session
from datetime import datetime
import os

from .config import BaseConfig, DevConfig, ProdConfig  # asegúrate de tener estas clases
from .extensions import db
from flask_migrate import Migrate
from .i18n import tr

# Blueprints (ok importarlos aquí si no crean la app)
from .routes.main import bp as main_bp
from .routes.auth import bp as auth_bp
from .routes.history import bp as history_bp
from .routes.admin import bp as admin_bp

migrate = Migrate()

def _normalize_database_url(url: str | None) -> str:
    if not url:
        return "sqlite:///local.db"
    # Render/Heroku a veces entregan postgres:// -> cámbialo a postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def create_app():
    app = Flask(__name__, static_folder="static")

    # 1) Elegir config por entorno
    cfg_key = (os.getenv("FLASK_CONFIG") or "dev").lower()
    cfg_map = {
        "dev": DevConfig,
        "prod": ProdConfig,
        "production": ProdConfig,
    }
    cfg_cls = cfg_map.get(cfg_key, DevConfig)
    app.config.from_object(BaseConfig)
    app.config.from_object(cfg_cls)

    # 2) Fallbacks/overrides por env (sin pisar lo ya definido)
    app.config.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "dev"))
    app.config.setdefault("APP_VERSION", os.getenv("APP_VERSION", "v0"))

    # Normaliza DATABASE_URL (si existe) o usa sqlite local
    env_db = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(
        env_db or app.config.get("SQLALCHEMY_DATABASE_URI")
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    # Opcional: para que Jinja no reordene dicts en JSON embebido
    app.config.setdefault("JSON_SORT_KEYS", False)

    # 3) Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)

    # 4) Registrar blueprints (una sola vez)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(admin_bp)

    # 5) Asegurar modelos para migraciones (no uses create_all; usa Alembic)
    with app.app_context():
        from . import models  # noqa: F401

    # 6) Helpers globales a plantillas
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
