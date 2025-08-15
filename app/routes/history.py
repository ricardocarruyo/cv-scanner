from flask import Blueprint, render_template, session, redirect, url_for, request, current_app, Response, flash, send_file, make_response, abort
from datetime import datetime
import math, csv, io

from ..extensions import db
from ..models import Execution, Comment
from ..services.pdf import render_analysis_pdf
from ..models import Execution, Comment, User

bp = Blueprint("history", __name__, url_prefix="/history")

def _require_login():
    if not session.get("user_email"):
        return False
    return True

def _is_admin():
    email = session.get("user_email")
    admin = current_app.config.get("ADMIN_EMAIL")
    return bool(admin and email and email.lower() == admin.lower())

@bp.route("/history")
def history():
    email = session.get("user_email")
    admin = (email and current_app.config.get("ADMIN_EMAIL") 
            and email.lower() == current_app.config["ADMIN_EMAIL"].lower())
    if not admin:
        abort(403)  # o: flash("Acceso solo para admin"); return redirect(url_for("main.index"))
    
    page_exec = int(request.args.get("page_exec", 1))
    page_cmt  = int(request.args.get("page_cmt", 1))
    per_page  = int(request.args.get("per_page", 20))

    exec_q = Execution.query.order_by(Execution.created_at.desc())
    cmt_q  = Comment.query.order_by(Comment.created_at.desc())

    executions = exec_q.limit(per_page).offset((page_exec-1)*per_page).all()
    total_exec = exec_q.count()
    pages_exec = max(1, (total_exec + per_page - 1)//per_page)

    comments = cmt_q.limit(per_page).offset((page_cmt-1)*per_page).all()
    total_cmt = cmt_q.count()
    pages_cmt = max(1, (total_cmt + per_page - 1)//per_page)

    return render_template(
        "history.html",
        is_admin=True,
        email=email,
        executions=executions,
        comments=comments,
        page_exec=page_exec, pages_exec=pages_exec,
        page_cmt=page_cmt,   pages_cmt=pages_cmt,
        per_page=per_page,
    )

@bp.route("/history/export")
def export_history():
    if not _require_login():
        return redirect(url_for("auth.login"))

    viewer = session["user_email"]
    is_admin = _is_admin()
    kind = (request.args.get("kind") or "executions").lower()

    si = io.StringIO()
    w = csv.writer(si)

    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if kind == "comments":
        q = Comment.query.order_by(Comment.created_at.desc())
        if not is_admin:
            q = q.filter(Comment.email == viewer)
        w.writerow(["created_at", "name", "email", "text"])
        for c in q.all():
            w.writerow([
                c.created_at.isoformat(),
                c.name or "",
                c.email or "",
                (c.text or "").replace("\n", " ")
            ])
        filename = f"comments_{'all' if is_admin else viewer}_{now}.csv"
    else:
        q = Execution.query.order_by(Execution.created_at.desc())
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

@bp.route("/download-pdf/<int:exec_id>")
def download_pdf(exec_id):
    if not _require_login():
        return redirect(url_for("auth.login"))

    viewer = session["user_email"]
    is_admin = _is_admin()

    ex = Execution.query.filter_by(id=exec_id).first()
    if not ex:
        flash("No se encontró el análisis.", "warning")
        return redirect(url_for("history.history"))
    if not is_admin and ex.email != viewer:
        flash("No tienes acceso a este análisis.", "danger")
        return redirect(url_for("history.history"))

    buffer = render_analysis_pdf(ex)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"analisis_{ex.id}.pdf",
        mimetype="application/pdf"
    )

@bp.route("/print/<int:exec_id>")
def print_view(exec_id):
    ex = db.session.get(Execution, exec_id)
    if not ex:
        abort(404)

    # Lo que guardaste cuando analizaste
    context = {
        "exec_id": ex.id,
        "created_at": ex.created_at,       # para fecha en el encabezado
        "email": ex.email,
        "filename": ex.uploaded_filename,
        "score_jd": ex.score,              # si guardas "score" como JD
        "score_ats": ex.ats_score,
        # feedback_text lo guardaste en texto plano markdown; en index lo sanitizas a HTML
        # aquí lo renderizamos igual que en index: pasa feedback_html desde index si lo prefieres.
        "feedback_html": ex.feedback_text, # en la plantilla lo marcarás |safe si ya está sanitizado
        # Para que aparezca el “Checklist ATS detectado”, te llega desde index como ats_details;
        # si lo quieres persistir, agrega una columna JSON en Execution. Si aún no, puedes no pintarlo.
        # Aquí asumo que lo pasas a la plantilla por el render desde index (ver paso 2).
    }
    return render_template("print_analysis.html", **context)