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
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _callback_url() -> str:
    """
    Devuelve la redirect_uri exacta que usaremos tanto en /login como en /auth/callback.
    - Si GOOGLE_REDIRECT_URI está definido en config/.env, se usa tal cual.
    - Si no, se construye con url_for(_external=True) y esquema de PREFERRED_URL_SCHEME.
    Esto evita mismatches entre local y producción.
    """
    explicit = current_app.config.get("GOOGLE_REDIRECT_URI")
    if explicit:
        return explicit

    scheme = current_app.config.get("PREFERRED_URL_SCHEME", "http")
    # El endpoint de callback es auth_callback (ruta /auth/callback)
    return url_for("auth.auth_callback", _external=True, _scheme=scheme)


@bp.route("/login")
def login():
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        flash("Faltan credenciales de Google OAuth. Revisa configuración.", "danger")
        return redirect(url_for("main.index"))

    redirect_uri = _callback_url()

    state = _rand()
    nonce = _rand()
    session["oauth_state"] = state
    session["oauth_nonce"] = nonce

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",  # en dev puedes usar "consent" para forzar
        "state": state,
        "nonce": nonce,
    }
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


@bp.route("/auth/callback")
def auth_callback():
    # 1) validar state
    sent_state = request.args.get("state")
    if not sent_state or sent_state != session.get("oauth_state"):
        # limpia por si acaso
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        flash("Estado de OAuth inválido. Intenta nuevamente.", "warning")
        return redirect(url_for("main.index"))

    code = request.args.get("code")
    if not code:
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        flash("Faltó el código de autenticación de Google.", "warning")
        return redirect(url_for("main.index"))

    redirect_uri = _callback_url()

    # 2) Intercambio de code por tokens
    data = {
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        tok = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=20)
    except Exception as e:
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        current_app.logger.exception("Error llamando a token endpoint de Google")
        flash("No se pudo contactar a Google para el login.", "danger")
        return redirect(url_for("main.index"))

    if tok.status_code != 200:
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        current_app.logger.error("Fallo de token Google: %s", tok.text)
        flash("No se pudo intercambiar el token con Google.", "danger")
        return redirect(url_for("main.index"))

    tokens = tok.json()

    # 3) Verificar ID Token (firma + audiencia + nonce)
    try:
        idinfo = id_token.verify_oauth2_token(
            tokens["id_token"],
            grequests.Request(),
            current_app.config["GOOGLE_CLIENT_ID"],
        )
        if idinfo.get("nonce") and idinfo["nonce"] != session.get("oauth_nonce"):
            session.pop("oauth_state", None)
            session.pop("oauth_nonce", None)
            flash("Nonce inválido.", "danger")
            return redirect(url_for("main.index"))
    except Exception:
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        flash("ID token inválido.", "danger")
        return redirect(url_for("main.index"))

    # 4) Extraer datos del usuario
    email = idinfo.get("email")
    given = idinfo.get("given_name")
    family = idinfo.get("family_name")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    if not email:
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        flash("La cuenta de Google no tiene email verificado.", "danger")
        return redirect(url_for("main.index"))

    # 5) Crear/actualizar usuario
    u = db.session.get(User, email)
    if not u:
        u = User(email=email, created_at=datetime.utcnow())
        db.session.add(u)
    
    # Garantiza que exista LEVEL_1
    lvl1 = ensure_level1()

    # Si el usuario no tiene nivel, asígnale LEVEL_1
    if not u.membership_id:
        u.membership_id = lvl1.id

    u.given_name = given or u.given_name
    u.family_name = family or u.family_name
    u.full_name = name or u.full_name
    u.picture = picture or u.picture
    u.last_login_at = datetime.utcnow()
    db.session.commit()

    # 6) Guardar sesión app
    session["user_email"] = email
    session["user_name"] = name
    session["user_picture"] = picture

    # limpiar secretos de OAuth
    session.pop("oauth_state", None)
    session.pop("oauth_nonce", None)

    return redirect(url_for("main.index"))


@bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.index"))
