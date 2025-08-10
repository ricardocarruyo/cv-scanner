from flask import Flask, request, render_template_string, session, redirect, url_for, flash, Response, make_response, send_file
import os, re, io, secrets, string, requests, math, csv
from urllib.parse import urlencode
from datetime import datetime
from io import StringIO

import fitz  # PyMuPDF
import markdown
import bleach
import langdetect
from openai import OpenAI
import openai
import google.generativeai as genai
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from docx import Document  # python-docx

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# --- DB (SQLAlchemy) ---
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ======================
# ENV / Config
# ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:10000")
FLASK_SECRET = os.getenv("FLASK_SECRET", "dev-secret-change-me")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///usage.db")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")  # si lo defines, ese correo verá /admin y todo el historial

ALLOWED_EXTS = {"pdf", "docx"}
MAX_MB = 10

# ======================
# Flask app & seguridad
# ======================
app = Flask(__name__, static_folder="static")
app.secret_key = FLASK_SECRET
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=MAX_MB * 1024 * 1024,
)

# ======================
# LLM clients
# ======================
client = OpenAI(api_key=OPENAI_API_KEY)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"
GOOGLE_REDIRECT_URI = f"{APP_BASE_URL}/auth/callback"

# ======================
# DB setup
# ======================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    email = Column(String(320), primary_key=True)
    given_name = Column(String(120))
    family_name = Column(String(120))
    full_name = Column(String(300))
    picture = Column(Text)
    occupation = Column(String(200))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime)
    # último análisis
    last_model_vendor = Column(String(20))
    last_model_name = Column(String(50))
    last_score = Column(Integer)
    last_exec_id = Column(Integer)
    last_analysis_at = Column(DateTime)

    executions = relationship("Execution", back_populates="user")
    comments = relationship("Comment", back_populates="user")

class Execution(Base):
    __tablename__ = "executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), ForeignKey("users.email"))
    uploaded_filename = Column(Text)
    uploaded_ext = Column(String(10))
    uploaded_size = Column(Integer)
    resume_lang = Column(String(5))
    jd_lang = Column(String(5))
    model_vendor = Column(String(20))   # "openai" | "gemini"
    model_name = Column(String(50))     # "gpt-4o" | "gemini-1.5-flash"
    score = Column(Integer)
    feedback_text = Column(Text)        # guardamos el feedback para exportar PDF
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user = relationship("User", back_populates="executions")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), ForeignKey("users.email"), nullable=True)
    name = Column(String(300))
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user = relationship("User", back_populates="comments")

Base.metadata.create_all(engine)

# ======================
# HTML templates
# ======================
HTML_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CV Match Scanner</title>
  <link rel="apple-touch-icon" sizes="180x180" href="{{ url_for('static', filename='apple-touch-icon.png') }}">
  <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', filename='favicon-32x32.png') }}">
  <link rel="icon" type="image/png" sizes="16x16" href="{{ url_for('static', filename='favicon-16x16.png') }}">
  <link rel="manifest" href="{{ url_for('static', filename='site.webmanifest') }}">
  <link rel="shortcut icon" href="{{ url_for('static', filename='favicon.ico') }}">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
  <style>
    .gauge-wrap { position: relative; width: 100%; max-width: 460px; margin: 0 auto; aspect-ratio: 2 / 1; }
    .gauge { width: 100%; height: 100%; }
    .needle { transform-origin: 50% 100%; transition: transform 0.8s ease-in-out; }
    .score-label { position: absolute; bottom: 8%; left: 50%; transform: translateX(-50%); font-size: 1.75rem; font-weight: 700; }
    .model-badge { font-size: .9rem; }
    .avatar { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; }
  </style>
