from streamlit.testing.v1 import AppTest


def test_locked_without_password_secret():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=20).run()
    assert any("locked" in e.value for e in at.error)


def test_unlocked_app_renders_table(monkeypatch):
    from app import sheets
    from app.table import new_row

    store = sheets.MemoryStore([new_row("a.pdf", {"seller": "S"})])
    store.url = "https://docs.google.com/spreadsheets/d/x"
    monkeypatch.setattr(sheets, "GoogleSheetStore", lambda *a, **k: store)

    at = AppTest.from_file("../streamlit_app.py", default_timeout=20)
    at.secrets["app_password"] = "pw"
    at.secrets["gcp_service_account"] = {}
    at.secrets["sheet_url"] = store.url
    at.secrets["ANTHROPIC_API_KEY"] = "sk-ant-test"
    at.run()
    at.text_input[0].set_value("pw").run()
    assert not at.exception
    assert len(at.session_state.rows) == 1
    assert at.title[0].value.endswith("Invoice Organizer")
