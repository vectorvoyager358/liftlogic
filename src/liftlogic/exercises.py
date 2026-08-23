"""Seed exercise catalog and lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Exercise:
    exercise_id: str
    name: str
    primary_muscle: str
    secondary_muscle: str
    equipment: str
    metric: str = "lb"  # unit for the value logged in the Weight column


DEFAULT_EXERCISES: tuple[Exercise, ...] = (
    Exercise("CH001", "Barbell Bench Press", "Chest", "Triceps", "Barbell"),
    Exercise("CH002", "Incline Dumbbell Press", "Chest", "Shoulders", "Dumbbell"),
    Exercise("CH003", "Cable Fly", "Chest", "Shoulders", "Cable"),
    Exercise("CH004", "Push-Up", "Chest", "Triceps", "Bodyweight"),
    Exercise("BK001", "Lat Pulldown", "Back", "Biceps", "Cable"),
    Exercise("BK002", "Barbell Row", "Back", "Biceps", "Barbell"),
    Exercise("BK003", "Pull-Up", "Back", "Biceps", "Bodyweight"),
    Exercise("BK004", "Seated Cable Row", "Back", "Biceps", "Cable"),
    Exercise("SH001", "Overhead Press", "Shoulders", "Triceps", "Barbell"),
    Exercise("SH002", "Lateral Raise", "Shoulders", "", "Dumbbell"),
    Exercise("SH003", "Face Pull", "Shoulders", "Back", "Cable"),
    Exercise("BI001", "Barbell Curl", "Biceps", "", "Barbell"),
    Exercise("BI002", "Hammer Curl", "Biceps", "Forearms", "Dumbbell"),
    Exercise("TR001", "Tricep Pushdown", "Triceps", "", "Cable"),
    Exercise("TR002", "Skull Crusher", "Triceps", "", "Barbell"),
    Exercise("LG001", "Back Squat", "Legs", "Core", "Barbell"),
    Exercise("LG002", "Romanian Deadlift", "Legs", "Back", "Barbell"),
    Exercise("LG003", "Leg Press", "Legs", "", "Machine"),
    Exercise("LG004", "Walking Lunge", "Legs", "Core", "Dumbbell"),
    Exercise("CD001", "Treadmill Run", "Cardio", "", "Machine", metric="minutes"),
    Exercise("CD002", "Stationary Bike", "Cardio", "", "Machine", metric="minutes"),
    Exercise("CD003", "Rowing Machine", "Cardio", "Back", "Machine", metric="minutes"),
    Exercise("CD004", "Steps", "Cardio", "", "Bodyweight", metric="steps"),
    Exercise("CD005", "Jump Rope", "Cardio", "", "Bodyweight", metric="minutes"),
    Exercise("CD006", "Elliptical", "Cardio", "", "Machine", metric="minutes"),
)


def exercises_for_muscle(muscle: str) -> list[Exercise]:
    return [ex for ex in DEFAULT_EXERCISES if ex.primary_muscle == muscle]


def exercise_by_name(name: str) -> Exercise | None:
    normalized = name.strip().casefold()
    for exercise in DEFAULT_EXERCISES:
        if exercise.name.casefold() == normalized:
            return exercise
    return None


def exercise_by_id(exercise_id: str) -> Exercise | None:
    normalized = exercise_id.strip().casefold()
    for exercise in DEFAULT_EXERCISES:
        if exercise.exercise_id.casefold() == normalized:
            return exercise
    return None


def exercise_display_name(name_or_id: str) -> str:
    """Resolve an exercise ID to its catalog name, or return the name as-is."""
    match = exercise_by_id(name_or_id)
    if match:
        return match.name
    return name_or_id


def exercise_metric(name_or_id: str) -> str:
    """Return the unit metric for an exercise name or ID. Defaults to 'lb'."""
    normalized = name_or_id.strip().casefold()
    for ex in DEFAULT_EXERCISES:
        if ex.name.casefold() == normalized or ex.exercise_id.casefold() == normalized:
            return ex.metric
    return "lb"


def exercise_rows() -> list[list[str]]:
    return [
        [
            ex.exercise_id,
            ex.name,
            ex.primary_muscle,
            ex.secondary_muscle,
            ex.equipment,
        ]
        for ex in DEFAULT_EXERCISES
    ]