</head>
<body class="bg-light">
<div class="container py-4">

  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="alert alert-info" role="alert">{{ messages[0] }}</div>
    {% endif %}
  {% endwith %}

  <div class="d-flex justify-content-between align-items-center mb-3">
    <div class="d-flex align-items-center gap-2">
      <h1 class="mb-0">CV Match Scanner</h1>
      <a class="btn btn-sm btn-outline-dark" target="_blank" href="https://youtu.be/4icmc4kkPEY">
        <i class="bi bi-play-circle"></i> Tutorial ATS
      </a>
    </div>
    <div class="text-end">
      {% if email %}
        <div class="d-flex align-items-center justify-content-end gap-2">
          {% if picture %}<img class="avatar" src="{{ picture }}" alt="avatar"/>{% endif %}
          <span><strong>{{ name or email }}</strong></span>
          {% if is_admin %}<a class="btn btn-sm btn-outline-dark" href="{{ url_for('admin') }}"><i class="bi bi-speedometer2"></i> Admin</a>{% endif %}
          <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('history') }}"><i class="bi bi-clock-history"></i> Historial</a>
          <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('logout') }}"><i class="bi bi-box-arrow-right"></i> Cerrar sesión</a>
        </div>
      {% else %}
        <a class="btn btn-sm btn-outline-primary" href="{{ url_for('login') }}"><i class="bi bi-google"></i> Iniciar sesión con Google</a>
      {% endif %}
    </div>
  </div>

  <div class="row g-4">
    <!-- Izquierda: Formulario -->
    <div class="col-12 col-lg-6">
      <div class="card p-4 shadow-sm h-100">
        <form method="post" enctype="multipart/form-data">
          {% if not email %}
          <div class="mb-3">
            <label class="form-label">Correo electrónico (si no iniciaste sesión):</label>
            <input type="email" class="form-control" name="email" placeholder="tu@email.com">
          </div>
          {% endif %}

          <div class="mb-3">
            <label class="form-label">Ocupación (opcional):</label>
            <input type="text" class="form-control" name="occupation" placeholder="Ej.: Analista de Negocio, QA, DevOps" value="{{ occupation or '' }}">
          </div>

          <div class="mb-2">
            <label class="form-label">Sube tu CV (PDF o DOCX, máx. {{ max_mb }} MB):</label>
            <input type="file" class="form-control" name="cv" accept=".pdf,.docx" required>
            <div class="form-text">Por seguridad, solo permitimos PDF/DOCX y analizamos el contenido para bloquear patrones potencialmente peligrosos.</div>
          </div>

          <div class="mb-3">
            <label class="form-label">Pega la descripción del puesto:</label>
            <textarea name="jobdesc" class="form-control" rows="6" required></textarea>
          </div>

          <button type="submit" class="btn btn-primary w-100"><i class="bi bi-search"></i> Analizar</button>
        </form>
      </div>
    </div>

    <!-- Derecha: Tacómetro -->
    <div class="col-12 col-lg-6">
      <div class="card p-4 shadow-sm h-100 d-flex align-items-center justify-content-center">
        {% if score is not none %}
          <div class="gauge-wrap">
            <svg class="gauge" viewBox="0 0 200 100" aria-label="Indicador de coincidencia">
              <path d="M10,100 A90,90 0 0 1 190,100" fill="none" stroke="#eee" stroke-width="20"/>
              <defs>
                <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#dc3545"/>
                  <stop offset="50%" stop-color="#ffc107"/>
                  <stop offset="100%" stop-color="#28a745"/>
                </linearGradient>
              </defs>
              <path d="M10,100 A90,90 0 0 1 190,100" fill="none" stroke="url(#g)" stroke-width="20" stroke-linecap="round"/>
              <g id="needle" class="needle">
                <polygon points="100,96 97,100 103,100" fill="#333"/>
                <rect x="99" y="10" width="2" height="90" fill="#333"/>
                <circle cx="100" cy="100" r="4" fill="#333"/>
              </g>
              <text x="10" y="98" font-size="10" fill="#6c757d">0</text>
              <text x="185" y="98" font-size="10" fill="#6c757d">100</text>
            </svg>
            <div class="score-label">{{ score }}%</div>
          </div>
        {% else %}
          <div class="text-muted text-center">Sube tu CV y la descripción para ver el indicador de coincidencia.</div>
        {% endif %}
      </div>
    </div>
  </div>

  {% if feedback %}
  <div class="card mt-4 p-4 shadow-sm">
    <div class="d-flex justify-content-between align-items-center mb-2">
      <h3 class="mb-0">Análisis de la IA</h3>
      <div class="d-flex gap-2">
        {% if model_used == 1 %}
          <span class="badge text-bg-primary model-badge"><i class="bi bi-cpu"></i> Modelo 1: OpenAI</span>
        {% elif model_used == 2 %}
          <span class="badge text-bg-success model-badge"><i class="bi bi-stars"></i> Modelo 2: Gemini</span>
        {% endif %}
        {% if exec_id %}
          <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('download_pdf', exec_id=exec_id) }}"><i class="bi bi-file-earmark-arrow-down"></i> Descargar PDF</a>
        {% endif %}
      </div>
    </div>
    <div>{{ feedback|safe }}</div>
  </div>
  {% endif %}

  <div class="card mt-4 p-4 shadow-sm">
    <h4 class="mb-3"><i class="bi bi-chat-text"></i> ¿Tienes sugerencias para mejorar?</h4>
    <form method="post" action="{{ url_for('leave_comment') }}">
      <div class="mb-2">
        <label class="form-label">Tu comentario</label>
        <textarea class="form-control" name="comment" rows="3" maxlength="2000" required></textarea>
      </div>
      <div class="d-flex justify-content-between align-items-center">
        <div class="small text-muted">Gracias por ayudar a mejorar el servicio</div>
        <button class="btn btn-outline-primary"><i class="bi bi-send"></i> Enviar</button>
      </div>
    </form>
  </div>

