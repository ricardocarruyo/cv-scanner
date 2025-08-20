from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
import google.generativeai as genai
import os
from sqlalchemy import MetaData

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
    key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=key) if key else None

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
