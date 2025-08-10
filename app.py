from flask import Flask, request, render_template_string, session, redirect, url_for, flash
import fitz  # PyMuPDF
import os
import markdown
from openai import OpenAI
import openai
import google.generativeai as genai
import langdetect
import re
import secrets, string, requests
from urllib.parse import urlencode
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

# ======================
# Configuración de claves/env
# ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:10000")
FLASK_SECRET = os.getenv("FLASK_SECRET", "dev-secret-change-me")

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Gemini (opcional, fallback)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Google OAuth config
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"
GOOGLE_REDIRECT_URI = f"{APP_BASE_URL}/auth/callback"

# ======================
# Flask app
# ======================
app = Flask(__name__)
app.secret_key = FLASK_SECRET  # importante para sesiones seguras

# ======================
# HTML (template)
# ======================
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CV Compatibility Scanner</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .gauge-wrap { position: relative; width: 100%; max-width: 460px; margin: 0 auto; aspect-ratio: 2 / 1; }
    .gauge { width: 100%; height: 100%; }
    .needle { transform-origin: 50% 100%; transition: transform 0.8s ease-in-out; }
    .score-label { position: absolute; bottom: 8%; left: 50%; transform: translateX(-50%); font-size: 1.75rem; font-weight: 700; }
    .model-badge { font-size: .9rem; }
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
    <h1 class="mb-0">CV Compatibility Scanner</h1>
    <div class="text-end">
      {% if email %}
        <div class="d-flex align-items-center justify-content-end gap-2">
          <span><strong>{{ email }}</strong></span>
          <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('logout') }}">Logout</a>
        </div>
      {% else %}
        <a class="btn btn-sm btn-outline-primary" href="{{ url_for('login') }}">Login con Google</a>
      {% endif %}
    </div>
  </div>

  <div class="row g-4">
    <!-- Izquierda: Form -->
    <div class="col-12 col-lg-6">
      <div class="card p-4 shadow-sm h-100">
        <form method="post" enctype="multipart/form-data">
          {% if not email %}
          <div class="mb-3">
            <label class="form-label">Email (si no iniciaste sesión):</label>
            <input type="email" class="form-control" name="email" placeholder="tu@email.com">
            <div class="form-text">Si inicias sesión con Google no hace falta completar este campo.</div>
          </div>
          {% endif %}
          <div class="mb-3">
            <label class="form-label">Upload your CV (PDF):</label>
            <input type="file" class="form-control" name="cv" required>
          </div>
          <div class="mb-3">
            <label class="form-label">Paste the job description:</label>
            <textarea name="jobdesc" class="form-control" rows="6" required></textarea>
          </div>
          <button type="submit" class="btn btn-primary w-100">Analyze</button>
        </form>
      </div>
    </div>

    <!-- Derecha: Gauge -->
    <div class="col-12 col-lg-6">
      <div class="card p-4 shadow-sm h-100 d-flex align-items-center justify-content-center">
        {% if score is not none %}
          <div class="gauge-wrap">
            <svg class="gauge" viewBox="0 0 200 100" aria-label="Match score gauge">
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
          <div class="text-muted text-center">Sube tu CV y descripción para ver el tacómetro de coincidencia.</div>
        {% endif %}
      </div>
    </div>
  </div>

  {% if feedback %}
  <div class="card mt-4 p-4 shadow-sm">
    <div class="d-flex justify-content-between align-items-center mb-2">
      <h3 class="mb-0">AI Feedback</h3>
      <div>
        {% if model_used == 1 %}
          <span class="badge text-bg-primary model-badge">Modelo 1: OpenAI</span>
        {% elif model_used == 2 %}
          <span class="badge text-bg-success model-badge">Modelo 2: Gemini</span>
        {% endif %}
        {% if model_used == 2 and oi_error %}
          <span class="badge text-bg-secondary ms-2">{{ oi_error }}</span>
        {% endif %}
      </div>
    </div>
    <div>{{ feedback|safe }}</div>
  </div>
  {% endif %}
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

