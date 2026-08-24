"""Spreadsheet bootstrap — creates and configures the LiftLogic workbook."""

from __future__ import annotations

from typing import Any

from liftlogic.constants import (
    AI_INSIGHTS_SHEET,
    ANALYTICS_SHEET,
    ANALYTICS_SECTION_NAMES,
    ANALYTICS_TABLE_HEADERS,
    DASHBOARD_SHEET,
    DASHBOARD_SEARCH_HINT,
    DATA_START_ROW,
    DASHBOARD_MUSCLE_FILTER_OPTIONS,
    DASHBOARD_VIEW_OPTIONS,
    EXERCISE_COLUMNS,
    EXERCISES_SHEET,
    GOAL_COLUMNS,
    GOAL_STATUS_OPTIONS,
    GOAL_TYPES,
    GOAL_UNITS,
    GOALS_SHEET,
    HIDDEN_SHEETS,
    MUSCLE_TABS,
    SETTINGS_ROWS,
    SETTINGS_SHEET,
    SPREADSHEET_TITLE,
    WORKOUT_ENTRY_COLUMNS,
    WORKOUT_LOG_COLUMNS,
    WORKOUT_LOG_SHEET,
)
from liftlogic.exercises import DEFAULT_EXERCISES, exercise_rows, exercises_for_muscle
from liftlogic.sheets.client import SheetsClient

# ---------------------------------------------------------------------------
# Color palette — premium slate + emerald accent
# ---------------------------------------------------------------------------

_TITLE_BG = "#0F172A"  # slate-900
_TITLE_FG = "#FFFFFF"
_SUBTITLE_BG = "#1E293B"  # slate-800
_SUBTITLE_FG = "#94A3B8"  # slate-400
_ACCENT_BG = "#10B981"  # emerald-500
_ACCENT_FG = "#FFFFFF"
_SECTION_BG = "#0F172A"
_SECTION_FG = "#FFFFFF"
_TABLE_HDR_BG = "#0F172A"
_TABLE_HDR_FG = "#FFFFFF"
_KPI_LABEL_BG = "#F1F5F9"  # slate-100
_KPI_LABEL_FG = "#64748B"  # slate-500
_KPI_VALUE_BG = "#FFFFFF"
_KPI_VALUE_FG = "#0F172A"  # slate-900
_STAT_LABEL_BG = "#F8FAFC"
_STAT_VALUE_BG = "#FFFFFF"
_ALT_ROW_BG = "#F8FAFC"
_BORDER_COLOR = "#E2E8F0"
_SHEET_BG = "#FFFFFF"

# Muscle tab colors: (tab hex, header-row bg hex, header text hex)
_MUSCLE_COLORS: dict[str, tuple[str, str, str]] = {
    "Chest": ("#E53935", "#FFCDD2", "#B71C1C"),
    "Back": ("#1E88E5", "#BBDEFB", "#0D47A1"),
    "Shoulders": ("#43A047", "#C8E6C9", "#1B5E20"),
    "Biceps": ("#FB8C00", "#FFE0B2", "#E65100"),
    "Triceps": ("#8E24AA", "#E1BEE7", "#4A148C"),
    "Legs": ("#00ACC1", "#B2EBF2", "#006064"),
    "Cardio": ("#F4511E", "#FFCCBC", "#BF360C"),
}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


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
    create_goals_tab(client, spreadsheet_id)
    format_dashboard(client, spreadsheet_id)
    create_analytics_tab(client, spreadsheet_id)
    format_workout_tabs(client, spreadsheet_id)
    format_goals_tab(client, spreadsheet_id)
    format_analytics_tab(client, spreadsheet_id)
    hide_internal_sheets(client, spreadsheet_id)
    return spreadsheet_id


def format_dashboard(client: SheetsClient, spreadsheet_id: str) -> None:
    """Rewrite Dashboard content and apply full visual formatting.

    Safe to run on existing sheets — only the Dashboard tab is touched.
    Workout data in muscle tabs is never modified.
    """
    _unmerge_dashboard(client, spreadsheet_id)
    client.clear_values(spreadsheet_id, f"{DASHBOARD_SHEET}!A:Z")
    _write_dashboard_content(client, spreadsheet_id)
    _apply_dashboard_formatting(client, spreadsheet_id)
    _create_dashboard_validations(client, spreadsheet_id)


