from flask import Blueprint, redirect, url_for, session, request, current_app, flash
from urllib.parse import urlencode
from datetime import datetime
import requests

from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"

def _rand(n=24):
    import secrets, string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

@bp.route("/login")
def login():
    client_id = current_app.config["GOOGLE_CLIENT_ID"]
    redirect_uri = f'{current_app.config["APP_BASE_URL"]}/auth/callback'

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
        "prompt": "select_account",
        "state": state,
        "nonce": nonce,
    }
    return redirect(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")

@bp.route("/auth/callback")
def auth_callback():
    if request.args.get("state") != session.get("oauth_state"):
        flash("Estado inválido de OAuth.", "warning")
        return redirect(url_for("main.index"))

    code = request.args.get("code")
    if not code:
        flash("Falta el código de autenticación.", "warning")
        return redirect(url_for("main.index"))

    data = {
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": f'{current_app.config["APP_BASE_URL"]}/auth/callback',
        "grant_type": "authorization_code",
    }
    tok = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=20)
    if tok.status_code != 200:
        flash("No se pudo intercambiar el token con Google.", "danger")
        return redirect(url_for("main.index"))

    tokens = tok.json()
    try:
        idinfo = id_token.verify_oauth2_token(
            tokens["id_token"],
            grequests.Request(),
            current_app.config["GOOGLE_CLIENT_ID"]
        )
        if idinfo.get("nonce") and idinfo["nonce"] != session.get("oauth_nonce"):
            flash("Nonce inválido.", "danger")
            return redirect(url_for("main.index"))
    except Exception:
        flash("ID token inválido.", "danger")
        return redirect(url_for("main.index"))

    email = idinfo.get("email")
    given = idinfo.get("given_name")
    family = idinfo.get("family_name")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    u = db.session.get(User, email)
    if not u:
        u = User(email=email, created_at=datetime.utcnow())
        db.session.add(u)
    u.given_name = given or u.given_name
    u.family_name = family or u.family_name
    u.full_name = name or u.full_name
    u.picture = picture or u.picture
    u.last_login_at = datetime.utcnow()
    db.session.commit()

    session["user_email"] = email
    session["user_name"] = name
    session["user_picture"] = picture

    return redirect(url_for("main.index"))

@bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.index"))
