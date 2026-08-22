"""Tests for exercise catalog helpers."""

from liftlogic.exercises import DEFAULT_EXERCISES, exercise_by_name, exercises_for_muscle


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