def format_workout_tabs(client: SheetsClient, spreadsheet_id: str) -> None:
    """Apply colours and formatting to every muscle tab.

    Only changes visual formatting — never overwrites workout data.
    Reapplies exercise dropdowns from the Exercises sheet (same list as sidebar).
    """
    requests: list[dict[str, Any]] = []
    exercise_names_by_muscle = _exercise_names_by_muscle_from_sheet(client, spreadsheet_id)

    for muscle in MUSCLE_TABS:
        colors = _MUSCLE_COLORS.get(muscle)
        if not colors:
            continue
        tab_hex, hdr_bg_hex, hdr_fg_hex = colors
        try:
            sheet_id = _sheet_id(client, spreadsheet_id, muscle)
        except ValueError:
            continue

        # Tab colour
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "tabColorStyle": {"rgbColor": _rgb(tab_hex)},
                    },
                    "fields": "tabColorStyle",
                }
            }
        )

        # Freeze header row
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )

        # Header row (row 0) background + bold white text
        requests.append(
            _format_range(
                sheet_id,
                0,
                1,
                0,
                6,
                bg=hdr_bg_hex,
                fg=hdr_fg_hex,
                bold=True,
                font_size=10,
            )
        )

        # Column widths: Date=100, Exercise=200, Weight=90, Notes=220
        for col_idx, px in [(0, 100), (1, 200), (2, 90), (3, 220)]:
            requests.append(_col_width(sheet_id, col_idx, px))

        # Date column: calendar picker + yyyy-mm-dd display
        requests.append(_date_format_request(sheet_id, column_index=0))
        requests.append(_date_validation_request(sheet_id, column_index=0))

        # Exercise dropdown — same catalog as Exercises sheet / sidebar
        exercise_names = exercise_names_by_muscle.get(muscle) or [
            ex.name for ex in exercises_for_muscle(muscle)
        ]
        if exercise_names:
            requests.append(
                _dropdown_validation_request(
                    sheet_id=sheet_id,
                    column_index=1,
                    options=exercise_names,
                )
            )

    client.batch_update(spreadsheet_id, requests)


def _exercise_names_by_muscle_from_sheet(
    client: SheetsClient, spreadsheet_id: str
) -> dict[str, list[str]]:
    """Read Exercises sheet; fall back to seed catalog per muscle if empty."""
    grouped: dict[str, list[str]] = {m: [] for m in MUSCLE_TABS}
    rows = client.get_values(spreadsheet_id, f"{EXERCISES_SHEET}!A2:C")
    for row in rows:
        padded = list(row) + [""] * 3
        name = str(padded[1]).strip()
        muscle = str(padded[2]).strip()
        if name and muscle in grouped:
            grouped[muscle].append(name)
    for muscle in MUSCLE_TABS:
        if grouped[muscle]:
            grouped[muscle] = sorted(set(grouped[muscle]))
        else:
            grouped[muscle] = [ex.name for ex in exercises_for_muscle(muscle)]
    return grouped


def format_analytics_tab(client: SheetsClient, spreadsheet_id: str) -> None:
    """Unhide the Analytics tab and apply styling.

    Uses conditional formatting so section headers stay styled regardless of
    how many PRs or muscle groups exist (the row positions shift with data).
    Safe to run multiple times — each call replaces the previous rule set.
    """
    sheet_id = _sheet_id(client, spreadsheet_id, ANALYTICS_SHEET)
    requests: list[dict[str, Any]] = []

    # Unhide + tab colour (sky blue)
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "hidden": False,
                    "tabColorStyle": {"rgbColor": _rgb("#0288D1")},
                },
                "fields": "hidden,tabColorStyle",
            }
        }
    )

    # Freeze title row
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }
    )

    # Title row (row 0) — always fixed
    requests.append(
        _format_range(sheet_id, 0, 1, 0, 5, bg=_TITLE_BG, fg=_TITLE_FG, bold=True, font_size=14)
    )

    # Column widths: Label=200, Value=110, Unit/Extra=90, Date=110, Detail=340
    for col_idx, px in [(0, 200), (1, 110), (2, 90), (3, 110), (4, 340)]:
        requests.append(_col_width(sheet_id, col_idx, px))

    client.batch_update(spreadsheet_id, requests)

    # Conditional formatting (separate batch — avoids index conflicts)
    _apply_analytics_conditional_formats(client, spreadsheet_id, sheet_id)


def _apply_analytics_conditional_formats(
    client: SheetsClient, spreadsheet_id: str, sheet_id: int
) -> None:
    """Replace all conditional format rules on the Analytics tab."""
    # First, delete every existing rule (fetch current count)
    meta = client._sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    rule_count = 0
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["sheetId"] == sheet_id:
            rule_count = len(sheet.get("conditionalFormats", []))
            break

    delete_requests: list[dict[str, Any]] = [
        {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}}
        for _ in range(rule_count)
    ]
    if delete_requests:
        client.batch_update(spreadsheet_id, delete_requests)

    # Data range (skip title row)
    data_range = {
        "sheetId": sheet_id,
        "startRowIndex": 1,
        "endRowIndex": 300,
        "startColumnIndex": 0,
        "endColumnIndex": 5,
    }

    section_formula = "=OR(" + ",".join(f'$A1="{s}"' for s in ANALYTICS_SECTION_NAMES) + ")"
    table_formula = "=OR(" + ",".join(f'$A1="{h}"' for h in ANALYTICS_TABLE_HEADERS) + ")"
    even_row_formula = '=AND(ISEVEN(ROW()),$A1<>"")'

    add_requests: list[dict[str, Any]] = [
        # Rule 0: Section headers → dark blue bg, white bold
        # Note: ConditionalFormatRule.format does not support fontSize
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [data_range],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": section_formula}],
                        },
                        "format": {
                            "backgroundColor": _rgb(_SECTION_BG),
                            "textFormat": {
                                "foregroundColor": _rgb(_SECTION_FG),
                                "bold": True,
                            },
                        },
                    },
                },
                "index": 0,
            }
        },
        # Rule 1: Table headers → light indigo bg, dark bold
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [data_range],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": table_formula}],
                        },
                        "format": {
                            "backgroundColor": _rgb(_TABLE_HDR_BG),
                            "textFormat": {
                                "foregroundColor": _rgb(_TABLE_HDR_FG),
                                "bold": True,
                            },
                        },
                    },
                },
                "index": 1,
            }
        },
        # Rule 2: Alternating even rows → off-white
        {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [data_range],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": even_row_formula}],
                        },
                        "format": {"backgroundColor": _rgb(_ALT_ROW_BG)},
                    },
                },
                "index": 2,
            }
        },
    ]
    client.batch_update(spreadsheet_id, add_requests)


# ---------------------------------------------------------------------------
# Sheet creation helpers (called by setup_spreadsheet)
# ---------------------------------------------------------------------------


def create_sheets(client: SheetsClient, spreadsheet_id: str) -> None:
    """Ensure all required tabs exist."""
    meta = client._sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}

    requests: list[dict[str, Any]] = []
    for sheet_name in [DASHBOARD_SHEET, *MUSCLE_TABS, GOALS_SHEET, *HIDDEN_SHEETS]:
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
    exercise_names_by_muscle = _exercise_names_by_muscle_from_sheet(client, spreadsheet_id)

    for muscle in MUSCLE_TABS:
        client.update_values(
            spreadsheet_id,
            f"{muscle}!A1",
            [WORKOUT_ENTRY_COLUMNS],
        )
        exercise_names = exercise_names_by_muscle.get(muscle) or []
        sheet_id = _sheet_id(client, spreadsheet_id, muscle)
        requests.append(_date_format_request(sheet_id, column_index=0))
        requests.append(_date_validation_request(sheet_id, column_index=0))
        if exercise_names:
            requests.append(
                _dropdown_validation_request(
                    sheet_id=sheet_id,
                    column_index=1,
                    options=exercise_names,
                )
            )

    client.batch_update(spreadsheet_id, requests)


