"""Database analytics: every number shown in charts, cards and reports comes from here."""
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, or_

from analysis.category_detector import CATEGORIES
from models import Complaint, ComplaintHistory, Customer, SentimentResult, db

SENTIMENTS = ["Positive", "Negative", "Neutral"]
STATUS_LIST = ["New", "In Progress", "Resolved", "Closed"]
PRIORITIES = ["Low", "Medium", "High"]


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def base_query():
    """Complaints joined with customer and sentiment (needed for search and filters)."""
    return (Complaint.query.join(Customer, Complaint.customer_id == Customer.id)
            .outerjoin(SentimentResult, SentimentResult.complaint_id == Complaint.id))


def apply_filters(query, args):
    """Apply search + filters from a dict-like `args` (request.args or API params)."""
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        conditions = [Customer.name.ilike(like), Customer.email.ilike(like), Complaint.product.ilike(like),
                      Complaint.complaint_text.ilike(like), Complaint.reference_id.ilike(like)]
        if q.lstrip("#").isdigit():
            conditions.append(Complaint.id == int(q.lstrip("#")))
        query = query.filter(or_(*conditions))
    if args.get("sentiment") in SENTIMENTS:
        query = query.filter(SentimentResult.sentiment == args["sentiment"])
    if args.get("priority") in PRIORITIES:
        query = query.filter(Complaint.priority == args["priority"])
    if args.get("status") in STATUS_LIST:
        query = query.filter(Complaint.status == args["status"])
    if args.get("category") in CATEGORIES:
        query = query.filter(Complaint.category == args["category"])
    if args.get("product"):
        query = query.filter(Complaint.product.ilike(f"%{args['product']}%"))
    if args.get("platform"):
        query = query.filter(Complaint.platform == args["platform"])
    now = datetime.now()
    date_range = args.get("date_range")
    if date_range == "today":
        query = query.filter(Complaint.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
    elif date_range == "7d":
        query = query.filter(Complaint.created_at >= now - timedelta(days=7))
    elif date_range == "30d":
        query = query.filter(Complaint.created_at >= now - timedelta(days=30))
    elif date_range == "custom":
        start, end = parse_date(args.get("date_from")), parse_date(args.get("date_to"))
        if start:
            query = query.filter(Complaint.created_at >= start)
        if end:
            query = query.filter(Complaint.created_at < end + timedelta(days=1))
    return query


def _count_by(query, column):
    """Count filtered complaints grouped by one column (query already has the joins)."""
    rows = query.with_entities(column, func.count(Complaint.id)).group_by(column).all()
    return {key: count for key, count in rows}


def _ids(query):
    return [row[0] for row in query.with_entities(Complaint.id).all()]


def resolution_hours(complaint_ids):
    """Hours from creation to the FIRST Resolved/Closed history entry, per complaint."""
    if not complaint_ids:
        return []
    rows = (db.session.query(Complaint.created_at, func.min(ComplaintHistory.created_at))
            .join(ComplaintHistory, ComplaintHistory.complaint_id == Complaint.id)
            .filter(Complaint.id.in_(complaint_ids), ComplaintHistory.status.in_(["Resolved", "Closed"]))
            .group_by(Complaint.id).all())
    return [max(0.0, (done - created).total_seconds() / 3600) for created, done in rows]


def summary(args=None):
    """Numbers for the dashboard cards and report header."""
    query = apply_filters(base_query(), args or {})
    ids = _ids(query)
    total = len(ids)
    status = _count_by(query, Complaint.status)
    sentiment = _count_by(query, SentimentResult.sentiment)
    hours = resolution_hours(ids)
    positive = sentiment.get("Positive", 0)
    return {
        "total": total,
        "new": status.get("New", 0), "in_progress": status.get("In Progress", 0),
        "resolved": status.get("Resolved", 0), "closed": status.get("Closed", 0),
        "open": status.get("New", 0) + status.get("In Progress", 0),
        "positive": positive, "negative": sentiment.get("Negative", 0), "neutral": sentiment.get("Neutral", 0),
        "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
        "resolved_count": len(hours),
        # share of complaints whose text expresses positive sentiment
        "satisfaction_pct": round(positive / total * 100, 1) if total else 0.0,
    }


def distributions(args=None):
    """Sentiment, category, status and priority counts (zero-filled so charts keep all labels)."""
    query = apply_filters(base_query(), args or {})
    total = query.count()
    sentiment = _count_by(query, SentimentResult.sentiment)
    category = _count_by(query, Complaint.category)
    status = _count_by(query, Complaint.status)
    priority = _count_by(query, Complaint.priority)
    return {
        "total": total,
        "sentiment": {k: sentiment.get(k, 0) for k in SENTIMENTS},
        "sentiment_pct": {k: round(sentiment.get(k, 0) / total * 100, 1) if total else 0 for k in SENTIMENTS},
        "category": {k: category.get(k, 0) for k in CATEGORIES},
        "status": {k: status.get(k, 0) for k in STATUS_LIST},
        "priority": {k: priority.get(k, 0) for k in PRIORITIES},
    }


def trend(args=None, period="daily"):
    """Complaints over time grouped by day / week / month (computed with pandas)."""
    query = apply_filters(base_query(), args or {})
    rows = query.with_entities(Complaint.created_at, SentimentResult.sentiment).all()
    if not rows:
        return {"labels": [], "total": [], "Positive": [], "Negative": [], "Neutral": []}
    df = pd.DataFrame(rows, columns=["created_at", "sentiment"])
    df["created_at"] = pd.to_datetime(df["created_at"])
    if period == "monthly":
        df["bucket"] = df["created_at"].dt.strftime("%Y-%m")
    elif period == "weekly":
        df["bucket"] = (df["created_at"] - pd.to_timedelta(df["created_at"].dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
    else:
        df["bucket"] = df["created_at"].dt.strftime("%Y-%m-%d")
    table = df.groupby(["bucket", "sentiment"]).size().unstack(fill_value=0)
    for s in SENTIMENTS:
        if s not in table.columns:
            table[s] = 0
    table = table.sort_index()
    return {"labels": list(table.index), "total": table[SENTIMENTS].sum(axis=1).astype(int).tolist(),
            **{s: table[s].astype(int).tolist() for s in SENTIMENTS}}


def filter_options():
    """Distinct products and platforms for the filter drop-downs."""
    products = [r[0] for r in db.session.query(Complaint.product).distinct().order_by(Complaint.product) if r[0]]
    platforms = [r[0] for r in db.session.query(Complaint.platform).distinct().order_by(Complaint.platform) if r[0]]
    return {"products": products, "platforms": platforms}


def customer_rows():
    """One row per customer with complaint count, last complaint date and sentiment summary."""
    rows = []
    for customer in Customer.query.order_by(Customer.name).all():
        counts = {s: 0 for s in SENTIMENTS}
        last = None
        for c in customer.complaints:
            if c.sentiment:
                counts[c.sentiment] += 1
            if last is None or c.created_at > last:
                last = c.created_at
        total = len(customer.complaints)
        overall = max(counts, key=counts.get) if total else "-"
        rows.append({"customer": customer, "total": total, "last": last, "counts": counts, "overall": overall})
    return rows
