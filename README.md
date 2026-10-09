# Invoice Organizer

Upload invoices (PDF, JPG, PNG), have Claude extract purchaser, seller, items, amount, GST and date, edit the results in a table, and download them as CSV.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # then put your ANTHROPIC_API_KEY in .env
```

## Run

```sh
uvicorn app.main:create_app --factory --host 127.0.0.1
```

Open http://127.0.0.1:8000. Data is stored in `data/invoices.db`. The extraction model defaults to `claude-opus-5-5`; set `INVOICE_MODEL` in `.env` to use another.

## Test

```sh
pytest
```

Tests mock the Claude call, so they need no API key.

## Notes

- Uploaded files are sent to Anthropic's API for extraction and are not kept locally; only extracted data and the filename are stored.
- Files are limited to 10 MB. Fields not found on an invoice are left blank.