def create_goals_tab(client: SheetsClient, spreadsheet_id: str) -> None:
    client.update_values(
        spreadsheet_id,
        f"{GOALS_SHEET}!A1",
        [GOAL_COLUMNS],
    )

    sheet_id = _sheet_id(client, spreadsheet_id, GOALS_SHEET)
    exercise_names = [ex.name for ex in DEFAULT_EXERCISES]
    requests: list[dict[str, Any]] = [
        _dropdown_validation_request(sheet_id=sheet_id, column_index=1, options=GOAL_TYPES),
        _dropdown_validation_request(sheet_id=sheet_id, column_index=2, options=exercise_names),
        _dropdown_validation_request(sheet_id=sheet_id, column_index=3, options=MUSCLE_TABS),
        _dropdown_validation_request(sheet_id=sheet_id, column_index=5, options=GOAL_UNITS),
        _date_format_request(sheet_id, column_index=6),
        _date_validation_request(sheet_id, column_index=6),
        _dropdown_validation_request(
            sheet_id=sheet_id, column_index=7, options=GOAL_STATUS_OPTIONS
        ),
    ]
    client.batch_update(spreadsheet_id, requests)


def format_goals_tab(client: SheetsClient, spreadsheet_id: str) -> None:
    """Apply colours and formatting to the Goals tab."""
    try:
        sheet_id = _sheet_id(client, spreadsheet_id, GOALS_SHEET)
    except ValueError:
        return

    hdr_bg = "#FFF9C4"
    hdr_fg = "#F57F17"
    requests: list[dict[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "tabColorStyle": {"rgbColor": _rgb("#F9A825")},
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "tabColorStyle,gridProperties.frozenRowCount",
            }
        },
        _format_range(sheet_id, 0, 1, 0, 9, bg=hdr_bg, fg=hdr_fg, bold=True, font_size=10),
    ]

    for col_idx, px in [
        (0, 80),  # Goal ID
        (1, 90),  # Type
        (2, 200),  # Exercise
        (3, 100),  # Muscle
        (4, 80),  # Target
        (5, 110),  # Unit
        (6, 110),  # Target Date
        (7, 90),  # Status
        (8, 220),  # Notes
    ]:
        requests.append(_col_width(sheet_id, col_idx, px))

    client.batch_update(spreadsheet_id, requests)


def create_analytics_tab(client: SheetsClient, spreadsheet_id: str) -> None:
    values = [
        ["Analytics (populated by liftlogic refresh)"],
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


# ---------------------------------------------------------------------------
# Dashboard — interactive workout tracker (data via Apps Script)
# ---------------------------------------------------------------------------
#
# Layout (0-based row → sheet row):
#  Row 0  : Title — "LiftLogic — Workout Tracker"           (merged A:L)
#  Row 1  : Subtitle — live sync status                     (merged A:L)
#  Row 2  : Filter controls (muscle, view, search, exercise)
#  Row 3  : spacer
#  Row 4  : KPI labels
#  Row 5  : KPI values (Apps Script refreshDashboard)
#  Row 6  : Section title (Apps Script)
#  Row 7  : Table headers (Apps Script)
#  Row 8+ : Table data (Apps Script)
#
# ---------------------------------------------------------------------------

_DASHBOARD_WIDTH = 12  # columns A–L
_DASHBOARD_DATA_ROWS = 100


def _write_dashboard_content(client: SheetsClient, spreadsheet_id: str) -> None:
    """Write dashboard shell — controls, KPI placeholders, and instructions."""
    blank = [""] * _DASHBOARD_WIDTH
    # Compact filter row: label|value pairs packed left-to-right
    control_row = list(blank)
    control_row[0] = "MUSCLE"
    control_row[1] = "All"
    control_row[2] = "VIEW"
    control_row[3] = "Summary"
    control_row[4] = "SEARCH"
    control_row[5] = ""  # empty — Sheets has no real placeholders; hint is a cell note
    control_row[7] = "EXERCISE"
    control_row[8] = "All"

    kpi_labels = list(blank)
    kpi_labels[1] = "EXERCISES"
    kpi_labels[4] = "LOG ENTRIES"
    kpi_labels[7] = "TOP LIFT (LB)"

    kpi_values = list(blank)
    kpi_values[1] = 0
    kpi_values[4] = 0
    kpi_values[7] = "—"
    kpi_values[9] = ""  # top-lift exercise (inside card)

    values: list[list[Any]] = [
        ["LiftLogic — Workout Tracker"],
        ["Live · open the sheet or use LiftLogic menu → Refresh Dashboard"],
        control_row,
        blank,
        kpi_labels,
        kpi_values,
        ["Summary — all muscles"],
        ["Exercise", "Best", "Unit", "Date", "Notes", ""],
        *[[""] * _DASHBOARD_WIDTH for _ in range(_DASHBOARD_DATA_ROWS)],
    ]
    client.update_values(spreadsheet_id, f"{DASHBOARD_SHEET}!A1", values)


def _create_dashboard_validations(client: SheetsClient, spreadsheet_id: str) -> None:
    sheet_id = _sheet_id(client, spreadsheet_id, DASHBOARD_SHEET)
    requests: list[dict[str, Any]] = [
        _dropdown_validation_request(
            sheet_id=sheet_id,
            column_index=1,
            options=list(DASHBOARD_MUSCLE_FILTER_OPTIONS),
            start_row=3,
            end_row=3,
        ),
        _dropdown_validation_request(
            sheet_id=sheet_id,
            column_index=3,
            options=list(DASHBOARD_VIEW_OPTIONS),
            start_row=3,
            end_row=3,
        ),
        _dropdown_validation_request(
            sheet_id=sheet_id,
            column_index=8,
            options=["All"],
            start_row=3,
            end_row=3,
        ),
    ]
    client.batch_update(spreadsheet_id, requests)


def _apply_dashboard_formatting(client: SheetsClient, spreadsheet_id: str) -> None:
    sheet_id = _sheet_id(client, spreadsheet_id, DASHBOARD_SHEET)
    requests: list[dict[str, Any]] = []
    w = _DASHBOARD_WIDTH

    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"hideGridlines": True, "frozenRowCount": 8},
                },
                "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount",
            }
        }
    )

    # Hero title
    requests.append(_merge_cells(sheet_id, 0, 1, 0, w))
    requests.append(
        _format_range(
            sheet_id,
            0,
            1,
            0,
            w,
            bg=_TITLE_BG,
            fg=_TITLE_FG,
            bold=True,
            font_size=20,
            h_align="LEFT",
            v_align="MIDDLE",
        )
    )
    requests.append(_row_height(sheet_id, 0, 48))

    # Subtitle
    requests.append(_merge_cells(sheet_id, 1, 2, 0, w))
    requests.append(
        _format_range(
            sheet_id,
            1,
            2,
            0,
            w,
            bg=_SUBTITLE_BG,
            fg=_SUBTITLE_FG,
            italic=True,
            font_size=9,
            h_align="LEFT",
            v_align="MIDDLE",
        )
    )
    requests.append(_row_height(sheet_id, 1, 22))

    # Control bar (row 2) — packed label|value pairs
    requests.append(
        _format_range(
            sheet_id,
            2,
            3,
            0,
            w,
            bg="#E2E8F0",
            fg="#334155",
            bold=True,
            font_size=9,
            v_align="MIDDLE",
        )
    )
    # Accent strip on left edge of filter bar
    requests.append(
        _format_range(
            sheet_id,
            2,
            3,
            0,
            1,
            bg=_ACCENT_BG,
            fg=_ACCENT_FG,
            bold=True,
            font_size=9,
            v_align="MIDDLE",
            h_align="CENTER",
        )
    )
    # Value cells: B, D, F:G (search), I
    for col in (1, 3, 8):
        requests.append(
            _format_range(
                sheet_id,
                2,
                3,
                col,
                col + 1,
                bg=_KPI_VALUE_BG,
                fg=_KPI_VALUE_FG,
                bold=False,
                font_size=10,
                v_align="MIDDLE",
            )
        )
        requests.append(_border_range(sheet_id, 2, 3, col, col + 1))
    requests.append(_merge_cells(sheet_id, 2, 3, 5, 7))  # search F:G
    requests.append(
        _format_range(
            sheet_id,
            2,
            3,
            5,
            7,
            bg=_KPI_VALUE_BG,
            fg=_KPI_VALUE_FG,
            italic=False,
            font_size=10,
            v_align="MIDDLE",
        )
    )
    requests.append(_border_range(sheet_id, 2, 3, 5, 7))
    # Hover hint (Sheets cannot show HTML placeholders)
    requests.append(
        {
            "updateCells": {
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": 2,
                    "columnIndex": 5,
                },
                "rows": [{"values": [{"note": DASHBOARD_SEARCH_HINT}]}],
                "fields": "note",
            }
        }
    )
    requests.append(_row_height(sheet_id, 2, 34))

    # Spacer row
    requests.append(_row_height(sheet_id, 3, 10))

    # KPI cards (rows 4–5): Exercises B–C, Entries E–F, Top Lift H–K
    requests.extend(_format_kpi_card(sheet_id, 1, 3, label_row=4, value_row=5))
    requests.extend(_format_kpi_card(sheet_id, 4, 6, label_row=4, value_row=5))
    requests.extend(_format_top_lift_kpi_card(sheet_id, label_row=4, value_row=5))
    requests.append(_row_height(sheet_id, 4, 22))
    requests.append(_row_height(sheet_id, 5, 42))

    # Section title (row 6)
    requests.append(_merge_cells(sheet_id, 6, 7, 0, w))
    requests.append(
        _format_range(
            sheet_id,
            6,
            7,
            0,
            w,
            bg=_SECTION_BG,
            fg=_SECTION_FG,
            bold=True,
            font_size=11,
            h_align="LEFT",
            v_align="MIDDLE",
        )
    )
    requests.append(_row_height(sheet_id, 6, 30))

    # Table header (row 7) — 6 cols including Unit
    requests.append(
        _format_range(
            sheet_id,
            7,
            8,
            0,
            6,
            bg=_TABLE_HDR_BG,
            fg=_TABLE_HDR_FG,
            bold=True,
            font_size=9,
        )
    )

    # Data rows (rows 8–107) — two range fills instead of 100 per-row requests
    data_start = 8
    data_end = 8 + _DASHBOARD_DATA_ROWS
    requests.append(
        _format_range(
            sheet_id,
            data_start,
            data_end,
            0,
            6,
            bg=_KPI_VALUE_BG,
            font_size=10,
        )
    )
    requests.append(
        {
            "addBanding": {
                "bandedRange": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": data_start,
                        "endRowIndex": data_end,
                        "startColumnIndex": 0,
                        "endColumnIndex": 6,
                    },
                    "rowProperties": {
                        "headerColor": _rgb(_KPI_VALUE_BG),
                        "firstBandColor": _rgb(_ALT_ROW_BG),
                        "secondBandColor": _rgb(_KPI_VALUE_BG),
                    },
                }
            }
        }
    )
    for col_idx, px in [
        (0, 100),
        (1, 110),
        (2, 150),
        (3, 90),
        (4, 70),
        (5, 160),
        (6, 20),
        (7, 80),
        (8, 130),
        (9, 70),
        (10, 100),
        (11, 16),
    ]:
        requests.append(_col_width(sheet_id, col_idx, px))

    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "tabColorStyle": {"rgbColor": _rgb("#059669")},
                },
                "fields": "tabColorStyle",
            }
        }
    )

    client.batch_update(spreadsheet_id, requests)


