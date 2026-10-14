from datetime import datetime
from . import db


class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    product = db.Column(db.String(150))
    complaint_text = db.Column(db.Text, nullable=False)
    cleaned_text = db.Column(db.Text)
    category = db.Column(db.String(40), index=True)
    platform = db.Column(db.String(50))
    priority = db.Column(db.String(10), index=True)
    status = db.Column(db.String(20), default="New", index=True)  # New / In Progress / Resolved / Closed
    reference_id = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    customer = db.relationship("Customer", back_populates="complaints")
    sentiment_result = db.relationship("SentimentResult", back_populates="complaint", uselist=False,
                                       cascade="all, delete-orphan")
    history = db.relationship("ComplaintHistory", back_populates="complaint",
                              order_by="ComplaintHistory.created_at, ComplaintHistory.id",
                              cascade="all, delete-orphan")

    @property
    def sentiment(self):
        return self.sentiment_result.sentiment if self.sentiment_result else None

    @property
    def confidence(self):
        return self.sentiment_result.confidence if self.sentiment_result else None
