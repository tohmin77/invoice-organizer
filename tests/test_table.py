import csv
import io

from app.table import apply_edits, build_csv, new_row, rows_to_df

FULL = {"purchaser": "P", "seller": "S", "items": "x", "amount": 10.0, "gst": 1.0, "date": "2026-01-02"}


def make_rows():
    return [new_row("a.pdf", FULL), new_row("b.pdf", {**FULL, "seller": "S2"}), new_row("c.pdf", {})]


def test_rows_to_df_flags_review():
    df = rows_to_df(make_rows())
    assert list(df["review"]) == ["", "", "⚠️"]


def test_edit_cell_and_delete_row():
    rows = make_rows()
    df = rows_to_df(rows).iloc[:2].copy()
    df.loc[0, "seller"] = "Changed"
    df = df.drop(index=1)
    result, errors = apply_edits(rows, {r["id"] for r in rows}, df)
    assert errors == []
    assert [r["seller"] for r in result][:1] == ["Changed"]
    assert len(result) == 1


def test_hidden_rows_survive_filtered_edit():
    rows = make_rows()
    shown = rows[2:]
    df = rows_to_df(shown)
    df.loc[0, "purchaser"] = "Fixed"
    result, errors = apply_edits(rows, {shown[0]["id"]}, df)
    assert errors == []
    assert [r["filename"] for r in result] == ["a.pdf", "b.pdf", "c.pdf"]
    assert result[2]["purchaser"] == "Fixed"
    assert result[0] == rows[0]


def test_new_row_added_and_blank_ignored():
    rows = make_rows()
    df = rows_to_df(rows)
    df.loc[len(df)] = ["", None, None, "Me", "Shop", None, 5.0, None, "2026-02-03", None]
    df.loc[len(df)] = ["", None, None, None, None, None, None, None, None, None]
    result, errors = apply_edits(rows, {r["id"] for r in rows}, df)
    assert errors == []
    assert len(result) == 4
    assert result[3]["filename"] == "manual entry" and result[3]["amount"] == 5.0


def test_invalid_values_rejected():
    rows = make_rows()
    df = rows_to_df(rows)
    df.loc[0, "date"] = "03/04/2026"
    result, errors = apply_edits(rows, {r["id"] for r in rows}, df)
    assert result is None and "Row 1" in errors[0]


def test_csv_formula_guard():
    rows = [new_row("a.pdf", {**FULL, "seller": "=HYPERLINK(1)", "amount": -5.0})]
    out = list(csv.reader(io.StringIO(build_csv(rows))))
    assert out[0] == ["filename", "purchaser", "seller", "items", "amount", "gst", "date"]
    assert out[1][2] == "'=HYPERLINK(1)" and out[1][4] == "-5.0"
