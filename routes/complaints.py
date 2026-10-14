import os

import pandas as pd
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from analysis.analytics import apply_filters, base_query, filter_options
from analysis.category_detector import CATEGORIES
from config import BASE_DIR, Config
from models import Complaint, db
from services.complaint_service import (PLATFORMS, STATUSES, DuplicateError, ValidationError, add_note,
                                        auto_category_enabled, change_status, process_and_save,
                                        process_dataframe)

bp = Blueprint("complaints", __name__)
REQUIRED_COLUMNS = {"customer_name", "customer_email", "complaint_text"}
KNOWN_COLUMNS = REQUIRED_COLUMNS | {"product", "category", "platform", "timestamp", "customer_phone", "reference_id"}
MAX_CSV_ROWS = 5000


def get_or_404(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        abort(404)
    return complaint


@bp.route("/complaints")
@login_required
def list_complaints():
    query = apply_filters(base_query(), request.args)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Complaint.created_at.desc(), Complaint.id.desc()).paginate(
        page=page, per_page=Config.PER_PAGE, error_out=False)
    return render_template("complaints.html", pagination=pagination, categories=CATEGORIES,
                           statuses=STATUSES, platforms=PLATFORMS, **filter_options())


@bp.route("/complaints/add", methods=["GET", "POST"])
@login_required
def add_complaint():
    result, form = None, {}
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            result = process_and_save({
                "customer_name": form.get("customer_name"), "customer_email": form.get("customer_email"),
                "customer_phone": form.get("customer_phone"), "product": form.get("product"),
                "complaint_text": form.get("complaint_text"), "category": form.get("category"),
                "reference_id": form.get("reference_id"), "platform": form.get("platform"),
                "timestamp": (form.get("timestamp") or "").replace("T", " "),
            })
            flash(f"Complaint #{result['complaint_id']} analyzed and saved.", "success")
            form = {}
        except ValidationError as exc:
            flash(str(exc), "danger")
        except DuplicateError as exc:
            flash(str(exc), "warning")
        except Exception:
            db.session.rollback()
            flash("The complaint could not be saved because of a database problem.", "danger")
    return render_template("add_complaint.html", result=result, form=form, categories=CATEGORIES,
                           platforms=PLATFORMS, auto_category=auto_category_enabled())


@bp.route("/complaints/<int:complaint_id>")
@login_required
def complaint_detail(complaint_id):
    complaint = get_or_404(complaint_id)
    return render_template("complaint_detail.html", complaint=complaint, statuses=STATUSES)


@bp.route("/complaints/<int:complaint_id>/edit", methods=["GET", "POST"])
@login_required
def edit_complaint(complaint_id):
    complaint = get_or_404(complaint_id)
    if request.method == "POST":
        category, priority = request.form.get("category"), request.form.get("priority")
        platform = request.form.get("platform")
        if category not in CATEGORIES or priority not in ("Low", "Medium", "High") or platform not in PLATFORMS:
            flash("Please choose valid category, priority and platform values.", "danger")
        else:
            complaint.product = (request.form.get("product") or "Not specified").strip()[:150]
            complaint.reference_id = (request.form.get("reference_id") or "").strip()[:80] or None
            complaint.category, complaint.priority, complaint.platform = category, priority, platform
            db.session.commit()
            flash("Complaint updated.", "success")
            return redirect(url_for("complaints.complaint_detail", complaint_id=complaint.id))
    return render_template("edit_complaint.html", complaint=complaint, categories=CATEGORIES, platforms=PLATFORMS)


@bp.route("/complaints/<int:complaint_id>/status", methods=["POST"])
@login_required
def update_status(complaint_id):
    complaint = get_or_404(complaint_id)
    try:
        change_status(complaint, request.form.get("status"), (request.form.get("note") or "").strip() or None)
        flash(f"Status changed to {complaint.status}.", "success")
    except ValidationError as exc:
        flash(str(exc), "danger")
    target = request.form.get("next") or ""
    if not (target.startswith("/") and not target.startswith("//")):   # only local redirects
        target = url_for("complaints.complaint_detail", complaint_id=complaint_id)
    return redirect(target)


@bp.route("/complaints/<int:complaint_id>/note", methods=["POST"])
@login_required
def create_note(complaint_id):
    complaint = get_or_404(complaint_id)
    try:
        add_note(complaint, request.form.get("note"))
        flash("Note added.", "success")
    except ValidationError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("complaints.complaint_detail", complaint_id=complaint_id))


@bp.route("/complaints/<int:complaint_id>/delete", methods=["POST"])
@login_required
def delete_complaint(complaint_id):
    complaint = get_or_404(complaint_id)
    db.session.delete(complaint)
    db.session.commit()
    flash(f"Complaint #{complaint_id} deleted.", "success")
    return redirect(url_for("complaints.list_complaints"))


# ---------------- CSV upload ----------------
def _read_csv(source):
    """Read and validate a CSV; returns a DataFrame or raises ValidationError."""
    try:
        df = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception:
        raise ValidationError("The file could not be read as a CSV. Check the format and try again.")
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValidationError("Missing required column(s): " + ", ".join(sorted(missing)))
    if df.empty:
        raise ValidationError("The CSV file has no rows.")
    if len(df) > MAX_CSV_ROWS:
        raise ValidationError(f"Too many rows ({len(df)}). Maximum is {MAX_CSV_ROWS} per upload.")
    return df


@bp.route("/complaints/upload", methods=["GET", "POST"])
@login_required
def upload():
    summary = None
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Please choose a CSV file.", "danger")
        elif not file.filename.lower().endswith(".csv"):
            flash("Unsupported file type. Only .csv files are accepted.", "danger")
        else:
            try:
                summary = process_dataframe(_read_csv(file))
                flash(f"Processed {summary['processed']} of {summary['total']} rows.", "success")
            except ValidationError as exc:
                flash(str(exc), "danger")
    return render_template("upload.html", summary=summary)


@bp.route("/complaints/upload/sample", methods=["POST"])
@login_required
def upload_sample():
    """Convenience button: import the bundled demo CSV."""
    path = os.path.join(BASE_DIR, "data", "sample_complaints.csv")
    try:
        summary = process_dataframe(_read_csv(path))
        flash(f"Sample data: {summary['processed']} added, {summary['duplicates']} duplicates skipped, "
              f"{summary['failed']} failed.", "success")
    except ValidationError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("complaints.list_complaints"))
