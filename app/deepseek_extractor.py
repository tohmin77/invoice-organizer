import base64
import json
import os

import openai
import pymupdf
from pydantic import ValidationError

from .extractor import ExtractionError
from .schemas import InvoiceData

BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
MAX_PDF_PAGES = 5
PDF_DPI = 150

PROMPT = (
    "Extract the following from the invoice image(s) and reply with JSON only. "
    "Keys: purchaser (party billed or buying), seller (party issuing the invoice), "
    "items (short comma-separated summary of goods or services), amount (total paid or "
    "payable including tax, as a plain number), gst (GST/tax amount included, as a plain "
    "number), date (invoice date as YYYY-MM-DD). Use null for anything not on the invoice; "
    "never guess.\n"
    'Example JSON output: {"purchaser": "Acme Pte Ltd", "seller": "Widgets Co", '
    '"items": "Widgets x3", "amount": 109.0, "gst": 9.0, "date": "2026-03-04"}'
)


def make_client(api_key: str) -> openai.OpenAI:
    return openai.OpenAI(api_key=api_key, base_url=BASE_URL)


def _image_part(data: bytes, media_type: str) -> dict:
    b64 = base64.standard_b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}}


def _pdf_to_pngs(data: bytes) -> list[bytes]:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count > MAX_PDF_PAGES:
                raise ExtractionError(
                    f"PDF has {doc.page_count} pages; DeepSeek mode supports up to {MAX_PDF_PAGES}."
                )
            return [page.get_pixmap(dpi=PDF_DPI).tobytes("png") for page in doc]
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"Could not read the PDF: {exc}") from exc


def _parse(text: str) -> InvoiceData:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return InvoiceData.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ExtractionError("DeepSeek returned data in an unexpected format.") from exc


def extract_invoice_deepseek(
    data: bytes, media_type: str, client: openai.OpenAI
) -> InvoiceData:
    if media_type == "application/pdf":
        images = [_image_part(png, "image/png") for png in _pdf_to_pngs(data)]
    else:
        images = [_image_part(data, media_type)]

    try:
        response = client.chat.completions.create(
            model=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
            max_tokens=4096,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": [*images, {"type": "text", "text": PROMPT}]}],
        )
    except openai.OpenAIError as exc:
        raise ExtractionError(f"DeepSeek request failed: {exc}") from exc

    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise ExtractionError("DeepSeek's reply was cut off; please try again.")
    if not choice.message.content:
        raise ExtractionError("DeepSeek returned an empty reply; please try again.")
    return _parse(choice.message.content)
