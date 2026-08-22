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
    Exercise("CD001", "Treadmill Run", "Cardio", "", "Machine"),
    Exercise("CD002", "Stationary Bike", "Cardio", "", "Machine"),
    Exercise("CD003", "Rowing Machine", "Cardio", "Back", "Machine"),
)


def exercises_for_muscle(muscle: str) -> list[Exercise]:
    return [ex for ex in DEFAULT_EXERCISES if ex.primary_muscle == muscle]


def exercise_by_name(name: str) -> Exercise | None:
    normalized = name.strip().casefold()
    for exercise in DEFAULT_EXERCISES:
        if exercise.name.casefold() == normalized:
            return exercise
    return None


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
