import pytest
from fastapi.testclient import TestClient

from app.extractor import ExtractionError
from app.main import create_app
from app.schemas import InvoiceData

PDF = b"%PDF-1.4 fake"
PNG = b"\x89PNG\r\n\x1a\n fake"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def client(db_path):
    def fake_extractor(data, media_type):
        if b"boom" in data:
            raise ExtractionError("model failed")
        return InvoiceData(
            purchaser="Acme Pte Ltd",
            seller="Widgets Co",
            items="Widgets x3",
            amount=109.0,
            gst=9.0,
            date="2026-03-04",
        )

    return TestClient(create_app(db_path, fake_extractor))
