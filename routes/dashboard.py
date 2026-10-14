from flask import Blueprint, render_template
from flask_login import login_required

from analysis.analytics import apply_filters, base_query, summary
from models import Complaint

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    stats = summary()                                   # every number comes from SQLite
    recent = Complaint.query.order_by(Complaint.created_at.desc()).limit(6).all()
    urgent = (Complaint.query.filter(Complaint.priority == "High", Complaint.status.in_(["New", "In Progress"]))
              .order_by(Complaint.created_at.desc()).limit(5).all())
    return render_template("dashboard.html", stats=stats, recent=recent, urgent=urgent)
