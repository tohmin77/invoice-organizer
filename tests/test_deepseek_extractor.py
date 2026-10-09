from types import SimpleNamespace

import pymupdf
import pytest

from app.deepseek_extractor import MAX_PDF_PAGES, extract_invoice_deepseek
from app.extractor import ExtractionError

GOOD = '{"purchaser": "P", "seller": "S", "items": "x", "amount": "109.5", "gst": 9, "date": "2026-03-04"}'


class FakeClient:
    def __init__(self, content=GOOD, finish="stop"):
        self.calls = []
        msg = SimpleNamespace(content=content)
        self._resp = SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)])
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._resp


def pdf_bytes(pages=1):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Invoice page {i}")
    return doc.tobytes()


def test_image_request_shape_and_parsing():
    client = FakeClient()
    result = extract_invoice_deepseek(b"\x89PNG fake", "image/png", client)
    assert result.amount == 109.5 and result.gst == 9.0 and result.seller == "S"
    call = client.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    parts = call["messages"][0]["content"]
    assert parts[0]["type"] == "image_url"
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "JSON" in parts[-1]["text"]


def test_pdf_pages_become_images():
    client = FakeClient()
    extract_invoice_deepseek(pdf_bytes(2), "application/pdf", client)
    parts = client.calls[0]["messages"][0]["content"]
    assert [p["type"] for p in parts] == ["image_url", "image_url", "text"]
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_too_many_pages_rejected():
    with pytest.raises(ExtractionError, match="pages"):
        extract_invoice_deepseek(pdf_bytes(MAX_PDF_PAGES + 1), "application/pdf", FakeClient())


def test_unreadable_pdf_rejected():
    with pytest.raises(ExtractionError):
        extract_invoice_deepseek(b"%PDF-1.4 garbage", "application/pdf", FakeClient())


def test_code_fenced_json_accepted():
    result = extract_invoice_deepseek(b"x", "image/png", FakeClient(f"```json\n{GOOD}\n```"))
    assert result.seller == "S"


@pytest.mark.parametrize(
    "content,finish",
    [("", "stop"), (None, "stop"), ("not json", "stop"), ('{"amount": "abc"}', "stop"), (GOOD, "length")],
)
def test_bad_replies_raise(content, finish):
    with pytest.raises(ExtractionError):
        extract_invoice_deepseek(b"x", "image/png", FakeClient(content, finish))


def test_api_error_wrapped():
    import httpx
    import openai

    client = FakeClient()
    err = openai.APIConnectionError(request=httpx.Request("POST", "https://x"))

    def boom(**kw):
        raise err

    client.chat.completions.create = boom
    with pytest.raises(ExtractionError, match="DeepSeek request failed"):
        extract_invoice_deepseek(b"x", "image/png", client)
