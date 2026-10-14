from datetime import datetime
from . import db


class ComplaintHistory(db.Model):
    """One row per status change or admin note."""
    __tablename__ = "complaint_history"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    status = db.Column(db.String(20))           # status at that moment
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    complaint = db.relationship("Complaint", back_populates="history")
