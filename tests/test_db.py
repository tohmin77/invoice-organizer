from app import db


def test_crud_roundtrip(db_path):
    db.init_db(db_path)
    row = db.add_invoice(db_path, "a.pdf", {"seller": "S", "amount": 5.0})
    assert row["seller"] == "S" and row["purchaser"] is None
    assert db.list_invoices(db_path) == [row]

    updated = db.update_invoice(db_path, row["id"], {"gst": 0.5, "bogus": "x"})
    assert updated["gst"] == 0.5

    assert db.update_invoice(db_path, 999, {"gst": 1}) is None
    assert db.delete_invoice(db_path, row["id"]) is True
    assert db.delete_invoice(db_path, row["id"]) is False
    assert db.list_invoices(db_path) == []


def test_list_newest_first(db_path):
    db.init_db(db_path)
    db.add_invoice(db_path, "1.pdf", {})
    db.add_invoice(db_path, "2.pdf", {})
    assert [r["filename"] for r in db.list_invoices(db_path)] == ["2.pdf", "1.pdf"]