# ======================
# Utilitarios
# ======================
def extract_text_from_pdf(file_stream):
    doc = fitz.open(stream=file_stream.read(), filetype="pdf")
    text = "\n".join([page.get_text() for page in doc])
    return text

def detectar_idioma(texto):
    try:
        idioma = langdetect.detect(texto)
        return "es" if idioma.startswith("es") else "en"
    except Exception:
        return "en"

def extraer_score(texto):
    """Intenta extraer un valor 0–100 desde el feedback."""
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
                if 0 <= val <= 100:
                    return val
            except Exception:
                pass
    return None

def _rand(n=24):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

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
        resp = client.responses.create(
            model="gpt-4o",
            input=prompt,
            temperature=0.2
        )
        return resp.output_text, None
    except openai.RateLimitError as e:
        err = str(e); print("[OpenAI RateLimitError]", err)
        if "insufficient_quota" in err:
            return None, "Sin cuota en la API de OpenAI"
        return None, "Rate limit de OpenAI"
    except openai.AuthenticationError as e:
        print("[OpenAI AuthError]", e); return None, "API key inválida o faltante"
    except openai.PermissionDeniedError as e:
        print("[OpenAI PermissionDenied]", e); return None, "Sin acceso al modelo gpt-4o"
    except openai.APIConnectionError as e:
        print("[OpenAI APIConnectionError]", e); return None, "Falla de conexión con OpenAI"
    except openai.APIStatusError as e:
        print("[OpenAI APIStatusError]", e); code = getattr(e, "status_code", "error")
        return None, f"OpenAI devolvió {code}"
    except Exception as e:
        print("[OpenAI UnknownError]", e); return None, "Error desconocido con OpenAI"

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
# Rutas de autenticación Google
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
    if not code:
        return "Missing code", 400

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
        idinfo = id_token.verify_oauth2_token(
            tokens["id_token"],
            grequests.Request(),
            GOOGLE_CLIENT_ID
        )
        if idinfo.get("nonce") and idinfo["nonce"] != session.get("oauth_nonce"):
            return "Invalid nonce", 400
    except Exception as e:
        return f"ID token invalid: {e}", 400

    session["user_email"] = idinfo.get("email")
    session["user_name"] = idinfo.get("name")
    session["user_picture"] = idinfo.get("picture")

    return redirect(url_for("scan"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("scan"))

# ======================
# Ruta principal
# ======================
@app.route('/', methods=['GET', 'POST'])
def scan():
    feedback = None
    model_used = None  # 1=OpenAI, 2=Gemini
    score = None
    oi_error = None

    email = session.get("user_email")  # si está logueado con Google

    if request.method == 'POST':
        # Si no hay login, aceptamos email manual (opcional)
        form_email = (request.form.get('email') or "").strip().lower()
        if email:
            form_email = email  # prioriza el email autenticado

        cv_file = request.files.get('cv')
        jobdesc = request.form.get('jobdesc', "")

        if not cv_file or not jobdesc:
            flash("Faltan archivo y/o descripción del puesto.")
            return redirect(url_for('scan'))

        cv_text = extract_text_from_pdf(cv_file)

        # Ejecutar análisis
        feedback_text, oi_error = analizar_con_openai(cv_text, jobdesc)
        if feedback_text:
            model_used = 1
        elif GEMINI_API_KEY:
            feedback_text = analizar_con_gemini(cv_text, jobdesc)
            if feedback_text:
                model_used = 2

        if feedback_text:
            score = extraer_score(feedback_text)
            feedback = markdown.markdown(feedback_text)

    return render_template_string(
        HTML_TEMPLATE,
        feedback=feedback,
        model_used=model_used,
        score=score,
        oi_error=oi_error,
        email=email or ""
    )

# ======================
# Main
# ======================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
