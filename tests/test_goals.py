"""Tests for goal tracking."""

from __future__ import annotations

from datetime import date

from liftlogic.goals import compute_goal_progress, parse_goal_row
from liftlogic.models import Goal, WorkoutEntry


def _entry(
    exercise: str,
    weight: float,
    workout_date: date,
    muscle: str = "Chest",
    exercise_id: str = "CH001",
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


def test_parse_exercise_goal_row():
    goal = parse_goal_row(
        [
            "G001",
            "Exercise",
            "Barbell Bench Press",
            "",
            "225",
            "lb",
            "2026-12-31",
            "Active",
            "Hit by year end",
        ]
    )
    assert goal is not None
    assert goal.goal_type == "Exercise"
    assert goal.exercise == "Barbell Bench Press"
    assert goal.target == 225.0
    assert goal.target_date == date(2026, 12, 31)


def test_parse_muscle_goal_row():
    goal = parse_goal_row(["", "Muscle", "", "Chest", "2", "sessions/week", "", "Active", ""])
    assert goal is not None
    assert goal.muscle == "Chest"
    assert goal.target == 2.0
    assert goal.unit == "sessions/week"


def test_parse_goal_row_invalid():
    assert parse_goal_row(["", "", "", "", "", "", "", "", ""]) is None
    assert parse_goal_row(["", "Exercise", "", "", "0", "lb", "", "Active", ""]) is None


def test_exercise_goal_progress_completed():
    goal = Goal(
        goal_id="G001",
        goal_type="Exercise",
        exercise="Barbell Bench Press",
        muscle="",
        target=200,
        unit="lb",
        target_date=None,
        status="Active",
        notes="",
    )
    entries = [_entry("Barbell Bench Press", 205, date(2026, 8, 20))]
    progress = compute_goal_progress(goal, entries, as_of=date(2026, 8, 21))
    assert progress.status == "completed"
    assert progress.current == 205
    assert progress.progress_pct == 100.0


def test_exercise_goal_progress_in_progress():
    goal = Goal(
        goal_id="G001",
        goal_type="Exercise",
        exercise="Barbell Bench Press",
        muscle="",
        target=225,
        unit="lb",
        target_date=None,
        status="Active",
        notes="",
    )
    entries = [_entry("Barbell Bench Press", 185, date(2026, 8, 20))]
    progress = compute_goal_progress(goal, entries, as_of=date(2026, 8, 21))
    assert progress.status in {"on_track", "behind"}
    assert progress.current == 185
    assert progress.progress_pct < 100


def test_muscle_goal_progress_this_week():
    goal = Goal(
        goal_id="G002",
        goal_type="Muscle",
        exercise="",
        muscle="Chest",
        target=2,
        unit="sessions/week",
        target_date=None,
        status="Active",
        notes="",
    )
    entries = [
        _entry("Barbell Bench Press", 185, date(2026, 8, 18)),
        _entry("Incline Dumbbell Press", 60, date(2026, 8, 20)),
    ]
    progress = compute_goal_progress(goal, entries, as_of=date(2026, 8, 21))
    assert progress.current == 2
    assert progress.status == "completed"
