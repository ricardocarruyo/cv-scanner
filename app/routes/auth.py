# app/routes/auth.py
from flask import Blueprint, redirect, url_for, session, request, current_app, flash
from urllib.parse import urlencode
from datetime import datetime
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from ..extensions import db
from ..models import User
from .admin import ensure_level1

bp = Blueprint("auth", __name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"

def _rand(n=24):
    import secrets, string
    a = string.ascii_letters + string.digits
    return "".join(secrets.choice(a) for _ in range(n))

def _callback_url() -> str:
    """
    Devuelve SIEMPRE la misma redirect_uri para /login y /auth/callback.

    Prioridad:
    1) OAUTH_REDIRECT_URI (env/config)  → se usa tal cual.
    2) APP_BASE_URL + '/auth/callback'  → ajusta https si FORCE_HTTPS=true.
    3) request.host_url + '/auth/callback' → último recurso.

    Además, deja trazas en log para depurar rápidamente.
    """
    # 1) Redirect explícito (recomendado en prod y local)
    explicit = current_app.config.get("OAUTH_REDIRECT_URI")
    if explicit:
        current_app.logger.info("OAuth redirect_uri (explicit) = %s", explicit)
        return explicit.rstrip("/")

    # 2) APP_BASE_URL
    base = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    if base:
        if current_app.config.get("FORCE_HTTPS", False) and base.startswith("http://"):
            base = "https://" + base[len("http://"):]
        uri = f"{base}/auth/callback"
        current_app.logger.info("OAuth redirect_uri (from APP_BASE_URL) = %s", uri)
        return uri

    # 3) Último recurso: host actual
    from flask import request
    base = request.host_url.rstrip("/")
    if current_app.config.get("FORCE_HTTPS", False) and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    uri = f"{base}/auth/callback"
    current_app.logger.info("OAuth redirect_uri (from request.host_url) = %s", uri)
    return uri

@bp.route("/login")
def login():
    cid = current_app.config.get("GOOGLE_CLIENT_ID")
    csec = current_app.config.get("GOOGLE_CLIENT_SECRET")
    if not cid or not csec:
        flash("Faltan credenciales de Google OAuth.", "danger")
        return redirect(url_for("main.index"))

    redirect_uri = _callback_url()
    current_app.logger.info("OAuth redirect_uri = %s", redirect_uri)

    state = _rand(); nonce = _rand()
    session["oauth_state"] = state
    session["oauth_nonce"] = nonce

    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
        "nonce": nonce,
    }
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")

@bp.route("/auth/callback")
def auth_callback():
    if request.args.get("state") != session.get("oauth_state"):
        session.pop("oauth_state", None); session.pop("oauth_nonce", None)
        flash("Estado de OAuth inválido.", "warning")
        return redirect(url_for("main.index"))

    code = request.args.get("code")
    if not code:
        session.pop("oauth_state", None); session.pop("oauth_nonce", None)
        flash("Falta el código de autenticación.", "warning")
        return redirect(url_for("main.index"))

    redirect_uri = _callback_url()

    data = {
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    tok = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=20)
    if tok.status_code != 200:
        current_app.logger.error("Fallo de token Google: %s", tok.text)
        session.pop("oauth_state", None); session.pop("oauth_nonce", None)
        flash("No se pudo intercambiar el token con Google.", "danger")
        return redirect(url_for("main.index"))

    tokens = tok.json()
    try:
        info = id_token.verify_oauth2_token(
            tokens["id_token"], grequests.Request(), current_app.config["GOOGLE_CLIENT_ID"]
        )
        if info.get("nonce") and info["nonce"] != session.get("oauth_nonce"):
            raise ValueError("Nonce inválido")
    except Exception:
        session.pop("oauth_state", None); session.pop("oauth_nonce", None)
        flash("ID token inválido.", "danger")
        return redirect(url_for("main.index"))

    email = info.get("email")
    if not email:
        session.pop("oauth_state", None); session.pop("oauth_nonce", None)
        flash("La cuenta de Google no tiene email verificado.", "danger")
        return redirect(url_for("main.index"))

    u = db.session.get(User, email) or User(email=email, created_at=datetime.utcnow())
    db.session.add(u)

    lvl1 = ensure_level1()
    if not u.membership_id:
        u.membership_id = lvl1.id

    u.given_name = info.get("given_name") or u.given_name
    u.family_name = info.get("family_name") or u.family_name
    u.full_name = info.get("name") or u.full_name
    u.picture = info.get("picture") or u.picture
    u.last_login_at = datetime.utcnow()
    db.session.commit()

    session["user_email"] = email
    session["user_name"] = u.full_name or email
    session["user_picture"] = u.picture
    session.pop("oauth_state", None); session.pop("oauth_nonce", None)

    return redirect(url_for("main.index"))

@bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.index"))
