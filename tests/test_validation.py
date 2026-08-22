"""Tests for workout validation."""

from liftlogic.validation import validate_workout_input


def test_valid_strength_entry():
    result = validate_workout_input(
        workout_date="2026-08-20",
        muscle="Chest",
        exercise="Barbell Bench Press",
        weight=185,
        notes="Strong",
        source_row="Chest!A2",
    )
    assert result.valid
    assert result.input is not None
    assert result.input.exercise_id == "CH001"
    assert result.errors == []


def test_missing_date_is_error():
    result = validate_workout_input(
        workout_date="",
        muscle="Chest",
        exercise="Barbell Bench Press",
        weight=185,
    )
    assert not result.valid
    assert any(issue.code == "required" and issue.field == "date" for issue in result.errors)


def test_zero_weight_strength_is_error():
    result = validate_workout_input(
        workout_date="2026-08-20",
        muscle="Chest",
        exercise="Barbell Bench Press",
        weight=0,
    )
    assert not result.valid
    assert any(issue.code == "zero_weight" for issue in result.errors)


def test_zero_weight_cardio_is_allowed():
    result = validate_workout_input(
        workout_date="2026-08-20",
        muscle="Cardio",
        exercise="Treadmill Run",
        weight=0,
    )
    assert result.valid


def test_unknown_exercise_is_warning():
    result = validate_workout_input(
        workout_date="2026-08-20",
        muscle="Chest",
        exercise="Mystery Press",
        weight=100,
    )
    assert result.valid
    assert any(issue.code == "unknown_exercise" for issue in result.warnings)


def test_invalid_muscle_is_error():
    result = validate_workout_input(
        workout_date="2026-08-20",
        muscle="Core",
        exercise="Barbell Bench Press",
        weight=185,
    )
    assert not result.valid
    assert any(issue.code == "invalid_muscle" for issue in result.errors)
