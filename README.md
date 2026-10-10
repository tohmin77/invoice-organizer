# Invoice Organizer (Streamlit)

Upload invoices (PDF, JPG, PNG) or take a photo. Claude extracts purchaser, seller, items, amount, GST and date. Results are edited in a table and saved to a Google Sheet; CSV download is available too.

## One-time Google setup

1. In Google Cloud Console, create a project and enable the **Google Sheets API**.
2. Create a **service account** and download its JSON key.
3. Create a blank Google Sheet and share it (Editor) with the service account's `client_email`.

## Secrets

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (git-ignored) and fill in:
`ANTHROPIC_API_KEY` and/or `DEEPSEEK_API_KEY`, `app_password`, `sheet_url`, and the `[gcp_service_account]` fields from the JSON key.
On Streamlit Community Cloud, paste the same content into the app's **Secrets** settings. Never commit real secrets.

## Run locally

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
streamlit run streamlit_app.py
```

## Test

```sh
pytest
```

Tests use fakes, so no Google or Anthropic access is needed.

## Extraction engines

Provide `ANTHROPIC_API_KEY` (Claude), `DEEPSEEK_API_KEY` (DeepSeek), or both. With both, a sidebar selector switches engines; `default_engine` in secrets sets the starting choice. DeepSeek reads images only, so PDFs are rendered to page images first (max 5 pages). Its model defaults to `deepseek-flash`; override with `DEEPSEEK_MODEL`.

## Notes

- Rows flagged ⚠️ have a missing purchaser, seller, amount or date, or GST larger than the amount.
- Saving rewrites the whole sheet; if you also edit the sheet by hand at the same time, the last save wins.
- Uploaded files are sent to the selected engine's provider (Anthropic or DeepSeek) for extraction and are not stored; only extracted data goes to the sheet.
- The extraction model defaults to `claude-opus-5-5`; set the `INVOICE_MODEL` environment variable to change it.
