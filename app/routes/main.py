from flask import (
    Blueprint, render_template, request, 
    session, redirect, url_for, flash, make_response, 
    send_from_directory, current_app, jsonify
)
from datetime import datetime
from sqlalchemy import asc

from ..extensions import db
from ..models import User, Execution, Comment
from ..services.security import allowed_file, looks_suspicious
from ..services.files import extract_pdf, extract_docx
from ..services.ai import (
    analizar_openai, analizar_gemini, extraer_score,
    sanitize_markdown, detectar_idioma, disclaimer_text
)
from ..services.ats import evaluate_ats_compliance

bp = Blueprint("main", __name__)
MAX_MB = 2


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        current_app.static_folder,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )


@bp.route("/descargas/plantilla-ats")
def descargar_plantilla_ats():
    return send_from_directory(
        current_app.static_folder,
        "docs/Plantilla_CV_ATS_STAR.docx",
        as_attachment=True,
        download_name="Plantilla_CV_ATS_STAR.docx"
    )


@bp.route("/", methods=["GET", "POST"])
def index():
    email = session.get("user_email")
    name = session.get("user_name")
    picture = session.get("user_picture")

    if request.method == "POST":
        try:
            if not email:
                flash("Inicia sesión para analizar tu CV.")
                return redirect(url_for("auth.login"))

            file = request.files.get("cv")
            jobdesc = (request.form.get("jobdesc") or "").strip()
            occ = (request.form.get("occupation") or "").strip()[:200]

            # Nombre de archivo
            filename = ""
            if file and getattr(file, "filename", None):
                filename = (file.filename or "").strip()

            # Validaciones
            if not filename:
                flash("No se recibió ningún archivo. Selecciona un PDF o DOCX.")
                return redirect(url_for("main.index"))

            if not jobdesc:
                flash("Falta la descripción del puesto.")
                return redirect(url_for("main.index"))

            if not allowed_file(filename):
                flash("Formato no permitido. Solo PDF o DOCX.")
                return redirect(url_for("main.index"))

            data = file.read() or b""
            if not data:
                flash("El archivo está vacío o no se pudo leer.")
                return redirect(url_for("main.index"))

            if len(data) > MAX_MB * 1024 * 1024:
                flash(f"El archivo supera {MAX_MB} MB.")
                return redirect(url_for("main.index"))

            # Extensión segura
            ext = filename.rsplit(".", 1)[-1].lower()

            # Extraer texto y metadatos (incluye fuentes normalizadas en meta["fonts"])
            if ext == "pdf":
                cv_text, pdf_meta = extract_pdf(data)   # -> (texto, {"pages","images","fonts"})
                docx_meta = None
            else:  # docx
                cv_text, docx_meta = extract_docx(data) # -> (texto, {"tables","images","fonts"})
                pdf_meta = None

            cv_text = cv_text or ""

            if looks_suspicious(cv_text[:100000]):
                flash("Detectamos contenido potencialmente peligroso en el archivo.")
                return redirect(url_for("main.index"))

            # Idioma del CV
            res_lang = detectar_idioma(cv_text)  # 'en' / 'es'

            # Fuentes para ATS (PDF o DOCX)
            doc_fonts = None
            if pdf_meta and isinstance(pdf_meta.get("fonts"), list):
                doc_fonts = pdf_meta["fonts"]
            elif docx_meta and isinstance(docx_meta.get("fonts"), list):
                doc_fonts = docx_meta["fonts"]

            # ATS score (estructura/lineamientos + tipografía)
            score_ats, ats_details = evaluate_ats_compliance(
                text=cv_text,
                lang_code=res_lang,
                ext=ext,
                pdf_meta=pdf_meta,
                docx_meta=docx_meta,
                docx_fonts=doc_fonts
            )

            # ========= LLMs =========
            model_vendor = None
            model_name   = None
            model_used   = None
            feedback_text = None
            oi_error = None

            nombre_persona = name or email

            # lee el modelo elegido por el admin (por defecto: openai)
            selected_model = session.get("selected_model", "auto")

            if selected_model == "gemini":
                fb_gemini = analizar_gemini(cv_text, jobdesc, nombre=nombre_persona)
                if fb_gemini:
                    feedback_text = fb_gemini
                    model_vendor  = "gemini"
                    model_name    = "gemini-1.5-flash"
                    model_used    = 2

            elif selected_model == "openai":
                fb_openai, oi_error = analizar_openai(cv_text, jobdesc, nombre=nombre_persona)
                if fb_openai:
                    feedback_text = fb_openai
                    model_vendor  = "openai"
                    model_name    = "gpt-4o"
                    model_used    = 1

            else:  # auto
                fb_openai, oi_error = analizar_openai(cv_text, jobdesc, nombre=nombre_persona)
                if fb_openai:
                    feedback_text = fb_openai
                    model_vendor  = "openai"
                    model_name    = "gpt-4o"
                    model_used    = 1
                else:
                    fb_gemini = analizar_gemini(cv_text, jobdesc, nombre=nombre_persona)
                    if fb_gemini:
                        feedback_text = fb_gemini
                        model_vendor  = "gemini"
                        model_name    = "gemini-1.5-flash"
                        model_used    = 2

            # si el modelo elegido no devolvió nada, mostramos error
            if not feedback_text:
                current_app.logger.error(
                    "No se pudo generar feedback con el modelo '%s'. err=%s",
                    selected_model, oi_error
                )
                flash("No pudimos generar el análisis en este momento. Intenta nuevamente.", "danger")
                return redirect(url_for("main.index"))

            # Extraer score JD y limpiar encabezado numérico si viene como "NN%"
            score_jd = extraer_score(feedback_text) if feedback_text else None
            if feedback_text:
                lines = feedback_text.splitlines()
                if lines:
                    import re
                    first = lines[0].strip()
                    if re.fullmatch(r"\d{1,3}\s*%", first):
                        feedback_text = "\n".join(lines[1:]).lstrip()

            feedback_html = sanitize_markdown(feedback_text) if feedback_text else None

            # Disclaimer según idioma (se pinta en plantilla)
            idioma_detectado = detectar_idioma(cv_text + " " + jobdesc)
            disclaimer = disclaimer_text(idioma_detectado)

            # Persistencia
            u = db.session.get(User, email)
            if not u:
                u = User(email=email)
                db.session.add(u)
            if name: u.full_name = name
            if picture: u.picture = picture
            if occ: u.occupation = occ
            db.session.commit()

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
                score=score_jd,
                feedback_text=feedback_text,
                ats_score=score_ats
            )
            db.session.add(ex)
            db.session.commit()

            # último análisis en users
            u.last_model_vendor = model_vendor
            u.last_model_name = model_name
            u.last_score = score_jd
            u.last_exec_id = ex.id
            u.last_analysis_at = ex.created_at
            db.session.commit()

            resp = make_response(render_template(
                "index.html",
                email=email, name=name, picture=picture,
                feedback=feedback_html,
                disclaimer=disclaimer,
                score_jd=score_jd,
                score_ats=score_ats,
                ats_details=ats_details,
                model_used=model_used,
                exec_id=ex.id,
                max_mb=MAX_MB,
                jobdesc=jobdesc,
                just_analyzed=True,
                is_admin=_is_admin()
            ))
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp

        except Exception:
            current_app.logger.exception("Error durante el análisis")
            flash("Ocurrió un error al procesar el análisis. Inténtalo nuevamente.", "danger")
            return redirect(url_for("main.index"))

    # GET
    return render_template(
        "index.html",
        email=email, name=name, picture=picture,
        feedback=None,
        score_jd=None, score_ats=None,
        ats_details=None,
        model_used=None, exec_id=None,
        max_mb=MAX_MB, jobdesc=None,
        just_analyzed=False,
        is_admin=_is_admin()
    )


@bp.route('/feedback', methods=['POST'])
def leave_comment():
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


def _is_admin():
    email = session.get("user_email")
    admin = current_app.config.get("ADMIN_EMAIL")
    return bool(admin and email and email.lower() == admin.lower())


@bp.route("/set_model", methods=["POST"])
def set_model():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json() or {}
    model = data.get("model", "openai")
    if model not in ["openai", "gemini"]:
        model = "openai"
    
    session["selected_model"] = model
    return jsonify({"model": model})


