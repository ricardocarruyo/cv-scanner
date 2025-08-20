# app/seeds.py
from .extensions import db
from .models import Membership

def seed_memberships():
    defaults = [
        {"code": "level_1", "title": "Nivel 1", "max_execs": 10},
        {"code": "level_2", "title": "Nivel 2", "max_execs": 50},
        {"code": "level_3", "title": "Nivel 3", "max_execs": 100},
    ]
    for d in defaults:
        m = Membership.query.filter_by(code=d["code"]).first()
        if not m:
            m = Membership(**d, is_active=True)
            db.session.add(m)
    db.session.commit()
