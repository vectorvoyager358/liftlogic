"""Tests for LiftLogic analytics."""

from datetime import date

from liftlogic.analytics import (
    calculate_personal_records,
    count_unique_workout_dates,
    count_workouts_in_range,
    muscle_session_counts,
)
from liftlogic.models import WorkoutEntry


def _entry(
    exercise_id: str,
    exercise: str,
    weight: float,
    workout_date: date,
    muscle: str = "Chest",
) -> WorkoutEntry:
    return WorkoutEntry(
        log_id="L000001",
        workout_date=workout_date,
        muscle=muscle,
        exercise_id=exercise_id,
        exercise=exercise,
        weight=weight,
        notes="",
        source_row="Chest!A2",
    )


def test_calculate_personal_records_picks_max_weight():
    entries = [
        _entry("CH001", "Bench Press", 185, date(2026, 8, 1)),
        _entry("CH001", "Bench Press", 200, date(2026, 8, 10)),
        _entry("CH001", "Bench Press", 195, date(2026, 8, 15)),
    ]
    records = calculate_personal_records(entries)
    assert len(records) == 1
    assert records[0].weight == 200
    assert records[0].workout_date == date(2026, 8, 10)


def test_calculate_personal_records_tie_goes_to_latest_date():
    entries = [
        _entry("CH001", "Bench Press", 200, date(2026, 8, 1)),
        _entry("CH001", "Bench Press", 200, date(2026, 8, 20)),
    ]
    records = calculate_personal_records(entries)
    assert records[0].workout_date == date(2026, 8, 20)


def test_calculate_personal_records_ignores_zero_weight():
    entries = [_entry("CH001", "Bench Press", 0, date(2026, 8, 1))]
    assert calculate_personal_records(entries) == []


def test_count_unique_workout_dates():
    entries = [
        _entry("CH001", "Bench Press", 185, date(2026, 8, 1)),
        _entry("CH002", "Incline Press", 60, date(2026, 8, 1)),
        _entry("CH001", "Bench Press", 190, date(2026, 8, 3)),
    ]
    assert count_unique_workout_dates(entries) == 2


def test_count_workouts_in_range():
    entries = [
        _entry("CH001", "Bench Press", 185, date(2026, 8, 1)),
        _entry("CH001", "Bench Press", 190, date(2026, 8, 15)),
        _entry("CH001", "Bench Press", 195, date(2026, 9, 1)),
    ]
    assert count_workouts_in_range(entries, date(2026, 8, 1), date(2026, 8, 31)) == 2


def test_muscle_session_counts():
    entries = [
        _entry("CH001", "Bench Press", 185, date(2026, 8, 1), muscle="Chest"),
        _entry("CH002", "Incline Press", 60, date(2026, 8, 1), muscle="Chest"),
        _entry("BK001", "Row", 135, date(2026, 8, 2), muscle="Back"),
    ]
    assert muscle_session_counts(entries) == {"Chest": 1, "Back": 1}
