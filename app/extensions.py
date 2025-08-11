from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
import google.generativeai as genai
import os

db = SQLAlchemy()

def openai_client():
    key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=key) if key else None

def gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai
