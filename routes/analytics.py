from flask import Blueprint, render_template
from flask_login import login_required

from analysis.analytics import distributions, filter_options
from analysis.category_detector import CATEGORIES
from services.complaint_service import STATUSES

bp = Blueprint("analytics", __name__)


@bp.route("/analytics")
@login_required
def sentiment_analytics():
    return render_template("analytics.html", categories=CATEGORIES, statuses=STATUSES, **filter_options())


@bp.route("/categories")
@login_required
def categories():
    data = distributions()
    ranked = sorted(data["category"].items(), key=lambda kv: -kv[1])
    return render_template("categories.html", ranked=ranked, total=data["total"])


@bp.route("/trends")
@login_required
def trends():
    return render_template("trends.html", categories=CATEGORIES, statuses=STATUSES, **filter_options())
