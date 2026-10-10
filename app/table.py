import csv
import io
import uuid
from datetime import datetime, timezone

import pandas as pd
from pydantic import ValidationError

from .review import review_reasons
from .schemas import FIELDS, InvoiceUpdate

COLUMNS = ("id", "filename", *FIELDS, "created_at", "invoice_id", "drive_url")
TEXT_COLUMNS = ("invoice_id", "filename", "purchaser", "seller", "items", "date")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def new_row(filename: str, data: dict) -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "filename": filename,
        **{f: data.get(f) for f in FIELDS},
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "invoice_id": None,
        "drive_url": None,
    }


def rows_to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=list(COLUMNS)).astype(object)
    df.insert(0, "review", ["⚠️" if review_reasons(r) else "" for r in rows])
    for col in ("amount", "gst"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _clean(value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def apply_edits(
    all_rows: list[dict], shown_ids: set[str], edited: pd.DataFrame
) -> tuple[list[dict] | None, list[str]]:
    originals = {r["id"]: r for r in all_rows}
    errors, edited_rows = [], {}
    new_rows = []
    for n, rec in enumerate(edited.to_dict("records"), start=1):
        fields = {f: _clean(rec.get(f)) for f in FIELDS}
        if all(v is None for v in fields.values()) and _clean(rec.get("id")) is None:
            continue
        try:
            clean = InvoiceUpdate(**fields).model_dump()
        except ValidationError:
            errors.append(f"Row {n}: amount and GST must be numbers and date must be YYYY-MM-DD.")
            continue
        row_id = _clean(rec.get("id"))
        if row_id in originals:
            edited_rows[row_id] = {**originals[row_id], **clean}
        else:
            new_rows.append(new_row(_clean(rec.get("filename")) or "manual entry", clean))
    if errors:
        return None, errors
    result = []
    for r in all_rows:
        if r["id"] not in shown_ids:
            result.append(r)
        elif r["id"] in edited_rows:
            result.append(edited_rows[r["id"]])
    return result + new_rows, []


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def build_csv(rows: list[dict]) -> str:
    cols = ("invoice_id", "filename", *FIELDS)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(cols)
    for row in rows:
        writer.writerow([_csv_safe(row[c]) if c in TEXT_COLUMNS else row[c] for c in cols])
    return out.getvalue()
