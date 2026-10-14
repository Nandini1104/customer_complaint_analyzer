"""JSON REST API.

Reading (GET) works with a logged-in browser session OR an `X-API-Key` header.
Writing (POST/PUT) requires the `X-API-Key` header, so external systems can send
complaints and browsers are protected from cross-site request forgery.
"""
import hmac
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user

from analysis.analytics import apply_filters, base_query, customer_rows, distributions, summary, trend
from analysis.category_detector import CATEGORIES
from models import Complaint, Customer, db
from routes.settings import current_api_key
from services.complaint_service import (PLATFORMS, STATUSES, DuplicateError, ValidationError, add_note,
                                        analyze_text, change_status, process_and_save)

bp = Blueprint("api", __name__, url_prefix="/api")


def api_auth(write=False):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            sent = request.headers.get("X-API-Key", "")
            key = current_api_key() or ""
            if sent and key and hmac.compare_digest(sent, key):
                return view(*args, **kwargs)
            if not write and current_user.is_authenticated:
                return view(*args, **kwargs)
            return jsonify(success=False, error="Missing or invalid API key (send it in the X-API-Key header)."), 401
        return wrapper
    return decorator


def error(message, status=400):
    return jsonify(success=False, error=message), status


def complaint_to_dict(c):
    return {
        "id": c.id, "customer": {"id": c.customer.id, "name": c.customer.name, "email": c.customer.email,
                                  "phone": c.customer.phone},
        "product": c.product, "complaint_text": c.complaint_text, "cleaned_text": c.cleaned_text,
        "sentiment": c.sentiment, "confidence": c.confidence, "category": c.category, "priority": c.priority,
        "status": c.status, "platform": c.platform, "reference_id": c.reference_id,
        "created_at": c.created_at.isoformat(sep=" ", timespec="seconds"),
        "updated_at": c.updated_at.isoformat(sep=" ", timespec="seconds") if c.updated_at else None,
        "history": [{"status": h.status, "note": h.note, "created_at": h.created_at.isoformat(sep=" ", timespec="seconds")}
                    for h in c.history],
    }


@bp.route("/complaints", methods=["POST"])
@api_auth(write=True)
def create_complaint():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be a JSON object.")
    try:
        return jsonify(process_and_save(data)), 201
    except ValidationError as exc:
        return error(str(exc))
    except DuplicateError as exc:
        db.session.rollback()
        return error(str(exc), 409)
    except Exception:
        db.session.rollback()
        return error("The complaint could not be saved.", 500)


@bp.route("/complaints", methods=["GET"])
@api_auth()
def list_complaints():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)
    query = apply_filters(base_query(), request.args).order_by(Complaint.created_at.desc(), Complaint.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(success=True, page=page, per_page=per_page, total=pagination.total,
                   complaints=[complaint_to_dict(c) for c in pagination.items])


@bp.route("/complaints/<int:complaint_id>", methods=["GET"])
@api_auth()
def get_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint:
        return error("Complaint not found.", 404)
    return jsonify(success=True, complaint=complaint_to_dict(complaint))


@bp.route("/complaints/<int:complaint_id>", methods=["PUT"])
@api_auth(write=True)
def update_complaint(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint:
        return error("Complaint not found.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be a JSON object.")
    try:
        if "category" in data and data["category"] not in CATEGORIES:
            return error("Invalid category.")
        if "priority" in data and data["priority"] not in ("Low", "Medium", "High"):
            return error("Invalid priority.")
        if "platform" in data and data["platform"] not in PLATFORMS:
            return error("Invalid platform.")
        for field in ("category", "priority", "platform"):
            if field in data:
                setattr(complaint, field, data[field])
        if "product" in data:
            complaint.product = str(data["product"])[:150]
        if "reference_id" in data:
            complaint.reference_id = str(data["reference_id"])[:80] or None
        db.session.commit()
        if "status" in data:
            change_status(complaint, data["status"], data.get("status_note"))
        if data.get("note"):
            add_note(complaint, data["note"])
    except ValidationError as exc:
        db.session.rollback()
        return error(str(exc))
    return jsonify(success=True, complaint=complaint_to_dict(complaint))


@bp.route("/analyze", methods=["POST"])
@api_auth(write=True)
def analyze():
    """Analyze text without saving anything."""
    data = request.get_json(silent=True)
    text = data.get("complaint_text") if isinstance(data, dict) else None
    if not text or not str(text).strip():
        return error("complaint_text is required.")
    try:
        cleaned, sentiment, category = analyze_text(str(text))
    except ValidationError as exc:
        return error(str(exc))
    return jsonify(success=True, cleaned_text=cleaned, sentiment=sentiment["sentiment"],
                   confidence=sentiment["confidence"], probabilities=sentiment["probabilities"],
                   predicted_category=category["category"], category_confidence=category["confidence"])


@bp.route("/sentiment", methods=["GET"])
@api_auth()
def sentiment():
    d = distributions(request.args)
    return jsonify(success=True, total=d["total"], counts=d["sentiment"], percentages=d["sentiment_pct"])


@bp.route("/categories", methods=["GET"])
@api_auth()
def categories():
    d = distributions(request.args)
    return jsonify(success=True, categories=CATEGORIES, counts=d["category"], total=d["total"])


@bp.route("/analytics", methods=["GET"])
@api_auth()
def analytics():
    period = request.args.get("period", "daily")
    if period not in ("daily", "weekly", "monthly"):
        period = "daily"
    return jsonify(success=True, summary=summary(request.args), distributions=distributions(request.args),
                   trend=trend(request.args, period))


@bp.route("/customers", methods=["GET"])
@api_auth()
def customers():
    rows = [{"id": r["customer"].id, "name": r["customer"].name, "email": r["customer"].email,
             "phone": r["customer"].phone, "complaints": r["total"],
             "last_complaint": r["last"].isoformat(sep=" ", timespec="seconds") if r["last"] else None,
             "sentiment_counts": r["counts"], "overall_sentiment": r["overall"]} for r in customer_rows()]
    return jsonify(success=True, total=len(rows), customers=rows)
