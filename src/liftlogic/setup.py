"""Spreadsheet bootstrap — creates and configures the LiftLogic workbook."""

from __future__ import annotations

from typing import Any

from liftlogic.constants import (
    AI_INSIGHTS_SHEET,
    ANALYTICS_SHEET,
    DASHBOARD_SHEET,
    DATA_START_ROW,
    EXERCISE_COLUMNS,
    EXERCISES_SHEET,
    HIDDEN_SHEETS,
    MUSCLE_TABS,
    SETTINGS_ROWS,
    SETTINGS_SHEET,
    SPREADSHEET_TITLE,
    WORKOUT_ENTRY_COLUMNS,
    WORKOUT_LOG_COLUMNS,
    WORKOUT_LOG_SHEET,
)
from liftlogic.exercises import exercise_rows, exercises_for_muscle
from liftlogic.sheets.client import SheetsClient


def setup_spreadsheet(
    client: SheetsClient,
    spreadsheet_id: str | None = None,
    title: str = SPREADSHEET_TITLE,
) -> str:
    """Create or configure a LiftLogic workbook."""
    if spreadsheet_id is None:
        spreadsheet_id = client.create_spreadsheet(title)

    create_sheets(client, spreadsheet_id)
    create_exercise_database(client, spreadsheet_id)
    create_settings(client, spreadsheet_id)
    create_workout_log(client, spreadsheet_id)
    create_workout_tabs(client, spreadsheet_id)
    create_dashboard(client, spreadsheet_id)
    create_analytics_tab(client, spreadsheet_id)
    hide_internal_sheets(client, spreadsheet_id)
    return spreadsheet_id


def create_sheets(client: SheetsClient, spreadsheet_id: str) -> None:
    """Ensure all required tabs exist."""
    meta = client._sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}

    requests: list[dict[str, Any]] = []
    for sheet_name in [DASHBOARD_SHEET, *MUSCLE_TABS, *HIDDEN_SHEETS]:
        if sheet_name not in existing:
            requests.append({"addSheet": {"properties": {"title": sheet_name}}})

    client.batch_update(spreadsheet_id, requests)


def create_exercise_database(client: SheetsClient, spreadsheet_id: str) -> None:
    values = [EXERCISE_COLUMNS, *exercise_rows()]
    client.update_values(spreadsheet_id, f"{EXERCISES_SHEET}!A1", values)


def create_settings(client: SheetsClient, spreadsheet_id: str) -> None:
    values = [["Setting", "Value"], *list(SETTINGS_ROWS)]
    client.update_values(spreadsheet_id, f"{SETTINGS_SHEET}!A1", values)


def create_workout_log(client: SheetsClient, spreadsheet_id: str) -> None:
    client.update_values(
        spreadsheet_id,
        f"{WORKOUT_LOG_SHEET}!A1",
        [WORKOUT_LOG_COLUMNS],
    )


def create_workout_tabs(client: SheetsClient, spreadsheet_id: str) -> None:
    requests: list[dict[str, Any]] = []

    for muscle in MUSCLE_TABS:
        client.update_values(
            spreadsheet_id,
            f"{muscle}!A1",
            [WORKOUT_ENTRY_COLUMNS],
        )
        exercise_names = [ex.name for ex in exercises_for_muscle(muscle)]
        if not exercise_names:
            continue

        sheet_id = _sheet_id(client, spreadsheet_id, muscle)
        requests.append(
            _dropdown_validation_request(
                sheet_id=sheet_id,
                column_index=1,
                options=exercise_names,
            )
        )

    client.batch_update(spreadsheet_id, requests)


def create_dashboard(client: SheetsClient, spreadsheet_id: str) -> None:
    """Write dashboard layout and formula-driven summary cells."""
    values = [
        ["LiftLogic Dashboard"],
        [],
        ["Overall Statistics"],
        [
            "Total Workouts",
            '=IFERROR(COUNTA(UNIQUE(FILTER(Workout_Log!B2:B,Workout_Log!B2:B<>""))),0)',
        ],
        [
            "Workouts This Week",
            '=IFERROR(COUNTA(UNIQUE(FILTER(Workout_Log!B2:B,(Workout_Log!B2:B<>"")*(Workout_Log!B2:B>=TODAY()-WEEKDAY(TODAY())+1)))),0)',
        ],
        [
            "Workouts This Month",
            '=IFERROR(COUNTA(UNIQUE(FILTER(Workout_Log!B2:B,(Workout_Log!B2:B<>"")*(MONTH(Workout_Log!B2:B)=MONTH(TODAY()))*(YEAR(Workout_Log!B2:B)=YEAR(TODAY()))))),0)',
        ],
        [],
        ["Personal Records"],
        ["Exercise", "Best Weight", "Date Achieved"],
        [
            "=IFERROR(QUERY(Workout_Log!B2:G,\"SELECT Col4, MAX(Col5), MAX(Col1) WHERE Col5 IS NOT NULL GROUP BY Col4 ORDER BY MAX(Col5) DESC LABEL Col4 'Exercise', MAX(Col5) 'Best Weight', MAX(Col1) 'Date'\",0),\"\")",
        ],
        [],
        ["Recent Activity"],
        ["Date", "Muscle", "Exercise", "Weight", "Notes"],
        [
            "=IFERROR(QUERY(Workout_Log!B2:G,\"SELECT Col1, Col2, Col4, Col5, Col6 WHERE Col1 IS NOT NULL ORDER BY Col1 DESC LIMIT 10 LABEL Col1 'Date', Col2 'Muscle', Col4 'Exercise', Col5 'Weight', Col6 'Notes'\",0),\"\")",
        ],
    ]
    client.update_values(spreadsheet_id, f"{DASHBOARD_SHEET}!A1", values)


def create_analytics_tab(client: SheetsClient, spreadsheet_id: str) -> None:
    values = [
        ["Analytics (populated by backend in Phase 2)"],
        ["Metric", "Value"],
    ]
    client.update_values(spreadsheet_id, f"{ANALYTICS_SHEET}!A1", values)
    client.update_values(
        spreadsheet_id,
        f"{AI_INSIGHTS_SHEET}!A1",
        [["AI Insights (Phase 3+)"]],
    )


def hide_internal_sheets(client: SheetsClient, spreadsheet_id: str) -> None:
    requests: list[dict[str, Any]] = []
    for sheet_name in HIDDEN_SHEETS:
        sheet_id = _sheet_id(client, spreadsheet_id, sheet_name)
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "hidden": True},
                    "fields": "hidden",
                }
            }
        )
    client.batch_update(spreadsheet_id, requests)


def _dropdown_validation_request(
    sheet_id: int,
    column_index: int,
    options: list[str],
) -> dict[str, Any]:
    return {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": DATA_START_ROW - 1,
                "endRowIndex": 1000,
                "startColumnIndex": column_index,
                "endColumnIndex": column_index + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": option} for option in options],
                },
                "showCustomUi": True,
                "strict": False,
            },
        }
    }


def _sheet_id(client: SheetsClient, spreadsheet_id: str, title: str) -> int:
    meta = client._sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] == title:
            return sheet["properties"]["sheetId"]
    raise ValueError(f"Sheet not found: {title}")
