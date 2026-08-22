"""Tests for muscle-tab vs Workout_Log reconciliation."""

from datetime import date
from unittest.mock import MagicMock

from liftlogic.models import WorkoutEntry
from liftlogic.reconcile import reconcile_workout_log


def _log_entry(
    source_row: str,
    exercise: str = "Barbell Bench Press",
    weight: float = 185,
    notes: str = "",
) -> WorkoutEntry:
    return WorkoutEntry(
        log_id="L000001",
        workout_date=date(2026, 8, 20),
        muscle="Chest",
        exercise_id="CH001",
        exercise=exercise,
        weight=weight,
        notes=notes,
        source_row=source_row,
    )


def _client_returning(muscle_rows: list[list]) -> MagicMock:
    """Return a mock SheetsClient that serves muscle_rows for Chest, empty for others."""
    client = MagicMock()

    def get_values(_spreadsheet_id: str, range_name: str) -> list[list]:
        if range_name.startswith("Chest"):
            return muscle_rows
        return []

    client.get_values.side_effect = get_values
    return client


def test_reconcile_clean():
    client = _client_returning([["2026-08-20", "Barbell Bench Press", 185, ""]])
    report = reconcile_workout_log(client, "sheet-id", [_log_entry("Chest!A2")])
    assert report.is_clean


def test_reconcile_missing_in_log():
    client = _client_returning([["2026-08-20", "Barbell Bench Press", 185, ""]])
    report = reconcile_workout_log(client, "sheet-id", [])
    assert len(report.missing_in_log) == 1
    assert report.missing_in_log[0].source_row == "Chest!A2"


def test_reconcile_orphaned_in_log():
    client = _client_returning([])
    report = reconcile_workout_log(client, "sheet-id", [_log_entry("Chest!A2")])
    assert len(report.orphaned_in_log) == 1
    assert report.orphaned_in_log[0].source_row == "Chest!A2"


def test_reconcile_mismatched_weight():
    client = _client_returning([["2026-08-20", "Barbell Bench Press", 200, ""]])
    report = reconcile_workout_log(client, "sheet-id", [_log_entry("Chest!A2", weight=185)])
    assert len(report.mismatched) == 1
    assert "weight" in report.mismatched[0].message


def test_reconcile_mismatched_exercise():
    client = _client_returning([["2026-08-20", "Cable Fly", 60, ""]])
    report = reconcile_workout_log(
        client, "sheet-id", [_log_entry("Chest!A2", exercise="Barbell Bench Press")]
    )
    assert len(report.mismatched) == 1


def test_reconcile_issue_count():
    client = _client_returning([["2026-08-20", "Barbell Bench Press", 185, ""]])
    report = reconcile_workout_log(client, "sheet-id", [])
    assert report.issue_count == 1
    assert not report.is_clean
