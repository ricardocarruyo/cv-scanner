# config.py
import os

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///local.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_VERSION = os.getenv("APP_VERSION", "local")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

    # URLs
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:10000")
    OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:10000/auth/callback")
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "false").lower() == "true"  # prod=True

    # OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # LLM
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    DONATIONS_ENABLED = os.getenv("DONATIONS_ENABLED", "true").lower() == "true"
    
class DevConfig(BaseConfig):
    DEBUG = True
    # En local normalmente no forzamos https
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "false").lower() == "true"

class ProdConfig(BaseConfig):
    DEBUG = False
    # En prod, por defecto forzamos https (puedes overridear con env)
    FORCE_HTTPS = os.getenv("FORCE_HTTPS", "true").lower() == "true"
