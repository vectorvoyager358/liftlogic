"""Google Sheets API client and authentication."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, TypeVar

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from liftlogic.constants import OAUTH_SCOPES

# Sheets can be slow on large batchUpdates; default httplib2 timeout is too tight.
_HTTP_TIMEOUT_SEC = 120
_BATCH_UPDATE_SIZE = 80
_MAX_RETRIES = 4
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

T = TypeVar("T")


class SheetsClient:
    """Thin wrapper around the Google Sheets and Drive APIs."""

    def __init__(self, credentials: Credentials) -> None:
        self._credentials = credentials
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=_HTTP_TIMEOUT_SEC))
        self._sheets = build("sheets", "v4", http=http, cache_discovery=False)
        self._drive = build("drive", "v3", http=http, cache_discovery=False)

    @classmethod
    def from_oauth(cls, credentials_dir: str | Path = "credentials") -> SheetsClient:
        creds = load_oauth_credentials(credentials_dir)
        return cls(creds)

    def create_spreadsheet(self, title: str) -> str:
        body = {"properties": {"title": title}}
        result = self._execute(self._sheets.spreadsheets().create(body=body))
        return result["spreadsheetId"]

    def batch_update(self, spreadsheet_id: str, requests: list[dict[str, Any]]) -> None:
        if not requests:
            return
        for start in range(0, len(requests), _BATCH_UPDATE_SIZE):
            chunk = requests[start : start + _BATCH_UPDATE_SIZE]
            self._execute(
                self._sheets.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": chunk},
                )
            )

    def get_values(self, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
        result = self._execute(
            self._sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name)
        )
        return result.get("values", [])

    def update_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        self._execute(
            self._sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            )
        )

    def append_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
    ) -> None:
        self._execute(
            self._sheets.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            )
        )

    def get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        meta = self._execute(self._sheets.spreadsheets().get(spreadsheetId=spreadsheet_id))
        for sheet in meta.get("sheets", []):
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        raise ValueError(f"Sheet not found: {sheet_name}")

    def get_spreadsheet(
        self,
        spreadsheet_id: str,
        *,
        fields: str | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"spreadsheetId": spreadsheet_id}
        if fields:
            kwargs["fields"] = fields
        return self._execute(self._sheets.spreadsheets().get(**kwargs))

    def clear_values(self, spreadsheet_id: str, range_name: str) -> None:
        self._execute(
            self._sheets.spreadsheets()
            .values()
            .clear(
                spreadsheetId=spreadsheet_id,
                range=range_name,
            )
        )

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

    def _execute(self, request: Any) -> Any:
        return execute_with_retries(request.execute)


def execute_with_retries(
    execute_fn: Callable[[], T],
    *,
    max_retries: int = _MAX_RETRIES,
) -> T:
    """Retry transient network / Sheets API failures with exponential backoff."""
    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return execute_fn()
        except TimeoutError as err:
            last_error = err
        except OSError as err:
            # Includes socket timeouts wrapped as OSError on some platforms.
            last_error = err
        except HttpError as err:
            status = getattr(err.resp, "status", None)
            if status not in _RETRYABLE_STATUS:
                raise
            last_error = err
        if attempt < max_retries - 1:
            time.sleep(1.5 * (2**attempt))
    assert last_error is not None
    raise last_error


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
