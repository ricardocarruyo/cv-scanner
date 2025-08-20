from flask import ( 
    Blueprint, render_template, session, redirect, url_for, 
    current_app, flash, request, make_response
)
from ..extensions import db
from ..models import User, Execution, Comment, Membership

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

@bp.route("/memberships", methods=["GET", "POST"])
def memberships():
    if not _is_admin():
        return redirect(url_for("main.index"))

    if request.method == "POST":
        code  = (request.form.get("code") or "").strip().lower().replace(" ", "_")
        title = (request.form.get("title") or "").strip()
        max_execs = int(request.form.get("max_execs") or 10)
        is_active = bool(request.form.get("is_active"))

        if not code or not title:
            flash("Código y título son obligatorios.", "warning")
        else:
            m = Membership.query.filter_by(code=code).first()
            if m:
                m.title = title
                m.max_execs = max_execs
                m.is_active = is_active
                flash("Nivel actualizado.", "success")
            else:
                m = Membership(code=code, title=title, max_execs=max_execs, is_active=is_active)
                db.session.add(m)
                flash("Nivel creado.", "success")
            db.session.commit()
        return redirect(url_for("admin.memberships"))

    all_levels = Membership.query.order_by(Membership.id.asc()).all()
    return render_template("admin_memberships.html", levels=all_levels)

@bp.post("/memberships/<int:mid>/delete")
def memberships_delete(mid):
    if not _is_admin():
        return redirect(url_for("main.index"))
    m = db.session.get(Membership, mid)
    if not m:
        flash("Nivel no encontrado.", "warning")
        return redirect(url_for("admin.memberships"))
    db.session.delete(m)
    db.session.commit()
    flash("Nivel eliminado.", "success")
    return redirect(url_for("admin.memberships"))