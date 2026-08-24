"""Tests for interactive dashboard layout constants."""

from liftlogic.constants import (
    DASHBOARD_CTRL_EXERCISE_CELL,
    DASHBOARD_CTRL_MUSCLE_CELL,
    DASHBOARD_CTRL_SEARCH_CELL,
    DASHBOARD_CTRL_VIEW_CELL,
    DASHBOARD_DATA_START_ROW,
    DASHBOARD_HEADER_ROW,
    DASHBOARD_KPI_TOPLIFT_EXERCISE_CELL,
    DASHBOARD_MUSCLE_FILTER_OPTIONS,
    DASHBOARD_SEARCH_HINT,
    DASHBOARD_VIEW_OPTIONS,
)
from liftlogic.setup import (
    _DASHBOARD_WIDTH,
    _date_format_request,
    _date_validation_request,
    _format_top_lift_kpi_card,
)


def test_dashboard_width():
    assert _DASHBOARD_WIDTH == 12


def test_dashboard_control_cells():
    assert DASHBOARD_CTRL_MUSCLE_CELL == "Dashboard!B3"
    assert DASHBOARD_CTRL_VIEW_CELL == "Dashboard!D3"
    assert DASHBOARD_CTRL_SEARCH_CELL == "Dashboard!F3"
    assert DASHBOARD_CTRL_EXERCISE_CELL == "Dashboard!I3"


def test_dashboard_table_rows():
    assert DASHBOARD_HEADER_ROW == 8
    assert DASHBOARD_DATA_START_ROW == 9


def test_dashboard_filter_options():
    assert DASHBOARD_MUSCLE_FILTER_OPTIONS[0] == "All"
    assert "Chest" in DASHBOARD_MUSCLE_FILTER_OPTIONS
    assert DASHBOARD_VIEW_OPTIONS == ["Summary", "Workout Log"]


def test_date_format_request_structure():
    req = _date_format_request(sheet_id=42, column_index=0)
    cell_range = req["repeatCell"]["range"]
    assert cell_range["sheetId"] == 42
    assert cell_range["startColumnIndex"] == 0
    assert cell_range["endColumnIndex"] == 1
    assert cell_range["startRowIndex"] == 1  # DATA_START_ROW=2 → 0-based 1
    fmt = req["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"]
    assert fmt["type"] == "DATE"
    assert fmt["pattern"] == "yyyy-mm-dd"


def test_date_validation_request_structure():
    req = _date_validation_request(sheet_id=7, column_index=0)
    rule = req["setDataValidation"]["rule"]
    assert rule["condition"]["type"] == "DATE_IS_VALID"
    assert rule["showCustomUi"] is True
    assert req["setDataValidation"]["range"]["sheetId"] == 7


def test_search_hint():
    assert "filter" in DASHBOARD_SEARCH_HINT.lower()
    assert DASHBOARD_SEARCH_HINT != "type to filter…"


def test_top_lift_exercise_inside_kpi_card():
    assert DASHBOARD_KPI_TOPLIFT_EXERCISE_CELL == "Dashboard!J6"
    reqs = _format_top_lift_kpi_card(sheet_id=1, label_row=4, value_row=5)
    merges = [r["mergeCells"]["range"] for r in reqs if "mergeCells" in r]
    # Label H–K, value H–I, exercise J–K
    assert any(m["startColumnIndex"] == 7 and m["endColumnIndex"] == 11 for m in merges)
    assert any(m["startColumnIndex"] == 7 and m["endColumnIndex"] == 9 for m in merges)
    assert any(m["startColumnIndex"] == 9 and m["endColumnIndex"] == 11 for m in merges)
