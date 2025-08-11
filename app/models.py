from datetime import datetime
from .extensions import db

class User(db.Model):
    __tablename__ = "users"
    email = db.Column(db.String(320), primary_key=True)
    given_name = db.Column(db.String(120))
    family_name = db.Column(db.String(120))
    full_name = db.Column(db.String(300))
    picture = db.Column(db.Text)
    occupation = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    # último análisis
    last_model_vendor = db.Column(db.String(20))
    last_model_name = db.Column(db.String(50))
    last_score = db.Column(db.Integer)
    last_exec_id = db.Column(db.Integer)
    last_analysis_at = db.Column(db.DateTime)

    executions = db.relationship("Execution", back_populates="user")
    comments = db.relationship("Comment", back_populates="user")

class Execution(db.Model):
    __tablename__ = "executions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(320), db.ForeignKey("users.email"))
    uploaded_filename = db.Column(db.Text)
    uploaded_ext = db.Column(db.String(10))
    uploaded_size = db.Column(db.Integer)
    resume_lang = db.Column(db.String(5))
    jd_lang = db.Column(db.String(5))
    model_vendor = db.Column(db.String(20))
    model_name = db.Column(db.String(50))
    score = db.Column(db.Integer)
    feedback_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="executions")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(320), db.ForeignKey("users.email"), nullable=True)
    name = db.Column(db.String(300))
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="comments")
