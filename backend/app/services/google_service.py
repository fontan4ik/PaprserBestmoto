import base64
import json
from datetime import datetime
from typing import Any, List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import settings
from ..core.logging import get_logger
from ..models import ParsingTask

logger = get_logger("google_sheets")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _load_credentials() -> Credentials:
    raw = settings.google_credentials
    if not raw:
        raise RuntimeError("GOOGLE_CREDENTIALS env not configured.")
    if raw.strip().startswith("{"):
        info = json.loads(raw)
    else:
        info = json.loads(base64.b64decode(raw).decode("utf-8"))
    return Credentials.from_service_account_info(info, scopes=SCOPES)


class GoogleSheetsService:
    def __init__(self):
        credentials = _load_credentials()
        self.sheets = build(
            "sheets", "v4", credentials=credentials, cache_discovery=False
        )
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self.service_account_email = settings.google_service_account_email

    def ensure_access(self, sheet_id: str) -> None:
        try:
            self.drive.permissions().create(
                fileId=sheet_id,
                body={
                    "type": "user",
                    "role": "writer",
                    "emailAddress": self.service_account_email,
                },
                sendNotificationEmail=False,
            ).execute()
        except HttpError as exc:
            if exc.resp.status not in (403, 404):
                raise
            raise

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
    def export_task(
        self, task: ParsingTask, sheet_id: str, sheet_tab: str, rows: List[List[Any]]
    ) -> None:
        if not rows:
            rows = [["Нет данных для экспорта"]]
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        tab_name = sheet_tab or f"Export_{timestamp}"

        self.ensure_access(sheet_id)
        sheet_identifier = None
        try:
            response = (
                self.sheets.spreadsheets()
                .batchUpdate(
                    spreadsheetId=sheet_id,
                    body={
                        "requests": [
                            {
                                "addSheet": {
                                    "properties": {
                                        "title": tab_name,
                                        "gridProperties": {"frozenRowCount": 1},
                                    }
                                }
                            }
                        ]
                    },
                )
                .execute()
            )
            sheet_identifier = response["replies"][0]["addSheet"]["properties"]["sheetId"]
        except HttpError as exc:
            if exc.resp.status == 400:
                metadata = (
                    self.sheets.spreadsheets()
                    .get(spreadsheetId=sheet_id)
                    .execute()
                    .get("sheets", [])
                )
                for sheet in metadata:
                    if sheet["properties"]["title"] == tab_name:
                        sheet_identifier = sheet["properties"]["sheetId"]
                        break
                self.sheets.spreadsheets().values().clear(
                    spreadsheetId=sheet_id, range=f"{tab_name}!A:ZZ"
                ).execute()
            else:
                raise

        self.sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()

        if sheet_identifier is not None:
            requests = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_identifier,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_identifier,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                        }
                    }
                },
            ]

            self.sheets.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id, body={"requests": requests}
            ).execute()

