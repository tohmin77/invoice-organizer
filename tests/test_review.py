from app.review import needs_review, review_reasons


def test_complete_row_ok():
    row = {"purchaser": "A", "seller": "B", "amount": 10.0, "gst": 1.0, "date": "2026-01-01"}
    assert not needs_review(row)


def test_missing_fields_flagged():
    assert review_reasons({"seller": "B", "amount": 10.0}) == ["missing purchaser", "missing date"]


def test_zero_amount_is_not_missing():
    row = {"purchaser": "A", "seller": "B", "amount": 0.0, "date": "2026-01-01"}
    assert not needs_review(row)


def test_gst_larger_than_amount():
    row = {"purchaser": "A", "seller": "B", "amount": 5.0, "gst": 9.0, "date": "2026-01-01"}
    assert "GST is larger than amount" in review_reasons(row)
