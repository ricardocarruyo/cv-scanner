# app/routes/admin.py
from flask import (Blueprint, render_template, session, redirect, url_for,
                   current_app, flash, request)
from ..extensions import db
from ..models import User, Execution, Comment, Membership

bp = Blueprint("admin", __name__, url_prefix="/admin")  # 👈 prefijo /admin

def _is_admin():
    email = session.get("user_email")
    admin = current_app.config.get("ADMIN_EMAIL")
    return bool(admin and email and email.lower() == admin.lower())

@bp.before_request
def require_admin():
    if not _is_admin():
        flash("Acceso solo para admin.", "danger")
        return redirect(url_for("main.index"))

def ensure_level1():
    """Crea LEVEL_1 si no existe y lo devuelve."""
    m = Membership.query.filter_by(code="LEVEL_1").first()
    if not m:
        m = Membership(code="LEVEL_1", title="Nivel 1", max_execs=10, is_active=True)
        db.session.add(m)
        db.session.commit()
    return m

# ---------- helpers opcionales ----------
def seed_default_memberships():
    """Crea niveles básicos si la tabla está vacía."""
    if Membership.query.count() == 0:
        db.session.add_all([
            Membership(code="LEVEL_1", title="Nivel 1", max_execs=10,  is_active=True),
            Membership(code="LEVEL_2", title="Nivel 2", max_execs=50,  is_active=True),
            Membership(code="LEVEL_3", title="Nivel 3", max_execs=100, is_active=True),
        ])
        db.session.commit()

# ---------- panel ----------
@bp.route("/")
def panel():
    seed_default_memberships()  # crea niveles por defecto si no existen
    users_count = User.query.count()
    execs_count = Execution.query.count()
    comments_count = Comment.query.count()
    levels = Membership.query.order_by(Membership.id.asc()).all()
    return render_template("admin/panel.html",
                           users_count=users_count,
                           execs_count=execs_count,
                           comments_count=comments_count,
                           levels=levels)

# ---------- comentarios ----------
@bp.route("/clear-comments", methods=["POST"])
def clear_comments():
    db.session.query(Comment).delete()
    db.session.commit()
    flash("Se borraron todos los comentarios.", "success")
    return redirect(url_for("admin.panel"))

# ---------- membresías ----------
@bp.route("/memberships")
def memberships_list():
    items = Membership.query.order_by(Membership.id.asc()).all()
    return render_template("admin/memberships.html", items=items)

@bp.route("/memberships/new", methods=["GET","POST"])
def memberships_new():
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        title = (request.form.get("title") or "").strip()
        max_execs = int(request.form.get("max_execs") or 10)
        is_active = bool(request.form.get("is_active"))
        if not code or not title:
            flash("Code y Title son requeridos.", "warning")
            return redirect(url_for("admin.memberships_new"))
        db.session.add(Membership(code=code, title=title, max_execs=max_execs, is_active=is_active))
        db.session.commit()
        flash("Membresía creada.", "success")
        return redirect(url_for("admin.memberships_list"))
    return render_template("admin/membership_form.html", item=None)

@bp.route("/memberships/<int:mid>/edit", methods=["GET","POST"])
def memberships_edit(mid):
    m = Membership.query.get_or_404(mid)
    if request.method == "POST":
        m.code = (request.form.get("code") or m.code).strip()
        m.title = (request.form.get("title") or m.title).strip()
        m.max_execs = int(request.form.get("max_execs") or m.max_execs or 10)
        m.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Membresía actualizada.", "success")
        return redirect(url_for("admin.memberships_list"))
    return render_template("admin/membership_form.html", item=m)

# ---------- usuarios ----------
@bp.route("/users")
def users_list():
    users = (User.query
                .order_by(User.created_at.desc())
                .all())
    # calcula uso y límite (si no llevas el cache execs_used)
    rows = []
    for u in users:
        used = Execution.query.filter_by(email=u.email).count()
        limit = u.exec_limit  # property de tu modelo User
        rows.append((u, used, limit, max(0, (limit or 0) - used)))
    levels = Membership.query.order_by(Membership.id.asc()).all()
    return render_template("admin/users.html", rows=rows, levels=levels)

@bp.route("/users/<email>")
def user_detail(email):
    u = User.query.get_or_404(email)
    used = Execution.query.filter_by(email=email).count()
    levels = Membership.query.order_by(Membership.id.asc()).all()
    return render_template("admin/user_detail.html", user=u, used=used, levels=levels)

@bp.route("/users/<email>/set_membership", methods=["POST"])
def set_user_membership(email):
    u = User.query.get_or_404(email)
    u.membership_id = int(request.form.get("membership_id")) if request.form.get("membership_id") else None
    u.exec_limit_override = int(request.form.get("exec_limit_override")) if request.form.get("exec_limit_override") else None
    db.session.commit()
    flash("Usuario actualizado.", "success")
    return redirect(url_for("admin.user_detail", email=email))
