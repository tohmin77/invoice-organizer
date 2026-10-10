from datetime import date

import pytest

from app.drive import DriveError, DriveStore, drive_filename, next_invoice_id

DAY = date(2026, 10, 10)


def test_next_invoice_id_counts_per_day():
    assert next_invoice_id([], DAY) == "20261010-001"
    rows = [{"invoice_id": "20261010-001"}, {"invoice_id": "20261010-007"}, {"invoice_id": "20261009-012"}, {"invoice_id": None}]
    assert next_invoice_id(rows, DAY) == "20261010-008"
    assert next_invoice_id(rows, date(2026, 10, 11)) == "20261011-001"


def test_drive_filename_uses_extension():
    assert drive_filename("20261010-001", "application/pdf") == "Invoice-20261010-001.pdf"
    assert drive_filename("20261010-001", "image/jpeg") == "Invoice-20261010-001.jpg"


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
