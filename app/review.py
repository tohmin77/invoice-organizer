REQUIRED = ("purchaser", "seller", "amount", "date")


def review_reasons(row: dict) -> list[str]:
    reasons = [f"missing {f}" for f in REQUIRED if row.get(f) in (None, "")]
    amount, gst = row.get("amount"), row.get("gst")
    if isinstance(amount, (int, float)) and isinstance(gst, (int, float)) and gst > amount:
        reasons.append("GST is larger than amount")
    return reasons


def needs_review(row: dict) -> bool:
    return bool(review_reasons(row))
