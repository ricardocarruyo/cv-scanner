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


def _base_url() -> str:
    """
    Devuelve la base URL a usar para construir redirect_uri.
    Prioriza APP_BASE_URL (prod), si no existe deriva de request.host_url.
    Limpia el slash final y puede forzar https si FORCE_HTTPS=true.
    """
    base = (current_app.config.get("APP_BASE_URL") or request.host_url).strip()
    base = base.rstrip("/")  # sin slash final

    # Fuerza https en prod (opcional, por config)
    if current_app.config.get("FORCE_HTTPS", False):
        if base.startswith("http://"):
            base = "https://" + base[len("http://"):]
    return base


def _callback_url() -> str:
    """
    Redirect URI única y consistente para /login y /auth/callback.

    Prioridad:
    1) GOOGLE_REDIRECT_URI (o alias OAUTH_REDIRECT_URI) si están definidos en config/.env
    2) APP_BASE_URL + '/auth/callback'
    3) request.host_url + '/auth/callback'
    """
    # 1) variables explícitas (recomendado)
    explicit = (
        current_app.config.get("GOOGLE_REDIRECT_URI")
        or current_app.config.get("OAUTH_REDIRECT_URI")
    )
    if explicit:
        return explicit.rstrip("/")

    # 2) base de app (producción normalmente)
    base = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    if base:
        return f"{base}/auth/callback"

    # 3) fallback: lo que estás usando en local
    base = (request.host_url or "").strip().rstrip("/")
    return f"{base}/auth/callback"


@bp.route("/login")
def login():
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        flash("Faltan credenciales de Google OAuth. Revisa configuración.", "danger")
        return redirect(url_for("main.index"))

    redirect_uri = _callback_url()
    # current_app.logger.info("OAuth redirect_uri = %s", redirect_uri)


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
        "prompt": "select_account",  # en dev puedes usar "consent"
        "state": state,
        "nonce": nonce,
    }
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


@bp.route("/auth/callback")
def auth_callback():
    # 1) validar state
    sent_state = request.args.get("state")
    if not sent_state or sent_state != session.get("oauth_state"):
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
    # current_app.logger.info("OAuth redirect_uri = %s", redirect_uri)

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
    except Exception:
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

    # Normaliza URL del avatar para evitar mixed content o URLs sin esquema
    def _normalize_pic(url: str | None) -> str | None:
        if not url:
            return None
        url = url.strip()
        if url.startswith("//"):           # esquema omitido
            url = "https:" + url
        if url.startswith("http://"):      # fuerza https en prod
            url = "https://" + url[len("http://"):]
        return url

    picture = _normalize_pic(picture)

    if not email:
        session.pop("oauth_state", None)
        session.pop("oauth_nonce", None)
        flash("La cuenta de Google no tiene email verificado.", "danger")
        return redirect(url_for("main.index"))

    # 5) Crear/actualizar usuario + membresía por defecto
    u = db.session.get(User, email)
    if not u:
        u = User(email=email, created_at=datetime.utcnow())
        db.session.add(u)

    lvl1 = ensure_level1()  # crea LEVEL_1 si no existe
    if not u.membership_id:
        u.membership_id = lvl1.id

    u.given_name = given or u.given_name
    u.family_name = family or u.family_name
    u.full_name = name or u.full_name
    u.picture = picture or u.picture
    u.last_login_at = datetime.utcnow()
    db.session.commit()

    # 6) Sesión
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
