from flask import Blueprint, render_template, session, redirect, url_for, current_app, flash, request, make_response
from ..extensions import db
from ..models import User, Execution, Comment

bp = Blueprint("admin", __name__)

def _require_login():
    return bool(session.get("user_email"))

def _is_admin():
    email = session.get("user_email")
    admin = current_app.config.get("ADMIN_EMAIL")
    return bool(admin and email and email.lower() == admin.lower())

@bp.route("/admin")
def panel():
    if not _require_login():
        return redirect(url_for("auth.login"))
    if not _is_admin():
        flash("No tienes permisos de administrador.", "warning")
        return redirect(url_for("main.index"))

    users_count = User.query.count()
    execs_count = Execution.query.count()
    comments_count = Comment.query.count()
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(20).all()

    html = render_template(
        "admin.html",
        users_count=users_count,
        execs_count=execs_count,
        comments_count=comments_count,
        recent_comments=recent_comments
    )
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

@bp.route("/admin/clear-comments", methods=["POST"])
def clear_comments():
    if not _require_login():
        return redirect(url_for("auth.login"))
    if not _is_admin():
        flash("No tienes permisos de administrador.", "warning")
        return redirect(url_for("main.index"))

    db.session.query(Comment).delete()
    db.session.commit()
    flash("Se borraron todos los comentarios.", "success")
    return redirect(url_for("admin.panel"))
