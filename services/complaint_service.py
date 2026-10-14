"""The complaint pipeline:
validate -> clean -> sentiment -> category -> priority -> save (+history).
Used by the Add Complaint form, CSV upload and the REST API.
"""
import re
from datetime import datetime, timedelta

import pandas as pd

from analysis.category_detector import CATEGORIES, detect_category
from analysis.preprocessing import clean_text, preprocess_for_model
from analysis.priority import calculate_priority
from analysis.sentiment_analyzer import ModelError, get_analyzer
from models import Complaint, ComplaintHistory, Customer, SentimentResult, Setting, db

PLATFORMS = ["Website", "Email", "Phone", "Mobile App", "Social Media", "Chat", "Other"]
STATUSES = ["New", "In Progress", "Resolved", "Closed"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(Exception):
    """Input is invalid (message is safe to show to the user)."""


class DuplicateError(Exception):
    """The same customer already submitted this complaint text."""


def auto_category_enabled():
    return Setting.get("auto_category", "1") == "1"


def parse_timestamp(value):
    """Accept blank (=now) or any common date/time format; raise ValidationError otherwise."""
    if value is None or str(value).strip() == "" or str(value).lower() == "nan":
        return datetime.now()
    parsed = pd.to_datetime(str(value).strip(), errors="coerce")
    if pd.isna(parsed):
        raise ValidationError(f"Invalid date/time: {value}")
    return parsed.to_pydatetime().replace(tzinfo=None)


def validate_input(data):
    """Return a cleaned dict of fields or raise ValidationError."""
    def field(name):
        value = data.get(name)
        return "" if value is None or str(value).lower() == "nan" else str(value).strip()

    name, email, text = field("customer_name"), field("customer_email").lower(), field("complaint_text")
    if not name:
        raise ValidationError("Customer name is required.")
    if not EMAIL_RE.match(email) or len(email) > 190:
        raise ValidationError("A valid customer email is required.")
    if not text:
        raise ValidationError("Complaint text cannot be empty.")
    if len(text) < 5 or len(text) > 5000:
        raise ValidationError("Complaint text must be between 5 and 5000 characters.")
    category = field("category")
    if category:
        match = next((c for c in CATEGORIES if c.lower() == category.lower()), None)
        if not match:
            raise ValidationError(f"Unknown category '{category}'. Allowed: {', '.join(CATEGORIES)}.")
        category = match
    platform = field("platform") or "Website"
    platform = next((p for p in PLATFORMS if p.lower() == platform.lower()), "Other")
    return {
        "name": name[:120], "email": email, "phone": field("customer_phone")[:30],
        "product": (field("product") or "Not specified")[:150], "text": text,
        "category": category, "platform": platform, "reference_id": field("reference_id")[:80],
        "created_at": parse_timestamp(data.get("timestamp")),
    }


def analyze_text(text):
    """Run the NLP steps only (used by /api/analyze too). Nothing is saved."""
    cleaned = clean_text(text)
    if not preprocess_for_model(text):
        raise ValidationError("Complaint text has no analyzable words.")
    try:
        sentiment = get_analyzer().predict(text)
    except ModelError as exc:
        raise ValidationError(str(exc))
    category = detect_category(text)
    return cleaned, sentiment, category


def _get_or_create_customer(fields):
    customer = Customer.query.filter_by(email=fields["email"]).first()
    if not customer:
        customer = Customer(name=fields["name"], email=fields["email"], phone=fields["phone"] or None)
        db.session.add(customer)
        db.session.flush()
    elif fields["phone"] and not customer.phone:
        customer.phone = fields["phone"]
    return customer


def process_and_save(data):
    """Full pipeline for one complaint. Returns a result dict; raises ValidationError/DuplicateError."""
    fields = validate_input(data)
    cleaned, sentiment, detected = analyze_text(fields["text"])

    customer = Customer.query.filter_by(email=fields["email"]).first()
    if customer and Complaint.query.filter_by(customer_id=customer.id, cleaned_text=cleaned).first():
        raise DuplicateError("This customer has already submitted the same complaint.")

    # User-selected category wins; otherwise use the automatic one (if enabled)
    if fields["category"]:
        final_category = fields["category"]
    elif auto_category_enabled():
        final_category = detected["category"]
    else:
        final_category = "Other"

    repeat_count = 0
    if customer:                                  # same customer + category in the last 30 days
        since = fields["created_at"] - timedelta(days=30)
        repeat_count = Complaint.query.filter(
            Complaint.customer_id == customer.id, Complaint.category == final_category,
            Complaint.created_at >= since).count()
    priority = calculate_priority(fields["text"], sentiment["sentiment"], sentiment["confidence"],
                                  final_category, repeat_count)

    customer = _get_or_create_customer(fields)
    complaint = Complaint(
        customer_id=customer.id, product=fields["product"], complaint_text=fields["text"],
        cleaned_text=cleaned, category=final_category, platform=fields["platform"],
        priority=priority["priority"], status="New", reference_id=fields["reference_id"] or None,
        created_at=fields["created_at"], updated_at=fields["created_at"])
    db.session.add(complaint)
    db.session.flush()
    db.session.add(SentimentResult(complaint_id=complaint.id, sentiment=sentiment["sentiment"],
                                   confidence=sentiment["confidence"]))
    db.session.add(ComplaintHistory(complaint_id=complaint.id, status="New",
                                    note="Complaint received and analyzed.", created_at=fields["created_at"]))
    db.session.commit()
    return {
        "success": True, "complaint_id": complaint.id, "sentiment": sentiment["sentiment"],
        "confidence": sentiment["confidence"], "probabilities": sentiment["probabilities"],
        "category": final_category, "predicted_category": detected["category"],
        "category_confidence": detected["confidence"], "priority": priority["priority"],
        "priority_reasons": priority["reasons"], "cleaned_text": cleaned,
    }


def process_dataframe(df):
    """Process every CSV row. Returns counts and per-row error messages."""
    result = {"total": len(df), "processed": 0, "failed": 0, "duplicates": 0, "errors": []}
    for index, row in df.iterrows():
        line = index + 2                           # +1 header, +1 for 1-based numbering
        try:
            process_and_save(row.to_dict())
            result["processed"] += 1
        except DuplicateError:
            db.session.rollback()
            result["duplicates"] += 1
        except ValidationError as exc:
            db.session.rollback()
            result["failed"] += 1
            result["errors"].append(f"Row {line}: {exc}")
        except Exception:                           # database or unexpected problem on this row only
            db.session.rollback()
            result["failed"] += 1
            result["errors"].append(f"Row {line}: could not be saved.")
    return result


def change_status(complaint, new_status, note=None):
    if new_status not in STATUSES:
        raise ValidationError("Invalid status.")
    complaint.status = new_status
    complaint.updated_at = datetime.now()
    db.session.add(ComplaintHistory(complaint_id=complaint.id, status=new_status,
                                    note=note or f"Status changed to {new_status}."))
    db.session.commit()


def add_note(complaint, note):
    note = (note or "").strip()
    if not note:
        raise ValidationError("Note cannot be empty.")
    if len(note) > 2000:
        raise ValidationError("Note is too long (max 2000 characters).")
    db.session.add(ComplaintHistory(complaint_id=complaint.id, status=complaint.status, note="Note: " + note))
    complaint.updated_at = datetime.now()
    db.session.commit()
