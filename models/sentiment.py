from datetime import datetime
from . import db


class SentimentResult(db.Model):
    __tablename__ = "sentiment_results"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, unique=True)
    sentiment = db.Column(db.String(10), nullable=False, index=True)
    confidence = db.Column(db.Float, nullable=False)
    analyzed_at = db.Column(db.DateTime, default=datetime.now)
    complaint = db.relationship("Complaint", back_populates="sentiment_result")
