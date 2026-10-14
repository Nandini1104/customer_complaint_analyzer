"""Complaint Priority (Low / Medium / High) using transparent, rule-based points.

Points:
  * Negative sentiment: +2 (+1 more if the model is >= 85% confident)
  * Positive sentiment: -2 (so praise never becomes High)
  * Category weight: Payment/Refund/Account +2; Delivery/Product/Quality/
    Technical/Customer Service +1; others 0
  * Impact keywords (stopped working, charged twice, not received ...): +1
  * Urgent keywords (fraud, unauthorized, legal, urgent ...): +2
  * Repeat complaint (same customer, same category, last 30 days): +1
Result: >= 4 High, >= 2 Medium, otherwise Low.
"""
from .preprocessing import clean_text

CATEGORY_POINTS = {"Payment": 2, "Refund": 2, "Account": 2, "Delivery": 1, "Product": 1,
                   "Quality": 1, "Technical Issue": 1, "Customer Service": 1,
                   "Pricing": 0, "Other": 0}
IMPACT_PHRASES = ["stopped working", "not working", "does not work", "broken", "defective", "damaged",
                  "not received", "never received", "not arrived", "charged twice", "deducted",
                  "double charged", "crash", "can not log", "can not login", "wrong item", "missing"]
URGENT_PHRASES = ["fraud", "scam", "unauthorized", "stolen", "legal", "lawyer", "consumer court",
                  "urgent", "immediately", "hacked", "dangerous", "unsafe", "injury", "fire", "twice"]


def calculate_priority(text, sentiment, confidence, category, repeat_count=0):
    """Return {"priority": str, "score": int, "reasons": [str, ...]}."""
    cleaned = " " + clean_text(text) + " "
    score, reasons = 0, []
    if sentiment == "Negative":
        score += 2
        reasons.append("negative sentiment")
        if confidence >= 0.85:
            score += 1
            reasons.append("high-confidence negative")
    elif sentiment == "Positive":
        score -= 2
        reasons.append("positive sentiment")
    points = CATEGORY_POINTS.get(category, 0)
    if points:
        score += points
        reasons.append(f"{category} category")
    if any(f" {p} " in cleaned for p in IMPACT_PHRASES):
        score += 1
        reasons.append("customer impact keyword")
    if any(f" {p} " in cleaned for p in URGENT_PHRASES):
        score += 2
        reasons.append("urgent keyword")
    if repeat_count > 0:
        score += 1
        reasons.append("repeat complaint")
    label = "High" if score >= 4 else "Medium" if score >= 2 else "Low"
    return {"priority": label, "score": score, "reasons": reasons}
