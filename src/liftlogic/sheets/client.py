"""Google Sheets API client and authentication."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from liftlogic.constants import OAUTH_SCOPES


class SheetsClient:
    """Thin wrapper around the Google Sheets and Drive APIs."""

    def __init__(self, credentials: Credentials) -> None:
        self._credentials = credentials
        self._sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._drive = build("drive", "v3", credentials=credentials, cache_discovery=False)

    @classmethod
    def from_oauth(cls, credentials_dir: str | Path = "credentials") -> SheetsClient:
        creds = load_oauth_credentials(credentials_dir)
        return cls(creds)

    def create_spreadsheet(self, title: str) -> str:
        body = {"properties": {"title": title}}
        result = self._sheets.spreadsheets().create(body=body).execute()
        return result["spreadsheetId"]

    def batch_update(self, spreadsheet_id: str, requests: list[dict[str, Any]]) -> None:
        if not requests:
            return
        self._sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

    def get_values(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
        result = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])

    def update_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        self._sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    def append_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        self._sheets.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()

    def get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        meta = self._sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sheet in meta.get("sheets", []):
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        raise ValueError(f"Sheet not found: {sheet_name}")

    def delete_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row_indices_1based: list[int],
    ) -> None:
        if not row_indices_1based:
            return

        sheet_id = self.get_sheet_id(spreadsheet_id, sheet_name)
        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row - 1,
                        "endIndex": row,
                    }
                }
            }
            for row in sorted(row_indices_1based, reverse=True)
        ]
        self.batch_update(spreadsheet_id, requests)


def load_oauth_credentials(credentials_dir: str | Path = "credentials") -> Credentials:
    base = Path(credentials_dir)
    token_path = base / "token.json"
    client_secrets_path = base / "client_secret.json"

    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), OAUTH_SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
        return creds

    if not client_secrets_path.exists():
        raise FileNotFoundError(
            f"Missing OAuth client secrets at {client_secrets_path}. "
            "Download from Google Cloud Console and save as credentials/client_secret.json"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), OAUTH_SCOPES)
    creds = flow.run_local_server(port=0)
    base.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds
