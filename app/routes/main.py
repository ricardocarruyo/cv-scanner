# app/routes/main.py
from flask import (
    Blueprint, render_template, request,
    session, redirect, url_for, flash, make_response,
    send_from_directory, current_app, jsonify
)
from datetime import datetime
from sqlalchemy import asc

from ..extensions import db
from ..models import User, Execution, Comment, Membership
from ..services.security import allowed_file, looks_suspicious
from ..services.files import extract_pdf, extract_docx
from ..services.ai import (
    analizar_openai, analizar_gemini, extraer_score,
    sanitize_markdown, detectar_idioma, disclaimer_text
)
from ..services.ats import evaluate_ats_compliance
from ..i18n import tr   # <-- i18n helper
import re

bp = Blueprint("main", __name__)
MAX_MB = 2

def _is_admin():
    email = session.get("user_email")
    admin = current_app.config.get("ADMIN_EMAIL")
    return bool(admin and email and email.lower() == admin.lower())

@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        current_app.static_folder,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )


@bp.route("/descargas/plantilla-ats")
def descargar_plantilla_ats():
    # Descarga la plantilla en el idioma elegido
    lang = (session.get("lang") or "es").lower()
    if lang == "en":
        relpath = "docs/ATS_CV_Template_English.docx"
        dlname  = "ATS_CV_Template_English.docx"
    else:
        relpath = "docs/Plantilla_CV_ATS_STAR.docx"
        dlname  = "Plantilla_CV_ATS_STAR.docx"

    return send_from_directory(
        current_app.static_folder,
        relpath,
        as_attachment=True,
        download_name=dlname
    )


