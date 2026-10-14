from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from . import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Setting(db.Model):
    """Simple key/value settings (auto category detection, API key ...)."""
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    value = db.Column(db.String(255))

    @staticmethod
    def get(name, default=None):
        row = Setting.query.filter_by(name=name).first()
        return row.value if row else default

    @staticmethod
    def set(name, value):
        row = Setting.query.filter_by(name=name).first()
        if row:
            row.value = str(value)
        else:
            db.session.add(Setting(name=name, value=str(value)))
        db.session.commit()
