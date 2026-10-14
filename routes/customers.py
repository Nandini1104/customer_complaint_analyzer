from flask import Blueprint, abort, render_template, request
from flask_login import login_required

from analysis.analytics import customer_rows
from models import Customer, db

bp = Blueprint("customers", __name__)


@bp.route("/customers")
@login_required
def list_customers():
    q = (request.args.get("q") or "").strip().lower()
    rows = customer_rows()
    if q:
        rows = [r for r in rows if q in r["customer"].name.lower() or q in r["customer"].email.lower()]
    return render_template("customers.html", rows=rows, q=q)


@bp.route("/customers/<int:customer_id>")
@login_required
def customer_detail(customer_id):
    customer = db_get(customer_id)
    complaints = sorted(customer.complaints, key=lambda c: c.created_at, reverse=True)
    return render_template("customer_detail.html", customer=customer, complaints=complaints)


def db_get(customer_id):
    customer = db.session.get(Customer, customer_id)
    if customer is None:
        abort(404)
    return customer