</div>

{% if score is not none %}
<script>
  (function() {
    var score = {{ score }};
    var deg = Math.max(0, Math.min(100, score)) * 1.8; // 0-100 => 0-180°
    var needle = document.getElementById("needle");
    if (needle) needle.style.transform = "rotate(" + deg + "deg)";
  })();
</script>
{% endif %}
</body>
</html>
"""

HISTORY_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Historial · CV Match Scanner</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Historial</h2>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-secondary" href="{{ url_for('scan') }}">Volver</a>
      <div class="btn-group">
        <a class="btn btn-outline-success" href="{{ url_for('export_history', kind='executions') }}">Exportar ejecuciones (CSV)</a>
        <a class="btn btn-outline-success" href="{{ url_for('export_history', kind='comments') }}">Exportar comentarios (CSV)</a>
      </div>
    </div>
  </div>

  <div class="mb-3 text-muted">
    {% if is_admin %}
      <span class="badge text-bg-dark">Administrador</span> Viendo todas las ejecuciones y comentarios
    {% else %}
      Mostrando datos de <strong>{{ email }}</strong>
    {% endif %}
  </div>

  <div class="card p-3 shadow-sm mb-4">
    <h4>Ejecuciones</h4>
    <div class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Archivo</th>
            <th>Ext</th>
            <th>Tamaño</th>
            <th>Modelo</th>
            <th>Puntaje</th>
            <th>Idioma CV</th>
            <th>Idioma JD</th>
            {% if is_admin %}<th>Correo</th>{% endif %}
          </tr>
        </thead>
        <tbody>
          {% for e in executions %}
          <tr>
            <td>{{ e.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
            <td>{{ e.uploaded_filename or '-' }}</td>
            <td>{{ e.uploaded_ext or '-' }}</td>
            <td>{{ (e.uploaded_size or 0) // 1024 }} KB</td>
            <td>{{ (e.model_vendor or '-') ~ ' / ' ~ (e.model_name or '-') }}</td>
            <td>{{ e.score if e.score is not none else '-' }}</td>
            <td>{{ e.resume_lang or '-' }}</td>
            <td>{{ e.jd_lang or '-' }}</td>
            {% if is_admin %}<td>{{ e.email }}</td>{% endif %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <nav aria-label="Ejecuciones">
      <ul class="pagination pagination-sm">
        <li class="page-item {% if page_exec<=1 %}disabled{% endif %}">
          <a class="page-link" href="{{ url_for('history', page_exec=page_exec-1, page_cmt=page_cmt, per_page=per_page) }}">&laquo;</a>
        </li>
        {% for p in range(1, pages_exec+1) %}
          <li class="page-item {% if p==page_exec %}active{% endif %}">
            <a class="page-link" href="{{ url_for('history', page_exec=p, page_cmt=page_cmt, per_page=per_page) }}">{{ p }}</a>
          </li>
        {% endfor %}
        <li class="page-item {% if page_exec>=pages_exec %}disabled{% endif %}">
          <a class="page-link" href="{{ url_for('history', page_exec=page_exec+1, page_cmt=page_cmt, per_page=per_page) }}">&raquo;</a>
        </li>
      </ul>
    </nav>
  </div>

  <div class="card p-3 shadow-sm">
    <h4>Comentarios</h4>
    <div class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Nombre</th>
            <th>Comentario</th>
            {% if is_admin %}<th>Correo</th>{% endif %}
          </tr>
        </thead>
        <tbody>
          {% for c in comments %}
          <tr>
            <td>{{ c.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
            <td>{{ c.name or '-' }}</td>
            <td style="max-width:600px">{{ c.text }}</td>
            {% if is_admin %}<td>{{ c.email or '-' }}</td>{% endif %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <nav aria-label="Comentarios">
      <ul class="pagination pagination-sm">
        <li class="page-item {% if page_cmt<=1 %}disabled{% endif %}">
          <a class="page-link" href="{{ url_for('history', page_exec=page_exec, page_cmt=page_cmt-1, per_page=per_page) }}">&laquo;</a>
        </li>
        {% for p in range(1, pages_cmt+1) %}
          <li class="page-item {% if p==page_cmt %}active{% endif %}">
            <a class="page-link" href="{{ url_for('history', page_exec=page_exec, page_cmt=p, per_page=per_page) }}">{{ p }}</a>
          </li>
        {% endfor %}
        <li class="page-item {% if page_cmt>=pages_cmt %}disabled{% endif %}">
          <a class="page-link" href="{{ url_for('history', page_exec=page_exec, page_cmt=page_cmt+1, per_page=per_page) }}">&raquo;</a>
        </li>
      </ul>
    </nav>
  </div>

</div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Administración · CV Match Scanner</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Panel de administración</h2>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-secondary" href="{{ url_for('scan') }}">Volver</a>
      <a class="btn btn-outline-secondary" href="{{ url_for('history') }}">Historial</a>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-md-4">
      <div class="card p-3 shadow-sm">
        <div class="text-muted">Usuarios totales</div>
        <div class="h3 mb-0">{{ users_count }}</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card p-3 shadow-sm">
        <div class="text-muted">Ejecuciones totales</div>
        <div class="h3 mb-0">{{ execs_count }}</div>
      </div>
    </div>
    <div class="col-md-4">
      <div class="card p-3 shadow-sm">
        <div class="text-muted">Comentarios totales</div>
        <div class="h3 mb-0">{{ comments_count }}</div>
      </div>
    </div>
  </div>

  <div class="card p-3 shadow-sm mt-4">
    <div class="d-flex justify-content-between align-items-center">
      <h4 class="mb-0">Últimos comentarios</h4>
      <form method="post" action="{{ url_for('admin_clear_comments') }}" onsubmit="return confirm('¿Seguro que deseas borrar todos los comentarios?');">
        <button class="btn btn-sm btn-danger">Vaciar comentarios</button>
      </form>
    </div>
    <div class="table-responsive mt-3">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Nombre</th>
            <th>Correo</th>
            <th>Comentario</th>
          </tr>
        </thead>
        <tbody>
          {% for c in recent_comments %}
          <tr>
            <td>{{ c.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
            <td>{{ c.name or '-' }}</td>
            <td>{{ c.email or '-' }}</td>
            <td style="max-width:600px">{{ c.text }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
</body>
</html>
"""

