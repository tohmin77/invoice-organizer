from datetime import date as _date

from pydantic import BaseModel, field_validator

FIELDS = ("purchaser", "seller", "items", "amount", "gst", "date")


def _valid_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


class InvoiceData(BaseModel):
    purchaser: str | None = None
    seller: str | None = None
    items: str | None = None
    amount: float | None = None
    gst: float | None = None
    date: str | None = None

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str | None) -> str | None:
        return _valid_iso_date(v)


class InvoiceUpdate(InvoiceData):
    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str | None) -> str | None:
        if v is not None and v.strip() and _valid_iso_date(v) is None:
            raise ValueError("date must be YYYY-MM-DD")
        return _valid_iso_date(v)
