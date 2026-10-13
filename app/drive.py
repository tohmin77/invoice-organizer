import json
import re
import uuid
from datetime import date

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
ID_PATTERN = re.compile(r"Invoice-(\d+)-\d{6}")
EXTENSIONS = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


class DriveError(Exception):
    pass


def next_invoice_id(rows: list[dict], today: date | None = None) -> str:
    """Sequential ID with the upload date, e.g. Invoice-001-261013."""
    used = 0
    for row in rows:
        match = ID_PATTERN.fullmatch(str(row.get("invoice_id") or ""))
        if match:
            used = max(used, int(match.group(1)))
    return f"Invoice-{used + 1:03d}-{(today or date.today()):%y%m%d}"


def parse_folder_id(value: str) -> str:
    """Accept a bare ID, an ID with URL parameters, or a full folder URL."""
    value = str(value).strip()
    if "/folders/" in value:
        value = value.split("/folders/", 1)[1]
    return re.split(r"[/?&#]", value, maxsplit=1)[0]


def drive_filename(invoice_id: str, media_type: str) -> str:
    return f"{invoice_id}{EXTENSIONS.get(media_type, '')}"


class DriveStore:
    """Uploads files into a Drive folder.

    With `oauth` (client_id, client_secret, refresh_token) files are uploaded as the
    user and count against their storage, so a normal My Drive folder works.
    Otherwise the service account is used, which only works in a Shared Drive.
    """

    def __init__(self, service_account_info: dict | None, folder_id: str, oauth: dict | None = None):
        if oauth:
            creds = UserCredentials(
                None,
                refresh_token=oauth["refresh_token"],
                token_uri=TOKEN_URI,
                client_id=oauth["client_id"],
                client_secret=oauth["client_secret"],
                scopes=SCOPES,
            )
        else:
            creds = Credentials.from_service_account_info(dict(service_account_info), scopes=SCOPES)
        self._session = AuthorizedSession(creds)
        self._folder_id = parse_folder_id(folder_id)

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
