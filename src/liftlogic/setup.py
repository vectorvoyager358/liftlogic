"""Spreadsheet bootstrap — creates and configures the LiftLogic workbook."""

from __future__ import annotations

from typing import Any

from liftlogic.constants import (
    AI_INSIGHTS_SHEET,
    ANALYTICS_SHEET,
    ANALYTICS_SECTION_NAMES,
    ANALYTICS_TABLE_HEADERS,
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

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

_TITLE_BG = "#1565C0"  # deep blue
_TITLE_FG = "#FFFFFF"
_SUBTITLE_BG = "#1976D2"  # medium blue
_SUBTITLE_FG = "#BBDEFB"  # light blue text
_SECTION_BG = "#283593"  # darker blue for section headers
_SECTION_FG = "#FFFFFF"
_TABLE_HDR_BG = "#E8EAF6"  # very light indigo
_TABLE_HDR_FG = "#1A237E"  # dark navy text
_STAT_LABEL_BG = "#F5F5F5"  # near-white gray
_STAT_VALUE_BG = "#FFFFFF"
_ALT_ROW_BG = "#FAFAFA"

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
    format_dashboard(client, spreadsheet_id)
    create_analytics_tab(client, spreadsheet_id)
    format_workout_tabs(client, spreadsheet_id)
    format_analytics_tab(client, spreadsheet_id)
    hide_internal_sheets(client, spreadsheet_id)
    return spreadsheet_id


def format_dashboard(client: SheetsClient, spreadsheet_id: str) -> None:
    """Rewrite Dashboard content and apply full visual formatting.

    Safe to run on existing sheets — only the Dashboard tab is touched.
    Workout data in muscle tabs is never modified.
    """
    client.clear_values(spreadsheet_id, f"{DASHBOARD_SHEET}!A:Z")
    _write_dashboard_content(client, spreadsheet_id)
    _apply_dashboard_formatting(client, spreadsheet_id)


def format_workout_tabs(client: SheetsClient, spreadsheet_id: str) -> None:
    """Apply colours and formatting to every muscle tab.

    Only changes visual formatting — never overwrites workout data.
    """
    requests: list[dict[str, Any]] = []

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

    client.batch_update(spreadsheet_id, requests)


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
# Dashboard content
# ---------------------------------------------------------------------------
#
# Layout (0-based row indices → Sheet rows 1-based):
#
#  Row 0  (A1)  : Title bar — "LiftLogic Dashboard"          (merged A:H)
#  Row 1  (A2)  : Subtitle — "Last refreshed: …"             (merged A:H)
#  Row 2  (A3)  : blank
#  Row 3  (A4)  : OVERVIEW header (A:C) | RECENT ACTIVITY header (E:H)
#  Row 4  (A5)  : Total Workouts | formula | | | =QUERY recent (spills E5:H14)
#  Row 5  (A6)  : This Week | formula
#  Row 6  (A7)  : This Month | formula
#  Rows 7-13    : blank in A:D; QUERY spill in E:H
#  Row 14 (A15) : blank
#  Row 15 (A16) : PERSONAL RECORDS header (A:D)
#  Row 16 (A17) : =QUERY PRs — strength only (spills A17:D...)
#
# ---------------------------------------------------------------------------

_RECENT_QUERY = (
    "=IFERROR(QUERY(Workout_Log!B2:G,"
    '"SELECT Col1,Col2,Col4,Col5 WHERE Col1 IS NOT NULL '
    "ORDER BY Col1 DESC LIMIT 10 "
    "LABEL Col1 'Date',Col2 'Muscle',Col4 'Exercise',Col5 'Weight'\""
    ',1),"")'
)

_PR_QUERY = (
    "=IFERROR(QUERY(Workout_Log!B2:G,"
    '"SELECT Col4,MAX(Col5),MAX(Col1) '
    "WHERE Col5>0 AND Col2<>'Cardio' "
    "GROUP BY Col4 ORDER BY MAX(Col5) DESC "
    "LABEL Col4 'Exercise',MAX(Col5) 'Best Weight (lb)',MAX(Col1) 'Date'\""
    ',0),"")'
)

_TOTAL_FORMULA = '=IFERROR(COUNTA(UNIQUE(FILTER(Workout_Log!B2:B,Workout_Log!B2:B<>""))),0)'
_WEEK_FORMULA = (
    "=IFERROR(COUNTA(UNIQUE(FILTER(Workout_Log!B2:B,"
    '(Workout_Log!B2:B<>"")'
    "*(Workout_Log!B2:B>=TODAY()-WEEKDAY(TODAY())+1)))),0)"
)
_MONTH_FORMULA = (
    "=IFERROR(COUNTA(UNIQUE(FILTER(Workout_Log!B2:B,"
    '(Workout_Log!B2:B<>"")'
    "*(MONTH(Workout_Log!B2:B)=MONTH(TODAY()))"
    "*(YEAR(Workout_Log!B2:B)=YEAR(TODAY()))))),0)"
)


def _write_dashboard_content(client: SheetsClient, spreadsheet_id: str) -> None:
    """Write all cell values and formulas to the Dashboard tab."""
    blank7 = [[] for _ in range(7)]  # rows 7-13: blank in A:D (QUERY spills E:H)

    values: list[list[Any]] = [
        # Row 0: Title
        ["LiftLogic Dashboard"],
        # Row 1: Last-refreshed subtitle (written here as placeholder; refresh updates it)
        ["Analytics last refreshed: Never  —  run  liftlogic refresh  to update"],
        # Row 2: blank
        [],
        # Row 3: Section headers (cols A–C and E–H)
        ["OVERVIEW", "", "", "", "RECENT ACTIVITY"],
        # Row 4: Stats + recent-activity QUERY
        ["Total Workouts", _TOTAL_FORMULA, "", "", _RECENT_QUERY],
        # Row 5
        ["This Week", _WEEK_FORMULA],
        # Row 6
        ["This Month", _MONTH_FORMULA],
        # Rows 7–13: blank (QUERY spill zone for recent activity)
        *blank7,
        # Row 14: blank separator
        [],
        # Row 15: Personal Records header
        ["PERSONAL RECORDS (Strength)"],
        # Row 16: PR QUERY
        [_PR_QUERY],
    ]

    client.update_values(spreadsheet_id, f"{DASHBOARD_SHEET}!A1", values)


# ---------------------------------------------------------------------------
# Dashboard formatting
# ---------------------------------------------------------------------------


def _apply_dashboard_formatting(client: SheetsClient, spreadsheet_id: str) -> None:
    sheet_id = _sheet_id(client, spreadsheet_id, DASHBOARD_SHEET)
    requests: list[dict[str, Any]] = []

    # ── Title bar (row 0, cols A:H = 0:8) ─────────────────────────────────
    requests.append(_merge_cells(sheet_id, 0, 1, 0, 8))
    requests.append(
        _format_range(
            sheet_id,
            0,
            1,
            0,
            8,
            bg=_TITLE_BG,
            fg=_TITLE_FG,
            bold=True,
            font_size=18,
            h_align="LEFT",
            v_align="MIDDLE",
        )
    )
    requests.append(_row_height(sheet_id, 0, 44))

    # ── Subtitle / last-refreshed (row 1) ─────────────────────────────────
    requests.append(_merge_cells(sheet_id, 1, 2, 0, 8))
    requests.append(
        _format_range(
            sheet_id,
            1,
            2,
            0,
            8,
            bg=_SUBTITLE_BG,
            fg=_SUBTITLE_FG,
            italic=True,
            font_size=9,
        )
    )
    requests.append(_row_height(sheet_id, 1, 22))

    # ── OVERVIEW section header (row 3, cols A:C = 0:3) ───────────────────
    requests.append(_merge_cells(sheet_id, 3, 4, 0, 3))
    requests.append(
        _format_range(sheet_id, 3, 4, 0, 3, bg=_SECTION_BG, fg=_SECTION_FG, bold=True, font_size=10)
    )
    requests.append(_row_height(sheet_id, 3, 28))

    # ── Stat label column (rows 4-6, col A) ───────────────────────────────
    requests.append(_format_range(sheet_id, 4, 7, 0, 1, bg=_STAT_LABEL_BG, bold=True, font_size=10))
    # Stat value column (rows 4-6, col B) — right-aligned
    requests.append(
        _format_range(
            sheet_id,
            4,
            7,
            1,
            2,
            bg=_STAT_VALUE_BG,
            bold=True,
            font_size=11,
            h_align="RIGHT",
        )
    )

    # ── RECENT ACTIVITY section header (row 3, cols E:H = 4:8) ───────────
    requests.append(_merge_cells(sheet_id, 3, 4, 4, 8))
    requests.append(
        _format_range(sheet_id, 3, 4, 4, 8, bg=_SECTION_BG, fg=_SECTION_FG, bold=True, font_size=10)
    )

    # ── Recent activity table header row (row 4, cols E:H) ────────────────
    # QUERY overwrites cell values but formatting persists
    requests.append(
        _format_range(
            sheet_id, 4, 5, 4, 8, bg=_TABLE_HDR_BG, fg=_TABLE_HDR_FG, bold=True, font_size=10
        )
    )

    # ── Alternating rows for recent activity (rows 5-14, cols E:H) ────────
    for i in range(10):
        row = 5 + i
        bg = _ALT_ROW_BG if i % 2 == 0 else _STAT_VALUE_BG
        requests.append(_format_range(sheet_id, row, row + 1, 4, 8, bg=bg, font_size=10))

    # ── PERSONAL RECORDS section header (row 15, cols A:D = 0:4) ─────────
    requests.append(_merge_cells(sheet_id, 15, 16, 0, 4))
    requests.append(
        _format_range(
            sheet_id, 15, 16, 0, 4, bg=_SECTION_BG, fg=_SECTION_FG, bold=True, font_size=10
        )
    )
    requests.append(_row_height(sheet_id, 15, 28))

    # ── PR table header row (row 16, cols A:D) ────────────────────────────
    requests.append(
        _format_range(
            sheet_id,
            16,
            17,
            0,
            4,
            bg=_TABLE_HDR_BG,
            fg=_TABLE_HDR_FG,
            bold=True,
            font_size=10,
        )
    )

    # ── Alternating rows for PRs (rows 17-40, cols A:D) ───────────────────
    for i in range(24):
        row = 17 + i
        bg = _ALT_ROW_BG if i % 2 == 0 else _STAT_VALUE_BG
        requests.append(_format_range(sheet_id, row, row + 1, 0, 4, bg=bg, font_size=10))

    # ── Column widths ──────────────────────────────────────────────────────
    for col_idx, px in [
        (0, 180),  # A: Label / Exercise
        (1, 110),  # B: Value / Best Weight
        (2, 80),  # C: spacer / Unit
        (3, 110),  # D: spacer / Date
        (4, 100),  # E: Date (recent)
        (5, 85),  # F: Muscle
        (6, 190),  # G: Exercise (recent)
        (7, 80),  # H: Weight (recent)
    ]:
        requests.append(_col_width(sheet_id, col_idx, px))

    # ── Freeze title + subtitle rows ───────────────────────────────────────
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 2},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }
    )

    # ── Dashboard tab colour (green) ───────────────────────────────────────
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "tabColorStyle": {"rgbColor": _rgb("#388E3C")},
                },
                "fields": "tabColorStyle",
            }
        }
    )

    client.batch_update(spreadsheet_id, requests)


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
