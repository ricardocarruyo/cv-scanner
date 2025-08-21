from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
import google.generativeai as genai
import os, logging
from sqlalchemy import MetaData

_log = logging.getLogger(__name__)
_openai_singleton = None

# Convención de nombres recomendable para Alembic
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})
db = SQLAlchemy(metadata=metadata)

def openai_client():
    global _openai_singleton
    if _openai_singleton:
        return _openai_singleton
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _log.error("OPENAI_API_KEY no está definido en el entorno")
        return None
    try:
        _openai_singleton = OpenAI(api_key=api_key)
        return _openai_singleton
    except Exception as e:
        _log.exception("No se pudo crear el cliente de OpenAI: %s", e)
        return None

# ---- Gemini (importación segura)
try:
    import google.generativeai as genai  # puede no estar instalado en dev
except Exception:
    genai = None

def gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai
