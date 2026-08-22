"""Tests for exercise catalog helpers."""

from liftlogic.exercises import (
    DEFAULT_EXERCISES,
    exercise_by_name,
    exercise_metric,
    exercises_for_muscle,
)


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


# ---------------------------------------------------------------------------
# Metric / unit
# ---------------------------------------------------------------------------


def test_strength_exercise_metric_is_lb():
    assert exercise_metric("Barbell Bench Press") == "lb"
    assert exercise_metric("CH001") == "lb"


def test_steps_exercise_metric_is_steps():
    assert exercise_metric("Steps") == "steps"
    assert exercise_metric("CD004") == "steps"


def test_treadmill_metric_is_minutes():
    assert exercise_metric("Treadmill Run") == "minutes"


def test_stationary_bike_metric_is_minutes():
    assert exercise_metric("Stationary Bike") == "minutes"


def test_unknown_exercise_metric_defaults_to_lb():
    assert exercise_metric("Made Up Exercise") == "lb"


def test_metric_lookup_is_case_insensitive():
    assert exercise_metric("steps") == "steps"
    assert exercise_metric("BARBELL BENCH PRESS") == "lb"


def test_cardio_exercises_have_non_lb_metric():
    cardio = exercises_for_muscle("Cardio")
    assert all(ex.metric != "lb" for ex in cardio), (
        "All Cardio exercises should have a non-lb metric"
    )


def test_strength_exercises_default_to_lb():
    strength_muscles = ["Chest", "Back", "Shoulders", "Biceps", "Triceps", "Legs"]
    for muscle in strength_muscles:
        for ex in exercises_for_muscle(muscle):
            assert ex.metric == "lb", f"{ex.name} should have metric='lb'"
