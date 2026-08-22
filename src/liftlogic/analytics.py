"""Workout analytics — PR detection and summaries."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from liftlogic.models import PersonalRecord, WorkoutEntry


def calculate_personal_records(entries: list[WorkoutEntry]) -> list[PersonalRecord]:
    """Return the max-weight PR per exercise. Most recent date wins on ties."""
    best: dict[str, PersonalRecord] = {}

    for entry in entries:
        if entry.weight <= 0:
            continue

        current = best.get(entry.exercise_id)
        if current is None:
            best[entry.exercise_id] = PersonalRecord(
                exercise_id=entry.exercise_id,
                exercise=entry.exercise,
                weight=entry.weight,
                workout_date=entry.workout_date,
            )
            continue

        if entry.weight > current.weight or (
            entry.weight == current.weight and entry.workout_date > current.workout_date
        ):
            best[entry.exercise_id] = PersonalRecord(
                exercise_id=entry.exercise_id,
                exercise=entry.exercise,
                weight=entry.weight,
                workout_date=entry.workout_date,
            )

    return sorted(best.values(), key=lambda pr: pr.exercise)


def count_unique_workout_dates(entries: list[WorkoutEntry]) -> int:
    return len({entry.workout_date for entry in entries})


def count_workouts_in_range(
    entries: list[WorkoutEntry],
    start: date,
    end: date,
) -> int:
    dates = {entry.workout_date for entry in entries if start <= entry.workout_date <= end}
    return len(dates)


def muscle_session_counts(entries: list[WorkoutEntry]) -> dict[str, int]:
    counts: dict[str, set[date]] = defaultdict(set)
    for entry in entries:
        counts[entry.muscle].add(entry.workout_date)
    return {muscle: len(dates) for muscle, dates in counts.items()}
