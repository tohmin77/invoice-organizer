import sqlite3
from contextlib import closing
from pathlib import Path

from .schemas import FIELDS

COLUMNS = ("id", "filename", *FIELDS, "created_at")

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    purchaser TEXT,
    seller TEXT,
    items TEXT,
    amount REAL,
    gst REAL,
    date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(path)) as conn, conn:
        conn.execute(SCHEMA)


def add_invoice(path: Path, filename: str, data: dict) -> dict:
    values = [data.get(f) for f in FIELDS]
    with closing(_connect(path)) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO invoices (filename, {', '.join(FIELDS)}) "
            f"VALUES (?, {', '.join('?' * len(FIELDS))})",
            [filename, *values],
        )
        return _get(conn, cur.lastrowid)


def _get(conn: sqlite3.Connection, invoice_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    return dict(row) if row else None


def list_invoices(path: Path) -> list[dict]:
    with closing(_connect(path)) as conn:
        rows = conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def update_invoice(path: Path, invoice_id: int, changes: dict) -> dict | None:
    changes = {k: v for k, v in changes.items() if k in FIELDS}
    with closing(_connect(path)) as conn, conn:
        if changes:
            assignments = ", ".join(f"{k} = ?" for k in changes)
            conn.execute(
                f"UPDATE invoices SET {assignments} WHERE id = ?",
                [*changes.values(), invoice_id],
            )
        return _get(conn, invoice_id)


def delete_invoice(path: Path, invoice_id: int) -> bool:
    with closing(_connect(path)) as conn, conn:
        cur = conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        return cur.rowcount > 0
