from typing import Protocol

import gspread
from google.oauth2.service_account import Credentials

from .table import COLUMNS

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
NUMERIC = ("amount", "gst")


class RowStore(Protocol):
    def load(self) -> list[dict]: ...
    def save(self, rows: list[dict]) -> None: ...


class MemoryStore:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = list(rows or [])

    def load(self) -> list[dict]:
        return [dict(r) for r in self.rows]

    def save(self, rows: list[dict]) -> None:
        self.rows = [dict(r) for r in rows]


def _to_number(value):
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class GoogleSheetStore:
    def __init__(self, service_account_info: dict, sheet_url: str):
        creds = Credentials.from_service_account_info(dict(service_account_info), scopes=SCOPES)
        self._ws = gspread.authorize(creds).open_by_url(sheet_url).sheet1
        self.url = sheet_url

    def load(self) -> list[dict]:
        values = self._ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
        if not values or tuple(values[0]) != COLUMNS:
            return []
        rows = []
        for raw in values[1:]:
            raw = list(raw) + [""] * (len(COLUMNS) - len(raw))
            row = {c: (None if v == "" else v) for c, v in zip(COLUMNS, raw)}
            for c in NUMERIC:
                row[c] = _to_number(row[c])
            if row["id"] is not None:
                row["id"] = str(row["id"])
                rows.append(row)
        return rows

    def save(self, rows: list[dict]) -> None:
        values = [list(COLUMNS)] + [
            ["" if r.get(c) is None else r[c] for c in COLUMNS] for r in rows
        ]
        self._ws.update(values, "A1", value_input_option="RAW")
        if self._ws.row_count > len(values):
            last_col = gspread.utils.rowcol_to_a1(1, len(COLUMNS))[:-1]
            self._ws.batch_clear([f"A{len(values) + 1}:{last_col}{self._ws.row_count}"])
