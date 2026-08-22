"""Tests for LiftLogic analytics."""

from datetime import date, timedelta

from liftlogic.analytics import (
    ExerciseProgression,
    ExerciseSession,
    Trend,
    build_dashboard_summary,
    calculate_personal_records,
    calculate_streak,
    count_unique_workout_dates,
    count_workouts_in_range,
    detect_plateau,
    detect_trend,
    exercise_progressions,
    last_trained_per_muscle,
    muscle_session_counts,
)
from liftlogic.models import WorkoutEntry


def _entry(
    exercise_id: str,
    exercise: str,
    weight: float,
    workout_date: date,
    muscle: str = "Chest",
    notes: str = "",
) -> WorkoutEntry:
    return WorkoutEntry(
        log_id="L000001",
        workout_date=workout_date,
        muscle=muscle,
        exercise_id=exercise_id,
        exercise=exercise,
        weight=weight,
        notes=notes,
        source_row="Chest!A2",
    )


# ---------------------------------------------------------------------------
# Personal records
# ---------------------------------------------------------------------------


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


def test_personal_record_unit_is_lb_for_strength():
    entries = [_entry("CH001", "Barbell Bench Press", 185, date(2026, 8, 1))]
    records = calculate_personal_records(entries)
    assert records[0].unit == "lb"


def test_personal_record_unit_is_steps_for_steps():
    entries = [
        _entry("CD004", "Steps", 8500, date(2026, 8, 1), muscle="Cardio"),
    ]
    records = calculate_personal_records(entries)
    assert len(records) == 1
    assert records[0].unit == "steps"
    assert records[0].weight == 8500


def test_personal_record_unit_is_minutes_for_treadmill():
    entries = [
        _entry("CD001", "Treadmill Run", 30, date(2026, 8, 1), muscle="Cardio"),
    ]
    records = calculate_personal_records(entries)
    assert records[0].unit == "minutes"


def test_strength_and_cardio_prs_are_separate():
    entries = [
        _entry("CH001", "Barbell Bench Press", 185, date(2026, 8, 1)),
        _entry("CD004", "Steps", 8500, date(2026, 8, 1), muscle="Cardio"),
    ]
    records = calculate_personal_records(entries)
    assert len(records) == 2
    units = {r.unit for r in records}
    assert "lb" in units
    assert "steps" in units


# ---------------------------------------------------------------------------
# Workout counts
# ---------------------------------------------------------------------------


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


def test_last_trained_per_muscle():
    entries = [
        _entry("CH001", "Bench Press", 185, date(2026, 8, 1), muscle="Chest"),
        _entry("CH001", "Bench Press", 190, date(2026, 8, 10), muscle="Chest"),
        _entry("BK001", "Row", 135, date(2026, 8, 5), muscle="Back"),
    ]
    result = last_trained_per_muscle(entries)
    assert result["Chest"] == date(2026, 8, 10)
    assert result["Back"] == date(2026, 8, 5)


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------


def test_streak_consecutive_days():
    today = date(2026, 8, 21)
    entries = [
        _entry("CH001", "Bench", 185, today),
        _entry("CH001", "Bench", 185, today - timedelta(days=1)),
        _entry("CH001", "Bench", 185, today - timedelta(days=2)),
    ]
    assert calculate_streak(entries, as_of=today) == 3


def test_streak_broken_by_gap():
    today = date(2026, 8, 21)
    entries = [
        _entry("CH001", "Bench", 185, today),
        _entry("CH001", "Bench", 185, today - timedelta(days=2)),  # gap
    ]
    assert calculate_streak(entries, as_of=today) == 1


def test_streak_empty():
    assert calculate_streak([]) == 0


def test_streak_too_old():
    old = date(2026, 8, 1)
    entries = [_entry("CH001", "Bench", 185, old)]
    assert calculate_streak(entries, as_of=date(2026, 8, 21)) == 0


# ---------------------------------------------------------------------------
# Exercise progression
# ---------------------------------------------------------------------------


def test_exercise_progressions_groups_by_id():
    entries = [
        _entry("CH001", "Bench Press", 185, date(2026, 8, 1)),
        _entry("CH001", "Bench Press", 190, date(2026, 8, 8)),
        _entry("BK001", "Row", 135, date(2026, 8, 5), muscle="Back"),
    ]
    progs = exercise_progressions(entries)
    assert "CH001" in progs
    assert "BK001" in progs
    assert progs["CH001"].session_count == 2
    assert progs["CH001"].best_weight == 190
    assert progs["CH001"].latest_weight == 190
    assert progs["CH001"].previous_weight == 185
    assert progs["CH001"].weight_change == 5


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------


def _progression(weights: list[float], start: date | None = None) -> ExerciseProgression:
    base = start or date(2026, 8, 1)
    prog = ExerciseProgression(exercise_id="CH001", exercise="Bench Press")
    for i, w in enumerate(weights):
        prog.sessions.append(ExerciseSession(base + timedelta(days=i * 7), w, ""))
    return prog


def test_detect_trend_improving():
    result = detect_trend(_progression([185, 190, 195, 200]))
    assert result.trend == Trend.IMPROVING
    assert result.weight_change == 15


def test_detect_trend_declining():
    result = detect_trend(_progression([200, 195, 190, 185]))
    assert result.trend == Trend.DECLINING
    assert result.weight_change == -15


def test_detect_trend_plateau():
    result = detect_trend(_progression([185, 185, 186, 185]))
    assert result.trend == Trend.PLATEAU


def test_detect_trend_insufficient_data():
    result = detect_trend(_progression([185]))
    assert result.trend == Trend.INSUFFICIENT_DATA


def test_detect_plateau_true():
    assert detect_plateau(_progression([185, 185, 185]), min_sessions=3) is True


def test_detect_plateau_false():
    assert detect_plateau(_progression([185, 190, 195]), min_sessions=3) is False


def test_detect_plateau_insufficient_sessions():
    assert detect_plateau(_progression([185, 185]), min_sessions=3) is False


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


def test_build_dashboard_summary():
    today = date(2026, 8, 21)
    entries = [
        _entry("CH001", "Bench Press", 200, today, muscle="Chest"),
        _entry("CH001", "Bench Press", 185, today - timedelta(days=1), muscle="Chest"),
        _entry("BK001", "Row", 135, today - timedelta(days=7), muscle="Back"),
    ]
    summary = build_dashboard_summary(entries, as_of=today)

    assert summary.total_workouts == 3
    assert summary.current_streak == 2
    assert len(summary.personal_records) == 2
    assert summary.muscle_session_counts["Chest"] == 2
    assert summary.muscle_session_counts["Back"] == 1
    assert len(summary.recent_prs) == 2