def _format_kpi_card(
    sheet_id: int,
    start_col: int,
    end_col: int,
    *,
    label_row: int,
    value_row: int,
) -> list[dict[str, Any]]:
    """Format a two-row KPI card with label on top and large value below."""
    requests: list[dict[str, Any]] = [
        _merge_cells(sheet_id, label_row, label_row + 1, start_col, end_col),
        _format_range(
            sheet_id,
            label_row,
            label_row + 1,
            start_col,
            end_col,
            bg=_TITLE_BG,
            fg="#94A3B8",
            bold=True,
            font_size=8,
            h_align="CENTER",
            v_align="BOTTOM",
        ),
        _merge_cells(sheet_id, value_row, value_row + 1, start_col, end_col),
        _format_range(
            sheet_id,
            value_row,
            value_row + 1,
            start_col,
            end_col,
            bg=_KPI_VALUE_BG,
            fg=_KPI_VALUE_FG,
            bold=True,
            font_size=22,
            h_align="CENTER",
            v_align="MIDDLE",
        ),
        _border_range(sheet_id, label_row, value_row + 1, start_col, end_col),
        # Emerald accent on top edge
        {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": label_row,
                    "endRowIndex": label_row + 1,
                    "startColumnIndex": start_col,
                    "endColumnIndex": end_col,
                },
                "top": {"style": "SOLID", "color": _rgb(_ACCENT_BG), "width": 3},
            }
        },
    ]
    return requests


