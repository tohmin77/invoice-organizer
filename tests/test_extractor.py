from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.extractor import ExtractionError, extract_invoice
from app.schemas import InvoiceData


class FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self._response, self._error = response, error
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def test_pdf_sent_as_document_and_result_returned():
    parsed = InvoiceData(seller="S", amount=1.0)
    client = FakeClient(SimpleNamespace(stop_reason="end_turn", parsed_output=parsed))
    assert extract_invoice(b"%PDF-x", "application/pdf", client) is parsed
    block = client.calls[0]["messages"][0]["content"][0]
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"
    assert client.calls[0]["output_format"] is InvoiceData


def test_image_sent_as_image():
    client = FakeClient(SimpleNamespace(stop_reason="end_turn", parsed_output=InvoiceData()))
    extract_invoice(b"x", "image/png", client)
    assert client.calls[0]["messages"][0]["content"][0]["type"] == "image"


def test_refusal_and_missing_output_raise():
    for resp in (
        SimpleNamespace(stop_reason="refusal", parsed_output=None),
        SimpleNamespace(stop_reason="end_turn", parsed_output=None),
    ):
        with pytest.raises(ExtractionError):
            extract_invoice(b"x", "image/png", FakeClient(resp))


def test_api_error_wrapped():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))
    with pytest.raises(ExtractionError):
        extract_invoice(b"x", "image/png", FakeClient(error=err))


def test_invalid_date_becomes_none():
    assert InvoiceData(date="not a date").date is None
    assert InvoiceData(date="2026-03-04").date == "2026-03-04"