# ======================
# Helpers
# ======================
def _rand(n=24):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def detectar_idioma(texto):
    try:
        idioma = langdetect.detect(texto)
        return "es" if idioma.startswith("es") else "en"
    except Exception:
        return "en"

def extraer_score(texto):
    if not texto:
        return None
    patrones = [
        r"(?:match\s*score|puntuaci[oó]n.*?(?:0.?100)?)\D{0,20}(\b100\b|\b\d{1,2}\b)",
        r"(?:score|coincidencia)\D{0,20}(\b100\b|\b\d{1,2}\b)",
        r"\b(\d{1,3})\s*/\s*100\b",
        r"\b(\d{1,3})\s*%",
        r"\b(\d{1,2})\b"
    ]
    for p in patrones:
        m = re.search(p, texto, flags=re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0 <= val <= 100: return val
            except Exception:
                pass
    return None

def extract_text_from_pdf_bytes(b: bytes) -> str:
    doc = fitz.open(stream=b, filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def extract_text_from_docx_bytes(b: bytes) -> str:
    doc = Document(io.BytesIO(b))
    return "\n".join([p.text for p in doc.paragraphs])

SUSPICIOUS_PATTERNS = [
    r"<script\b", r"</script>", r"<iframe\b", r"onerror\s*=", r"onload\s*=",
    r"document\.cookie", r"eval\s*\(", r"fetch\s*\(", r"xmlhttprequest",
    r"import\s+os", r"subprocess\.Popen", r"socket\.", r"<?php", r"bash -c",
    r"powershell", r"base64,", r"rm -rf /"
]

def looks_suspicious(text: str) -> bool:
    for pat in SUSPICIOUS_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return True
    return False

def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename: return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTS

def _require_login():
    if not session.get("user_email"):
        flash("Inicia sesión para continuar.")
        return False
    return True

def _require_admin():
    if not _require_login():
        return False
    email = session.get("user_email")
    if not (ADMIN_EMAIL and email and email.lower() == ADMIN_EMAIL.lower()):
        flash("No tienes permisos de administrador.")
        return False
    return True

# ======================
# LLMs
# ======================
def analizar_con_openai(cv_text, job_desc):
    idioma = detectar_idioma(cv_text + " " + job_desc)
    idioma_respuesta = "Spanish" if idioma == "es" else "English"

    prompt = f"""
You are a recruiter. Compare the following resume with the job description.
Please write the entire feedback in **{idioma_respuesta}**.

Resume:
{cv_text}

Job Description:
{job_desc}

Respond with:
1. A match score (0–100).
2. Key skills or qualifications missing.
3. Suggestions for improving the resume to better fit the role.
"""
    try:
        resp = client.responses.create(model="gpt-4o", input=prompt, temperature=0.2)
        return resp.output_text, None
    except openai.RateLimitError as e:
        err = str(e)
        if "insufficient_quota" in err:
            return None, "Sin cuota en la API de OpenAI"
        return None, "Rate limit de OpenAI"
    except Exception as e:
        return None, f"Error con OpenAI: {e}"

def analizar_con_gemini(cv_text, job_desc):
    idioma = detectar_idioma(cv_text + " " + job_desc)
    idioma_respuesta = "Spanish" if idioma == "es" else "English"
    prompt = f"""
You are a recruiter. Compare the following resume with the job description.
Please write the entire feedback in **{idioma_respuesta}**.

Resume:
{cv_text}

Job Description:
{job_desc}

Respond with:
1. A match score (0–100).
2. Key skills or qualifications missing.
3. Suggestions for improving the resume to better fit the role.
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

# ======================
# Autenticación Google
# ======================
@app.route("/login")
def login():
    state = _rand()
    nonce = _rand()
    session["oauth_state"] = state
    session["oauth_nonce"] = nonce
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
        "nonce": nonce,
    }
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")

@app.route("/auth/callback")
def auth_callback():
    if request.args.get("state") != session.get("oauth_state"):
        return "Invalid state", 400
    code = request.args.get("code")
    if not code: return "Missing code", 400

    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    tok = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=20)
    if tok.status_code != 200:
        return f"Token exchange failed: {tok.text}", 400
    tokens = tok.json()

    try:
        idinfo = id_token.verify_oauth2_token(tokens["id_token"], grequests.Request(), GOOGLE_CLIENT_ID)
        if idinfo.get("nonce") and idinfo["nonce"] != session.get("oauth_nonce"):
            return "Invalid nonce", 400
    except Exception as e:
        return f"ID token invalid: {e}", 400

    # Guardar/actualizar usuario
    email = idinfo.get("email")
    given = idinfo.get("given_name")
    family = idinfo.get("family_name")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    db = SessionLocal()
    try:
        u = db.get(User, email)
        if not u:
            u = User(email=email, created_at=datetime.utcnow())
            db.add(u)
        u.given_name = given or u.given_name
        u.family_name = family or u.family_name
        u.full_name = name or u.full_name
        u.picture = picture or u.picture
        u.last_login_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    session["user_email"] = email
    session["user_name"] = name
    session["user_picture"] = picture

    return redirect(url_for("scan"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("scan"))

# ======================
# Rutas principales
# ======================
@app.route('/', methods=['GET', 'POST'])
def scan():
    feedback = None
    model_used = None
    score = None
    oi_error = None
    exec_id = None

    email = session.get("user_email")
    name = session.get("user_name")
    picture = session.get("user_picture")
    occupation_value = None
    is_admin = bool(ADMIN_EMAIL and email and email.lower() == (ADMIN_EMAIL or "").lower())

    if request.method == 'POST':
        form_email = (request.form.get('email') or "").strip().lower()
        if email:
            if form_email and form_email != email:
                return "No puedes usar un correo distinto al de tu sesión de Google.", 400
            form_email = email

        occ = (request.form.get('occupation') or "").strip()[:200]

        file = request.files.get('cv')
        jobdesc = request.form.get('jobdesc', "")

        if not file or not jobdesc:
            flash("Faltan el archivo y/o la descripción del puesto.")
            return redirect(url_for('scan'))

        filename = file.filename or ""
        if not allowed_file(filename):
            flash("Formato no permitido. Solo PDF o DOCX.")
            return redirect(url_for('scan'))

        data = file.read()
        size = len(data)
        if size > app.config['MAX_CONTENT_LENGTH']:
            flash(f"El archivo supera {MAX_MB} MB.")
            return redirect(url_for('scan'))

        ext = filename.rsplit(".", 1)[1].lower()
        try:
            if ext == "pdf":
                cv_text = extract_text_from_pdf_bytes(data)
            else:
                cv_text = extract_text_from_docx_bytes(data)
        except Exception:
            flash("No se pudo leer el archivo. Asegúrate de que el PDF/DOCX no esté dañado.")
            return redirect(url_for('scan'))

        sample = (cv_text[:100000] or "")
        if looks_suspicious(sample):
            flash("Detectamos contenido potencialmente peligroso en el archivo. Por seguridad, no podemos procesarlo.")
            return redirect(url_for('scan'))

        feedback_text, oi_error = analizar_con_openai(cv_text, job_desc=jobdesc)
        if feedback_text:
            model_used = 1
            model_vendor, model_name = "openai", "gpt-4o"
        elif GEMINI_API_KEY:
            feedback_text = analizar_con_gemini(cv_text, jobdesc)
            if feedback_text:
                model_used = 2
                model_vendor, model_name = "gemini", "gemini-1.5-flash"
        else:
            feedback_text = None

        if feedback_text:
            score = extraer_score(feedback_text)
            # Markdown -> HTML + sanitización con bleach
            allowed_tags = [
                "p","ul","ol","li","strong","em","b","i","br","hr","blockquote","code","pre",
                "h1","h2","h3","h4","h5","h6","a","table","thead","tbody","tr","th","td"
            ]
            allowed_attrs = {"a": ["href","title","rel","target"]}
            raw_html = markdown.markdown(feedback_text, extensions=["nl2br"])
            safe_html = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs, strip=True)
            feedback = safe_html

        # Guardar en DB
        db = SessionLocal()
        try:
            if form_email:
                u = db.get(User, form_email)
                if not u:
                    u = User(email=form_email, created_at=datetime.utcnow())
                    db.add(u)
                if name: u.full_name = name
                if picture: u.picture = picture
                if occ: u.occupation = occ
                db.commit()
                occupation_value = u.occupation

            if form_email:
                res_lang = detectar_idioma(cv_text)
                jd_lang = detectar_idioma(jobdesc)
                ex = Execution(
                    email=form_email,
                    uploaded_filename=filename,
                    uploaded_ext=ext,
                    uploaded_size=size,
                    resume_lang=res_lang,
                    jd_lang=jd_lang,
                    model_vendor=(model_vendor if feedback_text else None),
                    model_name=(model_name if feedback_text else None),
                    score=(score if score is not None else None),
                    feedback_text=feedback_text or None,
                    created_at=datetime.utcnow()
                )
                db.add(ex)
                db.commit()
                exec_id = ex.id

                # actualizar último análisis del usuario
                u = db.get(User, form_email)
                if u:
                    u.last_model_vendor = ex.model_vendor
                    u.last_model_name = ex.model_name
                    u.last_score = ex.score
                    u.last_exec_id = ex.id
                    u.last_analysis_at = ex.created_at
                    db.commit()
        finally:
            db.close()

    if email and occupation_value is None:
        db = SessionLocal()
        try:
            u = db.get(User, email)
            if u:
                occupation_value = u.occupation
        finally:
            db.close()

    html = render_template_string(
        HTML_TEMPLATE,
        feedback=feedback,
        model_used=model_used,
        score=score,
        oi_error=oi_error,
        email=email or "",
        name=name or "",
        picture=picture or "",
        occupation=occupation_value or "",
        max_mb=MAX_MB,
        is_admin=is_admin,
        exec_id=exec_id
    )
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

@app.route('/feedback', methods=['POST'])
def leave_comment():
    text = (request.form.get('comment') or "").strip()
    if not text:
        flash("El comentario está vacío.")
        return redirect(url_for('scan'))

    email = session.get("user_email")
    name = session.get("user_name")

    db = SessionLocal()
    try:
        c = Comment(
            email=email if email else None,
            name=name if name else None,
            text=text[:2000],
            created_at=datetime.utcnow()
        )
        db.add(c)
        db.commit()
    finally:
        db.close()

    flash("Gracias por tu comentario.")
    return redirect(url_for('scan'))

# ======================
# Historial + export
# ======================
@app.route("/history")
def history():
    if not _require_login():
        return redirect(url_for("scan"))

    viewer = session["user_email"]
    is_admin = (ADMIN_EMAIL and viewer.lower() == ADMIN_EMAIL.lower())

    per_page = max(5, min(50, int(request.args.get("per_page", 10))))
    page_exec = max(1, int(request.args.get("page_exec", 1)))
    page_cmt = max(1, int(request.args.get("page_cmt", 1)))

    db = SessionLocal()
    try:
        q_exec = db.query(Execution).order_by(Execution.created_at.desc())
        q_cmt = db.query(Comment).order_by(Comment.created_at.desc())

        if not is_admin:
            q_exec = q_exec.filter(Execution.email == viewer)
            q_cmt = q_cmt.filter(Comment.email == viewer)

        total_exec = q_exec.count()
        total_cmt = q_cmt.count()

        executions = q_exec.offset((page_exec-1)*per_page).limit(per_page).all()
        comments = q_cmt.offset((page_cmt-1)*per_page).limit(per_page).all()

        pages_exec = max(1, math.ceil(total_exec / per_page)) if total_exec else 1
        pages_cmt  = max(1, math.ceil(total_cmt / per_page)) if total_cmt else 1

        html = render_template_string(
            HISTORY_TEMPLATE,
            email=viewer,
            is_admin=is_admin,
            executions=executions,
            comments=comments,
            page_exec=page_exec,
            page_cmt=page_cmt,
            pages_exec=pages_exec,
            pages_cmt=pages_cmt,
            per_page=per_page
        )
        resp = make_response(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp
    finally:
        db.close()

@app.route("/history/export")
def export_history():
    if not _require_login():
        return redirect(url_for("scan"))

    viewer = session["user_email"]
    is_admin = (ADMIN_EMAIL and viewer.lower() == ADMIN_EMAIL.lower())
    kind = request.args.get("kind", "executions").lower()

    db = SessionLocal()
    try:
        si = StringIO()
        w = csv.writer(si)

        now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        if kind == "comments":
            q = db.query(Comment).order_by(Comment.created_at.desc())
            if not is_admin:
                q = q.filter(Comment.email == viewer)
            w.writerow(["created_at", "name", "email", "text"])
            for c in q.all():
                w.writerow([c.created_at.isoformat(), c.name or "", c.email or "", (c.text or "").replace("\n", " ")])
            filename = f"comments_{'all' if is_admin else viewer}_{now}.csv"
        else:
            q = db.query(Execution).order_by(Execution.created_at.desc())
            if not is_admin:
                q = q.filter(Execution.email == viewer)
            w.writerow(["created_at","email","filename","ext","size_bytes","model_vendor","model_name","score","resume_lang","jd_lang"])
            for e in q.all():
                w.writerow([
                    e.created_at.isoformat(),
                    e.email,
                    e.uploaded_filename or "",
                    e.uploaded_ext or "",
                    e.uploaded_size or 0,
                    e.model_vendor or "",
                    e.model_name or "",
                    e.score if e.score is not None else "",
                    e.resume_lang or "",
                    e.jd_lang or ""
                ])
            filename = f"executions_{'all' if is_admin else viewer}_{now}.csv"

        out = si.getvalue()
        return Response(
            out,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        db.close()

# ======================
# Descarga PDF
# ======================
def _wrap_text(c, text, max_width):
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if c.stringWidth(test, "Helvetica", 11) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines

@app.route("/download-pdf/<int:exec_id>")
def download_pdf(exec_id):
    if not _require_login():
        return redirect(url_for("scan"))
    viewer = session.get("user_email")
    is_admin = (ADMIN_EMAIL and viewer.lower() == ADMIN_EMAIL.lower())

    db = SessionLocal()
    try:
        ex = db.query(Execution).filter(Execution.id == exec_id).first()
        if not ex:
            flash("No se encontró el análisis.")
            return redirect(url_for("scan"))
        if not is_admin and ex.email != viewer:
            flash("No tienes acceso a este análisis.")
            return redirect(url_for("scan"))

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        left, right = 2*cm, A4[0] - 2*cm
        y = height - 2*cm

        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y, "Informe de Análisis (CV Match Scanner)")
        y -= 18

        c.setFont("Helvetica", 11)
        meta = [
            f"Fecha: {ex.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Correo: {ex.email}",
            f"Archivo: {ex.uploaded_filename or '-'}",
            f"Modelo: {(ex.model_vendor or '-')}/{(ex.model_name or '-')}",
            f"Puntaje: {ex.score if ex.score is not None else '-'}",
            f"Idioma CV: {ex.resume_lang or '-'} | Idioma JD: {ex.jd_lang or '-'}",
        ]
        for m in meta:
            c.drawString(left, y, m)
            y -= 14

        y -= 6
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, y, "Análisis:")
        y -= 16

        c.setFont("Helvetica", 11)
        text = ex.feedback_text or "(Sin contenido)"
        text = re.sub(r"<[^>]+>", "", text).replace("\r", "")
        max_width = right - left
        for para in text.split("\n"):
            if not para.strip():
                y -= 10
                continue
            lines = _wrap_text(c, para, max_width)
            for line in lines:
                if y < 2*cm:
                    c.showPage()
                    y = height - 2*cm
                    c.setFont("Helvetica", 11)
                c.drawString(left, y, line)
                y -= 14

        c.showPage()
        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"analisis_{ex.id}.pdf", mimetype="application/pdf")
    finally:
        db.close()

# ======================
# Administración
# ======================
@app.route("/admin")
def admin():
    if not _require_admin():
        return redirect(url_for("scan"))

    db = SessionLocal()
    try:
        users_count = db.query(User).count()
        execs_count = db.query(Execution).count()
        comments_count = db.query(Comment).count()
        recent_comments = db.query(Comment).order_by(Comment.created_at.desc()).limit(20).all()

        html = render_template_string(
            ADMIN_TEMPLATE,
            users_count=users_count,
            execs_count=execs_count,
            comments_count=comments_count,
            recent_comments=recent_comments
        )
        resp = make_response(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp
    finally:
        db.close()

@app.route("/admin/clear-comments", methods=["POST"])
def admin_clear_comments():
    if not _require_admin():
        return redirect(url_for("scan"))
    db = SessionLocal()
    try:
        db.query(Comment).delete()
        db.commit()
        flash("Se borraron todos los comentarios.")
    finally:
        db.close()
    return redirect(url_for("admin"))

# ======================
# Run
# ======================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
