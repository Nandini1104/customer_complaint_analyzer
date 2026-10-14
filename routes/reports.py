import csv
import io

from flask import Blueprint, Response, render_template, request
from flask_login import login_required

from analysis.analytics import (apply_filters, base_query, distributions, filter_options, summary, trend)
from analysis.category_detector import CATEGORIES
from models import Complaint
from services.complaint_service import PLATFORMS, STATUSES

bp = Blueprint("reports", __name__)


def _safe(value):
    """Prevent spreadsheet formula injection in exported CSV files."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def _filters():
    keys = ("date_range", "date_from", "date_to", "sentiment", "category", "priority", "status", "product", "platform")
    return {k: request.args.get(k, "") for k in keys}


@bp.route("/reports")
@login_required
def reports():
    filters = _filters()
    data = {"summary": summary(filters), "dist": distributions(filters), "trend": trend(filters, "daily")}
    return render_template("reports.html", filters=filters, data=data, categories=CATEGORIES,
                           statuses=STATUSES, platforms=PLATFORMS, **filter_options())


@bp.route("/reports/export/complaints.csv")
@login_required
def export_complaints():
    rows = apply_filters(base_query(), _filters()).order_by(Complaint.created_at.desc()).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["complaint_id", "customer_name", "customer_email", "product", "complaint_text", "sentiment",
                     "confidence", "category", "priority", "status", "platform", "reference_id", "created_at"])
    for c in rows:
        writer.writerow([c.id, _safe(c.customer.name), _safe(c.customer.email), _safe(c.product),
                         _safe(c.complaint_text), c.sentiment, c.confidence, c.category, c.priority,
                         c.status, c.platform, _safe(c.reference_id), c.created_at.strftime("%Y-%m-%d %H:%M:%S")])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=complaints_report.csv"})


@bp.route("/reports/export/summary.csv")
@login_required
def export_summary():
    filters = _filters()
    s, d, t = summary(filters), distributions(filters), trend(filters, "daily")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["section", "item", "value"])
    writer.writerow(["overview", "total_complaints", s["total"]])
    for key in ("positive", "negative", "neutral"):
        writer.writerow(["sentiment", key, s[key]])
    for name, count in d["category"].items():
        writer.writerow(["category", name, count])
    for name, count in d["priority"].items():
        writer.writerow(["priority", name, count])
    for name, count in d["status"].items():
        writer.writerow(["status", name, count])
    writer.writerow(["resolution", "resolved_or_closed_count", s["resolved_count"]])
    writer.writerow(["resolution", "average_resolution_hours", s["avg_resolution_hours"]])
    for label, count in zip(t["labels"], t["total"]):
        writer.writerow(["trend_daily", label, count])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=complaints_summary.csv"})
