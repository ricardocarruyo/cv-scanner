from flask import Blueprint, render_template, session, redirect, url_for, request, current_app, Response, flash, send_file, make_response
from datetime import datetime
import math, csv, io

from ..extensions import db
from ..models import Execution, Comment
from ..services.pdf import render_analysis_pdf

bp = Blueprint("history", __name__)

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
    if not _require_login():
        return redirect(url_for("auth.login"))

    viewer = session["user_email"]
    is_admin = _is_admin()

    per_page = max(5, min(50, int(request.args.get("per_page", 10))))
    page_exec = max(1, int(request.args.get("page_exec", 1)))
    page_cmt = max(1, int(request.args.get("page_cmt", 1)))

    q_exec = Execution.query.order_by(Execution.created_at.desc())
    q_cmt = Comment.query.order_by(Comment.created_at.desc())

    if not is_admin:
        q_exec = q_exec.filter(Execution.email == viewer)
        q_cmt = q_cmt.filter(Comment.email == viewer)

    total_exec = q_exec.count()
    total_cmt = q_cmt.count()

    executions = q_exec.offset((page_exec - 1) * per_page).limit(per_page).all()
    comments = q_cmt.offset((page_cmt - 1) * per_page).limit(per_page).all()

    pages_exec = max(1, math.ceil(total_exec / per_page)) if total_exec else 1
    pages_cmt = max(1, math.ceil(total_cmt / per_page)) if total_cmt else 1

    html = render_template(
        "history.html",
        email=viewer,
        is_admin=is_admin,
        executions=executions,
        comments=comments,
        page_exec=page_exec,
        page_cmt=page_cmt,
        pages_exec=pages_exec,
        pages_cmt=pages_cmt,
        per_page=per_page,
    )
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

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
