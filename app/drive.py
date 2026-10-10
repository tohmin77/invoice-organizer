import json
import uuid
from datetime import date

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
EXTENSIONS = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


class DriveError(Exception):
    pass


def next_invoice_id(rows: list[dict], today: date | None = None) -> str:
    """Date-based ID, e.g. 20261010-001; the counter restarts each day."""
    prefix = (today or date.today()).strftime("%Y%m%d")
    used = 0
    for row in rows:
        existing = row.get("invoice_id") or ""
        head, _, tail = str(existing).partition("-")
        if head == prefix and tail.isdigit():
            used = max(used, int(tail))
    return f"{prefix}-{used + 1:03d}"


def drive_filename(invoice_id: str, media_type: str) -> str:
    return f"Invoice-{invoice_id}{EXTENSIONS.get(media_type, '')}"


class DriveStore:
    """Uploads files into a folder of a Shared Drive using the service account."""

    def __init__(self, service_account_info: dict, folder_id: str):
        creds = Credentials.from_service_account_info(dict(service_account_info), scopes=SCOPES)
        self._session = AuthorizedSession(creds)
        self._folder_id = folder_id

    def upload(self, name: str, data: bytes, media_type: str) -> str:
        boundary = uuid.uuid4().hex
        metadata = json.dumps({"name": name, "parents": [self._folder_id]})
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
            f"--{boundary}\r\nContent-Type: {media_type}\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--".encode()
        response = self._session.post(
            UPLOAD_URL,
            params={"uploadType": "multipart", "supportsAllDrives": "true", "fields": "webViewLink"},
            data=body,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            timeout=120,
        )
        if response.status_code != 200:
            raise DriveError(f"Drive upload failed ({response.status_code}): {response.text[:200]}")
        return response.json()["webViewLink"]
