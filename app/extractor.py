import base64
import os

import anthropic

from .schemas import InvoiceData

DEFAULT_MODEL = "claude-opus-5-5"

PROMPT = (
    "Extract the following from this invoice: purchaser (the party billed or buying), "
    "seller (the party issuing the invoice), items (a short comma-separated summary of the "
    "goods or services purchased), amount (total amount paid or payable, including tax, as a "
    "number), gst (the GST/tax amount included, as a number), and date (invoice or purchase "
    "date as YYYY-MM-DD). Use null for any field that is not on the invoice; never guess."
)


class ExtractionError(Exception):
    pass


def sniff_media_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _content_block(data: bytes, media_type: str) -> dict:
    kind = "document" if media_type == "application/pdf" else "image"
    return {
        "type": kind,
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def extract_invoice(
    data: bytes, media_type: str, client: anthropic.Anthropic | None = None
) -> InvoiceData:
    try:
        client = client or anthropic.Anthropic()
        response = client.messages.parse(
            model=os.environ.get("INVOICE_MODEL", DEFAULT_MODEL),
            max_tokens=16000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        _content_block(data, media_type),
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
            output_format=InvoiceData,
        )
    except anthropic.AnthropicError as exc:
        raise ExtractionError(f"Claude request failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise ExtractionError("The model declined to process this file.")
    if response.parsed_output is None:
        raise ExtractionError("Could not read structured data from the model response.")
    return response.parsed_output
