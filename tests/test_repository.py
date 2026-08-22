"""Tests for workout repository parsing and ID generation."""

from datetime import date

from liftlogic.exercises import DEFAULT_EXERCISES, exercise_by_name, exercises_for_muscle
from liftlogic.models import WorkoutEntry
from liftlogic.repository import _next_log_id, _parse_workout_row


def _entry(log_id: str, weight: float = 185) -> WorkoutEntry:
    return WorkoutEntry(
        log_id=log_id,
        workout_date=date(2026, 8, 20),
        muscle="Chest",
        exercise_id="CH001",
        exercise="Barbell Bench Press",
        weight=weight,
        notes="",
        source_row="Chest!A2",
    )


def test_parse_workout_row():
    row = [
        "L000001",
        "2026-08-20",
        "Chest",
        "CH001",
        "Barbell Bench Press",
        "185",
        "Felt strong",
        "Chest!A5",
    ]
    entry = _parse_workout_row(row)
    assert entry.log_id == "L000001"
    assert entry.workout_date == date(2026, 8, 20)
    assert entry.weight == 185.0
    assert entry.source_row == "Chest!A5"


def test_parse_workout_row_short_row():
    row = ["L000002", "2026-08-20", "Back", "BK001", "Lat Pulldown", "120"]
    entry = _parse_workout_row(row)
    assert entry.notes == ""
    assert entry.source_row == ""


def test_next_log_id_increments():
    entries = [_entry("L000005")]
    assert _next_log_id(entries) == "L000006"


def test_next_log_id_empty():
    assert _next_log_id([]) == "L000001"


def test_next_log_id_pads_to_six():
    entries = [_entry("L000009")]
    assert _next_log_id(entries) == "L000010"


def test_exercises_for_muscle():
    chest = exercises_for_muscle("Chest")
    assert len(chest) >= 3
    assert all(ex.primary_muscle == "Chest" for ex in chest)


def test_exercise_by_name_case_insensitive():
    found = exercise_by_name("barbell bench press")
    assert found is not None
    assert found.exercise_id == "CH001"


def test_exercise_by_name_unknown():
    assert exercise_by_name("Unknown Exercise") is None


def test_default_exercises_have_unique_ids():
    ids = [ex.exercise_id for ex in DEFAULT_EXERCISES]
    assert len(ids) == len(set(ids))
