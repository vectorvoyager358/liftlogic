"""Tests for muscle tab scoping."""

from __future__ import annotations

from datetime import date

from liftlogic.models import WorkoutEntry
from liftlogic.muscle_context import (
    detect_muscle_in_query,
    entries_for_muscle_tab,
    find_mislogged_entries,
)


def _entry(
    exercise: str,
    muscle: str,
    exercise_id: str = "SH002",
    source_row: str = "Shoulders!A2",
) -> WorkoutEntry:
    return WorkoutEntry(
        log_id="L000001",
        workout_date=date(2026, 8, 21),
        muscle=muscle,
        exercise_id=exercise_id,
        exercise=exercise,
        weight=25,
        notes="",
        source_row=source_row,
    )


def test_detect_muscle_in_query():
    assert detect_muscle_in_query("What shoulder exercises have I done?") == "Shoulders"
    assert detect_muscle_in_query("How is my chest training?") == "Chest"
    assert detect_muscle_in_query("overall progress") is None


def test_entries_for_muscle_tab():
    entries = [
        _entry("Lateral Raise", "Shoulders"),
        _entry("T-Bar", "Back", exercise_id="BK999", source_row="Back!A5"),
    ]
    shoulders = entries_for_muscle_tab(entries, "Shoulders")
    assert len(shoulders) == 1
    assert shoulders[0].exercise == "Lateral Raise"


def test_find_mislogged_expected_muscle():
    entries = [
        _entry("Lateral Raise", "Back", exercise_id="SH002", source_row="Back!A9"),
    ]
    mislogged = find_mislogged_entries(entries, expected_muscle="Shoulders")
    assert len(mislogged) == 1
    assert mislogged[0]["expected_tab"] == "Shoulders"
    assert mislogged[0]["logged_on_tab"] == "Back"


def test_find_mislogged_by_exercise_id():
    entries = [
        _entry(
            "Lateral Raise w/ cable",
            "Back",
            exercise_id="SH002",
            source_row="Back!A9",
        ),
    ]
    mislogged = find_mislogged_entries(entries, expected_muscle="Shoulders")
    assert len(mislogged) == 1
    assert "Move this entry" in mislogged[0]["message"]