@bp.route("/", methods=["GET", "POST"])
def index():
    # idioma de la UI
    lang = (session.get("lang") or "es").lower()
    is_en = (lang == "en")
    # helper para usar en Jinja: t('clave', **kwargs)
    T = lambda key, **kw: tr(lang, key, **kw)

    email = session.get("user_email")
    name = session.get("user_name")
    picture = session.get("user_picture")

    if request.method == "POST":
        try:
            if not email:
                flash(T("err.login"))
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
                flash(T("err.no_file"))
                return redirect(url_for("main.index"))

            if not jobdesc:
                flash(T("err.no_jd"))
                return redirect(url_for("main.index"))

            if not allowed_file(filename):
                flash(T("err.bad_ext"))
                return redirect(url_for("main.index"))

            data = file.read() or b""
            if not data:
                flash(T("err.empty"))
                return redirect(url_for("main.index"))

            if len(data) > MAX_MB * 1024 * 1024:
                flash(T("err.too_big", max_mb=MAX_MB))
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
                flash(T("err.malicious"))
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

            # modelo elegido por admin (por defecto: auto)
            selected_model = session.get("selected_model", "auto")
            if selected_model not in ("auto", "openai", "gemini"):
                selected_model = "auto"

            if selected_model == "gemini":
                fb_gemini = analizar_gemini(cv_text, jobdesc, nombre=None)
                if fb_gemini:
                    feedback_text = fb_gemini
                    model_vendor  = "gemini"
                    model_name    = "gemini-1.5-flash"
                    model_used    = 2

            elif selected_model == "openai":
                fb_openai, oi_error = analizar_openai(cv_text, jobdesc, nombre=None)
                if fb_openai:
                    feedback_text = fb_openai
                    model_vendor  = "openai"
                    model_name    = "gpt-4o"
                    model_used    = 1

            else:  # auto
                fb_openai, oi_error = analizar_openai(cv_text, jobdesc, nombre=None)
                if fb_openai:
                    feedback_text = fb_openai
                    model_vendor  = "openai"
                    model_name    = "gpt-4o"
                    model_used    = 1
                else:
                    fb_gemini = analizar_gemini(cv_text, jobdesc, nombre=None)
                    if fb_gemini:
                        feedback_text = fb_gemini
                        model_vendor  = "gemini"
                        model_name    = "gemini-1.5-flash"
                        model_used    = 2

            if not feedback_text:
                current_app.logger.error(
                    "No se pudo generar feedback con el modelo '%s'. vendor=openai err=%s cv_len=%s jd_len=%s",
                    selected_model, oi_error, len(cv_text or ""), len(jobdesc or "")
                )
                flash(T("err.analysis"))
                return redirect(url_for("main.index"))

            # Extraer score JD y limpiar encabezado numérico si viene como "NN%"
            score_jd = extraer_score(feedback_text) if feedback_text else None
            if feedback_text:
                lines = feedback_text.splitlines()
                if lines:
                    first = lines[0].strip()
                    if re.fullmatch(r"\d{1,3}\s*%", first):
                        lines = lines[1:]
                    elif re.match(r"^(Analysis for|Análisis (para|de))\b", first, re.IGNORECASE):
                        lines = lines[1:]
                feedback_text = "\n".join(lines).lstrip()

            feedback_html = sanitize_markdown(feedback_text) if feedback_text else None

            # Disclaimer según idioma (se pinta en plantilla)
            idioma_detectado = detectar_idioma(cv_text + " " + jobdesc)
            disclaimer = disclaimer_text(idioma_detectado)

            def _default_membership():
                return Membership.query.filter_by(code="level_1").first()   

            # Persistencia
            u = db.session.get(User, email)
            if not u:
                u = User(email=email)
                db.session.add(u)
            # asigna nivel 1 por defecto si existe
            m = _default_membership()
            if m:
                u.membership = m
                db.session.add(u)

            if name: u.full_name = name
            if picture: u.picture = picture
            if occ: u.occupation = occ
            db.session.commit()

            # 0) Asegura que el usuario existe/trae su nivel
            u = db.session.get(User, email)
            if not u:
                u = User(email=email)
                # asigna nivel por defecto si existe                
                m = Membership.query.filter_by(code="level_1").first()
                if m:
                    u.membership = m
                db.session.add(u)
                db.session.commit()

            # 1) Calcula usados y límite
            # Opción A: usar columna cacheada
            # used = u.execs_used or 0

            # Opción B (si prefieres calcular en vivo):
            # from ..models import Execution
            used = db.session.query(Execution).filter(Execution.email == email).count()

            limit = u.exec_limit

            if used >= limit:
                # Guardamos datos para el modal en sesión
                session["limit_modal"] = {
                    "limit": limit,
                    "lang": session.get("lang", "es")
                }
                return redirect(url_for("main.index"))
            
            limit_modal_data = session.pop("limit_modal", None)

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

            # incrementa usado (si usas execs_used)
            u.execs_used = (u.execs_used or 0) + 1
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
                # i18n helpers
                t=T, is_en=is_en, lang=lang,
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
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
            resp.headers["Pragma"] = "no-cache"
            return resp

        except Exception:
            current_app.logger.exception("Error durante el análisis")
            flash(tr(lang, "err.generic"))
            return redirect(url_for("main.index"))
        
    # GET
    return render_template(
        "index.html",
        # i18n helpers
        t=T, is_en=is_en, lang=lang,

        email=email, name=name, picture=picture,
        feedback=None,
        score_jd=None, score_ats=None,
        ats_details=None,
        model_used=None, exec_id=None,
        max_mb=MAX_MB, jobdesc=None,
        just_analyzed=False,
        is_admin=_is_admin(),
        show_limit_modal=bool(limit_modal_data),
        limit_for_modal=(limit_modal_data or {}).get("limit")
    )


@bp.route('/feedback', methods=['POST'])
def leave_comment():
    lang = (session.get("lang") or "es").lower()
    T = lambda key, **kw: tr(lang, key, **kw)

    if not session.get("user_email"):
        flash(T("err.login"))
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


@bp.route("/set_model", methods=["POST"])
def set_model():
    if not _is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    model = (data.get("model") or "auto").lower()
    if model not in ["auto", "openai", "gemini"]:
        model = "auto"

    session["selected_model"] = model
    return jsonify({"model": model})


# --- Selector de idiomas ---
@bp.route("/set_lang", methods=["POST"])
def set_lang():
    data = request.get_json(silent=True) or {}
    lang = (data.get("lang") or "es").lower()
    if lang not in ("es", "en"):
        lang = "es"
    session["lang"] = lang
    return jsonify({"lang": lang})