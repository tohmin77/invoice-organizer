import csv
import io

from tests.conftest import PDF, PNG


def upload(client, *files):
    return client.post("/api/upload", files=[("files", f) for f in files])


def test_upload_and_list(client):
    res = upload(client, ("a.pdf", PDF, "application/pdf"), ("b.png", PNG, "image/png"))
    assert res.status_code == 200
    assert [r["invoice"]["seller"] for r in res.json()] == ["Widgets Co", "Widgets Co"]
    assert len(client.get("/api/invoices").json()) == 2


def test_rejects_bad_type_and_reports_extraction_failure(client):
    res = upload(
        client,
        ("notes.txt", b"hello", "text/plain"),
        ("bad.pdf", PDF + b"boom", "application/pdf"),
        ("ok.pdf", PDF, "application/pdf"),
    ).json()
    assert "Only PDF" in res[0]["error"]
    assert res[1]["error"] == "model failed"
    assert "invoice" in res[2]
    assert len(client.get("/api/invoices").json()) == 1


def test_rejects_oversize(client, monkeypatch):
    monkeypatch.setattr("app.main.MAX_BYTES", 10)
    res = upload(client, ("big.pdf", PDF + b"x" * 20, "application/pdf")).json()
    assert "10 MB" in res[0]["error"]


def test_edit_and_delete(client):
    inv = upload(client, ("a.pdf", PDF, "application/pdf")).json()[0]["invoice"]
    url = f"/api/invoices/{inv['id']}"

    res = client.patch(url, json={"seller": "New", "gst": None})
    assert res.json()["seller"] == "New" and res.json()["gst"] is None
    assert res.json()["amount"] == 109.0

    assert client.patch(url, json={"date": "03/04/2026"}).status_code == 422
    assert client.patch("/api/invoices/999", json={"seller": "x"}).status_code == 404

    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404


def test_csv_export_and_formula_guard(client):
    inv = upload(client, ("a.pdf", PDF, "application/pdf")).json()[0]["invoice"]
    client.patch(f"/api/invoices/{inv['id']}", json={"seller": "=HYPERLINK(1)", "amount": -5})
    res = client.get("/api/export.csv")
    assert res.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0] == ["filename", "purchaser", "seller", "items", "amount", "gst", "date"]
    assert rows[1][2] == "'=HYPERLINK(1)"
    assert rows[1][4] == "-5.0"


def test_index_served(client):
    assert "Invoice Organizer" in client.get("/").text


def test_manual_create_then_edit(client):
    res = client.post("/api/invoices", json={"seller": "Corner Shop", "amount": 12.5})
    assert res.status_code == 201
    inv = res.json()
    assert inv["filename"] == "manual entry" and inv["seller"] == "Corner Shop"
    assert client.post("/api/invoices", json={"date": "bad"}).status_code == 422
    client.patch(f"/api/invoices/{inv['id']}", json={"purchaser": "Me"})
    assert client.get("/api/invoices").json()[0]["purchaser"] == "Me"
