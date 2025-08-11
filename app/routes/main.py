from flask import Blueprint, render_template, request, session, redirect, url_for, flash, make_response
from ..extensions import db
from ..models import User, Execution
from ..services.security import allowed_file, looks_suspicious
from ..services.files import extract_pdf, extract_docx
from ..services.ai import analizar_openai, analizar_gemini, extraer_score, sanitize_markdown, detectar_idioma
import markdown
from ..models import User, Execution, Comment   # <-- agrega Comment
from sqlalchemy import asc                      # <-- agrega asc
from datetime import datetime                   # <-- para timestamps
from flask import send_from_directory, current_app


bp = Blueprint("main", __name__)

MAX_MB = 10

@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        current_app.static_folder,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )

@bp.route("/", methods=["GET", "POST"])
def index():
    email = session.get("user_email")
    name = session.get("user_name")
    picture = session.get("user_picture")

    if request.method == "POST":
        if not email:
            flash("Inicia sesión para analizar tu CV.")
            return redirect(url_for("auth.login"))

        file = request.files.get("cv")
        jobdesc = request.form.get("jobdesc", "")
        occ = (request.form.get("occupation") or "").strip()[:200]

        if not file or not jobdesc:
            flash("Faltan el archivo y/o la descripción del puesto.")
            return redirect(url_for("main.index"))

        filename = file.filename or ""
        if not allowed_file(filename):
            flash("Formato no permitido. Solo PDF o DOCX.")
            return redirect(url_for("main.index"))

        data = file.read()
        if len(data) > MAX_MB * 1024 * 1024:
            flash("El archivo supera 10 MB.")
            return redirect(url_for("main.index"))

        ext = filename.rsplit(".", 1)[1].lower()
        try:
            cv_text = extract_pdf(data) if ext == "pdf" else extract_docx(data)
        except Exception:
            flash("No se pudo leer el archivo.")
            return redirect(url_for("main.index"))

        if looks_suspicious(cv_text[:100000]):
            flash("Detectamos contenido potencialmente peligroso en el archivo.")
            return redirect(url_for("main.index"))

        # LLMs
        feedback_text, oi_error = analizar_openai(cv_text, jobdesc)
        if feedback_text:
            model_vendor, model_name, model_used = "openai", "gpt-4o", 1
        else:
            fb = analizar_gemini(cv_text, jobdesc)
            feedback_text = fb
            model_vendor, model_name, model_used = ("gemini", "gemini-1.5-flash", 2) if fb else (None, None, None)

        feedback_html = sanitize_markdown(feedback_text) if feedback_text else None
        score = extraer_score(feedback_text) if feedback_text else None

        # Persistencia
        u = db.session.get(User, email)
        if not u:
            u = User(email=email)
            db.session.add(u)
        if name: u.full_name = name
        if picture: u.picture = picture
        if occ: u.occupation = occ
        db.session.commit()

        res_lang = detectar_idioma(cv_text)
        jd_lang = detectar_idioma(jobdesc)

        ex = Execution(
            email=email,
            uploaded_filename=filename,
            uploaded_ext=ext,
            uploaded_size=len(data),
            resume_lang=res_lang,
            jd_lang=jd_lang,
            model_vendor=model_vendor,
            model_name=model_name,
            score=score,
            feedback_text=feedback_text
        )
        db.session.add(ex); db.session.commit()

        # último análisis en users
        u.last_model_vendor = model_vendor
        u.last_model_name = model_name
        u.last_score = score
        u.last_exec_id = ex.id
        u.last_analysis_at = ex.created_at
        db.session.commit()

        resp = make_response(render_template(
            "index.html",
            email=email, name=name, picture=picture,
            feedback=feedback_html, model_used=model_used, score=score,
            exec_id=ex.id, is_admin=False  # se calcula en base al ADMIN_EMAIL en el template/base
        ))
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    return render_template(
        "index.html",
        email=email, name=name, picture=picture,
        feedback=None,
        score=None,
        model_used=None,
        exec_id=None,
        occupation=None,
        max_mb=10
    )

@bp.route('/feedback', methods=['POST'])
def leave_comment():
    # exigir login
    if not session.get("user_email"):
        flash("Inicia sesión para enviar sugerencias.")
        return redirect(url_for("auth.login"))

    text = (request.form.get('comment') or "").strip()
    if not text:
        return redirect(url_for('main.index'))

    email = session.get("user_email")
    name  = session.get("user_name")

    # límite rodante: máximo 5 por usuario
    count = db.session.query(Comment).filter(Comment.email == email).count()
    if count >= 5:
        oldest = (
            db.session.query(Comment)
            .filter(Comment.email == email)
            .order_by(asc(Comment.created_at))
            .first()
        )
        if oldest:
            db.session.delete(oldest)

    c = Comment(
        email=email,
        name=name if name else None,
        text=text[:2000],
        created_at=datetime.utcnow()
    )
    db.session.add(c)
    db.session.commit()

    return redirect(url_for('main.index'))
