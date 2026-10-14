"""Rule-based complaint category detection with a confidence score.

Each category has weighted keywords/phrases. The category with the highest
total weight wins. Confidence = top_score / (sum_of_all_scores + 0.5), so a
clear single-category match scores higher than an ambiguous one. If nothing
matches the category is "Other" with confidence 0.
"""
from .preprocessing import clean_text

CATEGORIES = ["Product", "Delivery", "Payment", "Refund", "Customer Service",
              "Account", "Technical Issue", "Pricing", "Quality", "Other"]

# phrase -> weight (phrases are matched on cleaned text, so no punctuation)
KEYWORDS = {
    "Payment": {"payment": 2, "charged": 2, "charged twice": 3, "deducted": 3, "double charged": 3,
                "transaction": 2, "billing": 2, "invoice": 2, "card": 1, "upi": 2, "debited": 3,
                "declined": 2, "checkout": 1, "paid": 1, "overcharged": 2},
    "Delivery": {"delivery": 2, "delivered": 2, "shipping": 2, "shipment": 2, "courier": 2,
                 "arrived": 2, "not arrived": 3, "late": 1, "delayed": 2, "delay": 2, "tracking": 2,
                 "package": 1, "parcel": 2, "dispatched": 2, "wrong address": 3, "never received": 3},
    "Refund": {"refund": 3, "refunded": 3, "money back": 3, "return": 1, "returned": 1,
               "reimbursement": 3, "cancellation": 1, "cancel": 1, "replacement": 1},
    "Customer Service": {"customer service": 3, "customer support": 3, "support team": 3, "agent": 2,
                         "representative": 2, "staff": 2, "helpline": 2, "call centre": 2,
                         "call center": 2, "rude": 3, "no response": 2, "not respond": 2, "responded": 1,
                         "replied": 1, "complaint handling": 2, "executive": 1},
    "Account": {"account": 3, "login": 3, "log in": 3, "password": 3, "sign in": 3, "profile": 1,
                "locked": 2, "otp": 2, "verification": 1, "username": 2, "unsubscribe": 2, "hacked": 2},
    "Technical Issue": {"app": 2, "application": 2, "website": 2, "crash": 3, "crashes": 3, "crashing": 3,
                        "error": 2, "bug": 3, "glitch": 3, "freezes": 3, "freeze": 3, "loading": 2,
                        "upload": 2, "server": 2, "not loading": 3, "update": 1, "software": 2,
                        "slow": 1, "page": 1},
    "Pricing": {"price": 3, "prices": 3, "pricing": 3, "expensive": 3, "cost": 2, "costly": 3,
                "overpriced": 3, "discount": 2, "coupon": 2, "offer": 1, "cheaper": 2, "fee": 2,
                "fees": 2, "hidden charges": 3, "value for money": 3},
    "Quality": {"quality": 3, "poor quality": 4, "cheap material": 3, "material": 2, "stitching": 3,
                "flimsy": 3, "fake": 2, "durable": 2, "durability": 2, "build": 1, "finish": 1,
                "scratched": 2, "faded": 2},
    "Product": {"product": 2, "item": 2, "headphones": 2, "phone": 2, "laptop": 2, "stopped working": 3,
                "not working": 3, "does not work": 3, "broken": 3, "defective": 3, "damaged": 3,
                "faulty": 3, "battery": 2, "device": 2, "wrong item": 3, "missing parts": 3,
                "size": 1, "color": 1, "colour": 1},
}


def detect_category(text):
    """Return {"category", "confidence", "scores"} for the given complaint text."""
    cleaned = " " + clean_text(text) + " "
    scores = {}
    for category, words in KEYWORDS.items():
        total = 0
        for phrase, weight in words.items():
            if f" {phrase} " in cleaned:
                total += weight
        if total:
            scores[category] = total
    if not scores:
        return {"category": "Other", "confidence": 0.0, "scores": {}}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], CATEGORIES.index(kv[0])))
    top_category, top_score = ranked[0]
    confidence = round(top_score / (sum(scores.values()) + 0.5), 2)
    return {"category": top_category, "confidence": confidence, "scores": scores}
