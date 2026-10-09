import csv
import io
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .extractor import ExtractionError, extract_invoice
from .schemas import FIELDS, InvoiceData, InvoiceUpdate

load_dotenv()

BASE_DIR = Path(__file__).parent
DEFAULT_DB = BASE_DIR.parent / "data" / "invoices.db"
MAX_BYTES = 10 * 1024 * 1024
TEXT_FIELDS = ("filename", "purchaser", "seller", "items", "date")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

Extractor = Callable[[bytes, str], InvoiceData]


def sniff_media_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def build_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["filename", *FIELDS])
    for row in rows:
        writer.writerow(
            [_csv_safe(row[c]) if c in TEXT_FIELDS else row[c] for c in ("filename", *FIELDS)]
        )
    return out.getvalue()


def create_app(db_path: Path = DEFAULT_DB, extractor: Extractor = extract_invoice) -> FastAPI:
    db.init_db(db_path)
    app = FastAPI(title="Invoice Organizer")
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=BASE_DIR / "templates")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html")

    @app.get("/api/invoices")
    def list_all():
        return db.list_invoices(db_path)

    @app.post("/api/upload")
    def upload(files: list[UploadFile] = File(...)):
        results = []
        for f in files:
            name = Path(f.filename or "invoice").name
            data = f.file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                results.append({"filename": name, "error": "File is larger than 10 MB."})
                continue
            media_type = sniff_media_type(data)
            if media_type is None:
                results.append({"filename": name, "error": "Only PDF, JPG and PNG are supported."})
                continue
            try:
                extracted = extractor(data, media_type)
            except ExtractionError as exc:
                results.append({"filename": name, "error": str(exc)})
                continue
            invoice = db.add_invoice(db_path, name, extracted.model_dump())
            results.append({"filename": name, "invoice": invoice})
        return results

    @app.post("/api/invoices", status_code=201)
    def create(body: InvoiceUpdate):
        return db.add_invoice(db_path, "manual entry", body.model_dump())

    @app.patch("/api/invoices/{invoice_id}")
    def update(invoice_id: int, body: InvoiceUpdate):
        invoice = db.update_invoice(db_path, invoice_id, body.model_dump(exclude_unset=True))
        if invoice is None:
            raise HTTPException(404, "Invoice not found")
        return invoice

    @app.delete("/api/invoices/{invoice_id}", status_code=204)
    def delete(invoice_id: int):
        if not db.delete_invoice(db_path, invoice_id):
            raise HTTPException(404, "Invoice not found")

    @app.get("/api/export.csv")
    def export():
        return Response(
            build_csv(db.list_invoices(db_path)),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="invoices.csv"'},
        )

    return app

