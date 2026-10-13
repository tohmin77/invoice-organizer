from datetime import date

import pytest

from app.drive import DriveError, DriveStore, drive_filename, next_invoice_id

DAY = date(2026, 10, 10)


def test_next_invoice_id_is_sequential_across_days():
    assert next_invoice_id([], DAY) == "Invoice-001-261010"
    rows = [{"invoice_id": "Invoice-001-261009"}, {"invoice_id": "Invoice-007-261010"}, {"invoice_id": None}, {"invoice_id": "junk"}]
    assert next_invoice_id(rows, DAY) == "Invoice-008-261010"
    assert next_invoice_id(rows, date(2026, 10, 11)) == "Invoice-008-261011"


def test_next_invoice_id_grows_past_three_digits():
    assert next_invoice_id([{"invoice_id": "Invoice-999-261010"}], DAY) == "Invoice-1000-261010"


def test_drive_filename_uses_extension():
    assert drive_filename("Invoice-001-261010", "application/pdf") == "Invoice-001-261010.pdf"
    assert drive_filename("Invoice-001-261010", "image/jpeg") == "Invoice-001-261010.jpg"


class FakeSession:
    def __init__(self, status=200):
        self.status, self.calls = status, []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        status = self.status

        class R:
            status_code = status
            text = "denied"

            def json(self):
                return {"webViewLink": "https://drive.google.com/file/d/1/view"}

        return R()


def store_with(session):
    s = DriveStore.__new__(DriveStore)
    s._session, s._folder_id = session, "folder1"
    return s


def test_upload_sends_name_parent_and_bytes():
    session = FakeSession()
    url = store_with(session).upload("Invoice-1.pdf", b"PDFDATA", "application/pdf")
    assert url.startswith("https://drive.google.com")
    body = session.calls[0][1]["data"]
    assert b'"name": "Invoice-1.pdf"' in body and b'"folder1"' in body and b"PDFDATA" in body
    assert session.calls[0][1]["params"]["supportsAllDrives"] == "true"


def test_upload_failure_raises():
    with pytest.raises(DriveError):
        store_with(FakeSession(403)).upload("x.pdf", b"1", "application/pdf")
