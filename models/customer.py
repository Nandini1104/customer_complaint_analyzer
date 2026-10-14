from datetime import datetime
from . import db


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.now)
    complaints = db.relationship("Complaint", back_populates="customer", cascade="all, delete-orphan")