def _format_top_lift_kpi_card(
    sheet_id: int,
    *,
    label_row: int,
    value_row: int,
) -> list[dict[str, Any]]:
    """Top-lift card spans H–K: value on the left, exercise name on the right."""
    start_col, end_col = 7, 11  # H–K
    requests: list[dict[str, Any]] = [
        _merge_cells(sheet_id, label_row, label_row + 1, start_col, end_col),
        _format_range(
            sheet_id,
            label_row,
            label_row + 1,
            start_col,
            end_col,
            bg=_TITLE_BG,
            fg="#94A3B8",
            bold=True,
            font_size=8,
            h_align="CENTER",
            v_align="BOTTOM",
        ),
        _merge_cells(sheet_id, value_row, value_row + 1, start_col, start_col + 2),
        _format_range(
            sheet_id,
            value_row,
            value_row + 1,
            start_col,
            start_col + 2,
            bg=_KPI_VALUE_BG,
            fg=_KPI_VALUE_FG,
            bold=True,
            font_size=22,
            h_align="CENTER",
            v_align="MIDDLE",
        ),
        _merge_cells(sheet_id, value_row, value_row + 1, start_col + 2, end_col),
        _format_range(
            sheet_id,
            value_row,
            value_row + 1,
            start_col + 2,
            end_col,
            bg=_KPI_VALUE_BG,
            fg=_KPI_LABEL_FG,
            italic=False,
            font_size=10,
            h_align="LEFT",
            v_align="MIDDLE",
        ),
        _border_range(sheet_id, label_row, value_row + 1, start_col, end_col),
        {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": label_row,
                    "endRowIndex": label_row + 1,
                    "startColumnIndex": start_col,
                    "endColumnIndex": end_col,
                },
                "top": {"style": "SOLID", "color": _rgb(_ACCENT_BG), "width": 3},
            }
        },
    ]
    return requests


def _border_range(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
    *,
    color: str = _BORDER_COLOR,
) -> dict[str, Any]:
    border_style = {"style": "SOLID", "color": _rgb(color), "width": 1}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "top": border_style,
            "bottom": border_style,
            "left": border_style,
            "right": border_style,
        }
    }


# ---------------------------------------------------------------------------
# Low-level formatting helpers
# ---------------------------------------------------------------------------


def _rgb(hex_color: str) -> dict[str, float]:
    """Convert #RRGGBB to Sheets API RGB dict (values 0–1)."""
    h = hex_color.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue": int(h[4:6], 16) / 255,
    }


