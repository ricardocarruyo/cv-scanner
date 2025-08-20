from datetime import datetime
from .extensions import db


class Membership(db.Model):
    __tablename__ = "memberships"

    id         = db.Column(db.Integer, primary_key=True)
    code       = db.Column(db.String(50), unique=True, nullable=False)   # p.ej. "level_1"
    title      = db.Column(db.String(100), nullable=False)               # p.ej. "Nivel 1"
    max_execs  = db.Column(db.Integer, nullable=False, default=10)
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relación inversa
    users = db.relationship("User", back_populates="membership")

    def __repr__(self):
        return f"<Membership {self.code} max={self.max_execs}>"


class User(db.Model):
    __tablename__ = "users"

    # PK por email (como ya tenías)
    email         = db.Column(db.String(320), primary_key=True)
    given_name    = db.Column(db.String(120))
    family_name   = db.Column(db.String(120))
    full_name     = db.Column(db.String(300))
    picture       = db.Column(db.Text)
    occupation    = db.Column(db.String(200))
    created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    # último análisis
    last_model_vendor = db.Column(db.String(20))
    last_model_name   = db.Column(db.String(50))
    last_score        = db.Column(db.Integer)
    last_exec_id      = db.Column(db.Integer)
    last_analysis_at  = db.Column(db.DateTime)

    # --- Membresía y límites ---
    membership_id        = db.Column(db.Integer, db.ForeignKey("memberships.id"), nullable=True)
    exec_limit_override  = db.Column(db.Integer, nullable=True)   # permite sobrescribir el límite del nivel
    execs_used           = db.Column(db.Integer, nullable=False, default=0)  # contador (opcional)

    membership = db.relationship("Membership", back_populates="users")

    # relaciones con hijos
    executions = db.relationship("Execution", back_populates="user")
    comments   = db.relationship("Comment", back_populates="user")

    @property
    def exec_limit(self) -> int:
        """Límite efectivo de ejecuciones (override del usuario > nivel > fallback)."""
        if self.exec_limit_override is not None:
            return int(self.exec_limit_override)
        if self.membership and self.membership.max_execs is not None:
            return int(self.membership.max_execs)
        return 10  # fallback por defecto


class Execution(db.Model):
    __tablename__ = "executions"

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email            = db.Column(db.String(320), db.ForeignKey("users.email"))
    uploaded_filename= db.Column(db.Text)
    uploaded_ext     = db.Column(db.String(10))
    uploaded_size    = db.Column(db.Integer)
    resume_lang      = db.Column(db.String(5))
    jd_lang          = db.Column(db.String(5))
    model_vendor     = db.Column(db.String(20))
    model_name       = db.Column(db.String(50))
    score            = db.Column(db.Integer)
    feedback_text    = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ats_score        = db.Column(db.Integer, nullable=True)

    user = db.relationship("User", back_populates="executions")


class Comment(db.Model):
    __tablename__ = "comments"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email      = db.Column(db.String(320), db.ForeignKey("users.email"), nullable=True)
    name       = db.Column(db.String(300))
    text       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="comments")
