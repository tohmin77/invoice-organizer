import hmac

import anthropic
import streamlit as st

from app.deepseek_extractor import extract_invoice_deepseek, make_client
from app.extractor import ExtractionError, extract_invoice, sniff_media_type
from app.review import needs_review
from app.sheets import GoogleSheetStore
from app.table import apply_edits, build_csv, new_row, rows_to_df

MAX_BYTES = 10 * 1024 * 1024

st.set_page_config(page_title="Invoice Organizer", page_icon="🧾", layout="wide")


def require_password() -> None:
    try:
        expected = st.secrets.get("app_password")
    except FileNotFoundError:
        expected = None
    if not expected:
        st.error("No app_password is set in the app's secrets, so the app is locked.")
        st.stop()
    if st.session_state.get("authed"):
        return
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(entered.encode(), str(expected).encode()):
            st.session_state["authed"] = True
            st.rerun()
        st.error("Wrong password.")
    st.stop()


@st.cache_resource
def get_store() -> GoogleSheetStore:
    return GoogleSheetStore(st.secrets["gcp_service_account"], st.secrets["sheet_url"])


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


@st.cache_resource
def get_deepseek_client():
    return make_client(st.secrets["DEEPSEEK_API_KEY"])


def available_engines() -> list[str]:
    engines = []
    if "ANTHROPIC_API_KEY" in st.secrets:
        engines.append("Claude")
    if "DEEPSEEK_API_KEY" in st.secrets:
        engines.append("DeepSeek")
    return engines


def run_extraction(engine: str, data: bytes, media_type: str):
    if engine == "DeepSeek":
        return extract_invoice_deepseek(data, media_type, get_deepseek_client())
    return extract_invoice(data, media_type, get_client())


def process(files: list[tuple[str, bytes]], engine: str) -> None:
    rows = st.session_state.rows
    failures = []
    progress = st.progress(0.0)
    for i, (name, data) in enumerate(files, start=1):
        media_type = sniff_media_type(data)
        if len(data) > MAX_BYTES:
            failures.append(f"{name}: larger than 10 MB.")
        elif media_type is None:
            failures.append(f"{name}: only PDF, JPG and PNG are supported.")
        else:
            try:
                extracted = run_extraction(engine, data, media_type)
                rows.append(new_row(name, extracted.model_dump()))
            except ExtractionError as exc:
                failures.append(f"{name}: {exc}")
        progress.progress(i / len(files))
    get_store().save(rows)
    st.session_state.upload_key += 1
    st.session_state.editor_v += 1
    st.session_state.messages = failures


require_password()
store = get_store()

st.session_state.setdefault("upload_key", 0)
st.session_state.setdefault("editor_v", 0)
if "rows" not in st.session_state:
    st.session_state.rows = store.load()

st.title("🧾 Invoice Organizer")

engines = available_engines()
if not engines:
    st.error("No ANTHROPIC_API_KEY or DEEPSEEK_API_KEY is set in the app's secrets.")
    st.stop()
default = st.secrets.get("default_engine", engines[0])
engine = st.sidebar.selectbox(
    "Extraction engine", engines, index=engines.index(default) if default in engines else 0
)
if engine == "DeepSeek":
    st.sidebar.caption("Uploaded invoices are sent to DeepSeek's servers. PDFs are limited to 5 pages.")
else:
    st.sidebar.caption("Uploaded invoices are sent to Anthropic's servers.")

key = st.session_state.upload_key
uploads = st.file_uploader(
    "Upload invoices (PDF, JPG, PNG)",
    type=["pdf", "jpg", "jpeg", "png"],
    accept_multiple_files=True,
    key=f"files{key}",
)
with st.expander("Take a photo instead"):
    photo = st.camera_input("Photograph an invoice", key=f"photo{key}")

pending = [(f.name, f.getvalue()) for f in uploads]
if photo is not None:
    pending.append(("camera photo.jpg", photo.getvalue()))

if st.button("Extract data", type="primary", disabled=not pending):
    with st.spinner("Reading invoices… this can take a little while."):
        process(pending, engine)
    st.rerun()

if st.session_state.pop("saved", False):
    st.success("Saved to Google Sheets.")
for msg in st.session_state.pop("messages", []):
    st.warning(msg)

rows = st.session_state.rows
st.caption("Edit any cell, add rows with the + at the bottom, or tick rows and press Delete. Click Save changes when done.")
review_only = st.checkbox("Show only rows needing review (⚠️)")
shown = [r for r in rows if not review_only or needs_review(r)]
shown_ids = {r["id"] for r in shown}

edited = st.data_editor(
    rows_to_df(shown),
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    key=f"editor{st.session_state.editor_v}-{review_only}",
    column_order=["review", "filename", "purchaser", "seller", "items", "amount", "gst", "date"],
    disabled=["review", "filename"],
    column_config={
        "review": st.column_config.TextColumn("", width="small"),
        "filename": "File",
        "items": "Items / services",
        "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
        "gst": st.column_config.NumberColumn("GST", format="%.2f"),
        "date": st.column_config.TextColumn("Date", help="YYYY-MM-DD"),
    },
)

left, mid, right = st.columns(3)
if left.button("Save changes"):
    new_rows, errors = apply_edits(rows, shown_ids, edited)
    if errors:
        for e in errors:
            st.error(e)
    else:
        store.save(new_rows)
        st.session_state.rows = new_rows
        st.session_state.editor_v += 1
        st.session_state.saved = True
        st.rerun()
mid.download_button("Download CSV", build_csv(rows), "invoices.csv", "text/csv")
right.link_button("Open in Google Sheets", store.url)