def _format_range(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
    *,
    bg: str | None = None,
    fg: str | None = None,
    bold: bool = False,
    italic: bool = False,
    font_size: int | None = None,
    h_align: str | None = None,
    v_align: str | None = None,
) -> dict[str, Any]:
    cell_format: dict[str, Any] = {}
    fields: list[str] = []

    if bg:
        cell_format["backgroundColor"] = _rgb(bg)
        fields.append("backgroundColor")

    text_format: dict[str, Any] = {}
    if fg:
        text_format["foregroundColor"] = _rgb(fg)
    if bold:
        text_format["bold"] = True
    if italic:
        text_format["italic"] = True
    if font_size:
        text_format["fontSize"] = font_size
    if text_format:
        cell_format["textFormat"] = text_format
        fields.append("textFormat")

    if h_align:
        cell_format["horizontalAlignment"] = h_align
        fields.append("horizontalAlignment")
    if v_align:
        cell_format["verticalAlignment"] = v_align
        fields.append("verticalAlignment")

    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "cell": {"userEnteredFormat": cell_format},
            "fields": f"userEnteredFormat({','.join(fields)})",
        }
    }


def _merge_cells(
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
) -> dict[str, Any]:
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def _col_width(sheet_id: int, col_index: int, pixel_size: int) -> dict[str, Any]:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col_index,
                "endIndex": col_index + 1,
            },
            "properties": {"pixelSize": pixel_size},
            "fields": "pixelSize",
        }
    }


def _row_height(sheet_id: int, row_index: int, pixel_size: int) -> dict[str, Any]:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": row_index,
                "endIndex": row_index + 1,
            },
            "properties": {"pixelSize": pixel_size},
            "fields": "pixelSize",
        }
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _dropdown_validation_request(
    sheet_id: int,
    column_index: int,
    options: list[str],
    *,
    start_row: int | None = None,
    end_row: int | None = None,
) -> dict[str, Any]:
    row_start = (start_row - 1) if start_row else (DATA_START_ROW - 1)
    row_end = end_row if end_row else 1000
    return {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_start,
                "endRowIndex": row_end,
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


def _date_column_range(
    sheet_id: int,
    column_index: int,
    *,
    start_row: int | None = None,
    end_row: int | None = None,
) -> dict[str, int]:
    row_start = (start_row - 1) if start_row else (DATA_START_ROW - 1)
    row_end = end_row if end_row else 1000
    return {
        "sheetId": sheet_id,
        "startRowIndex": row_start,
        "endRowIndex": row_end,
        "startColumnIndex": column_index,
        "endColumnIndex": column_index + 1,
    }


def _date_format_request(
    sheet_id: int,
    column_index: int,
    *,
    start_row: int | None = None,
    end_row: int | None = None,
) -> dict[str, Any]:
    """Display Date column as yyyy-mm-dd so Sheets offers a calendar picker."""
    return {
        "repeatCell": {
            "range": _date_column_range(
                sheet_id, column_index, start_row=start_row, end_row=end_row
            ),
            "cell": {
                "userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _date_validation_request(
    sheet_id: int,
    column_index: int,
    *,
    start_row: int | None = None,
    end_row: int | None = None,
) -> dict[str, Any]:
    """Require a valid date; Sheets shows the calendar UI when editing."""
    return {
        "setDataValidation": {
            "range": _date_column_range(
                sheet_id, column_index, start_row=start_row, end_row=end_row
            ),
            "rule": {
                "condition": {"type": "DATE_IS_VALID"},
                "showCustomUi": True,
                "strict": False,
            },
        }
    }


def _sheet_id(client: SheetsClient, spreadsheet_id: str, title: str) -> int:
    meta = client.get_spreadsheet(spreadsheet_id, fields="sheets.properties")
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] == title:
            return sheet["properties"]["sheetId"]
    raise ValueError(f"Sheet not found: {title}")


def _unmerge_dashboard(client: SheetsClient, spreadsheet_id: str) -> None:
    """Clear merges and banding on Dashboard before reformatting."""
    meta = client.get_spreadsheet(
        spreadsheet_id,
        fields="sheets.merges,sheets.bandedRanges,sheets.properties",
    )
    requests: list[dict[str, Any]] = []
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] != DASHBOARD_SHEET:
            continue
        for merge_range in sheet.get("merges", []):
            requests.append({"unmergeCells": {"range": merge_range}})
        for band in sheet.get("bandedRanges", []):
            requests.append({"deleteBanding": {"bandedRangeId": band["bandedRangeId"]}})
    if requests:
        client.batch_update(spreadsheet_id, requests)
