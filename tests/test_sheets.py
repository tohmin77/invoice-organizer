from app.sheets import GoogleSheetStore, MemoryStore
from app.table import COLUMNS, new_row


def test_memory_store_roundtrip():
    store = MemoryStore()
    rows = [new_row("a.pdf", {"seller": "S", "amount": 1.0})]
    store.save(rows)
    loaded = store.load()
    assert loaded == rows and loaded is not store.rows


class FakeWorksheet:
    def __init__(self, values, row_count=10):
        self.values, self.row_count, self.cleared, self.written = values, row_count, [], None

    def get_all_values(self, value_render_option=None):
        return self.values

    def update(self, values, cell, value_input_option=None):
        self.written = (values, cell, value_input_option)

    def batch_clear(self, ranges):
        self.cleared = ranges


def store_with(ws):
    s = GoogleSheetStore.__new__(GoogleSheetStore)
    s._ws = ws
    return s


def test_load_parses_numbers_and_blanks():
    header = list(COLUMNS)
    data = ["abc123", "a.pdf", "P", "S", "", 12.5, "", "2026-01-02", "2026-01-03 10:00"]
    rows = store_with(FakeWorksheet([header, data])).load()
    assert rows[0]["amount"] == 12.5 and rows[0]["gst"] is None
    assert rows[0]["items"] is None and rows[0]["id"] == "abc123"


def test_load_ignores_sheet_without_expected_header():
    assert store_with(FakeWorksheet([["foo", "bar"]])).load() == []
    assert store_with(FakeWorksheet([])).load() == []


def test_save_writes_raw_and_clears_leftover_rows():
    ws = FakeWorksheet([], row_count=10)
    rows = [new_row("a.pdf", {"seller": "=1+1"})]
    store_with(ws).save(rows)
    values, cell, mode = ws.written
    assert mode == "RAW" and cell == "A1"
    assert values[0] == list(COLUMNS) and values[1][3] == "=1+1"
    assert ws.cleared == ["A3:K10"]


def test_load_old_sheet_without_new_columns():
    header = list(COLUMNS[:9])
    data = ["abc123", "a.pdf", "P", "S", "", 12.5, "", "2026-01-02", "2026-01-03 10:00"]
    rows = store_with(FakeWorksheet([header, data])).load()
    assert rows[0]["id"] == "abc123" and rows[0]["invoice_id"] is None and rows[0]["drive_url"] is None
