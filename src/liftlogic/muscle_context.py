"""Muscle tab scoping — detect muscle from queries and find mislogged entries."""

from __future__ import annotations

import re

from liftlogic.exercises import exercise_by_id, exercise_by_name
from liftlogic.models import WorkoutEntry

# Longest aliases first so "lower back" matches before "back"
_MUSCLE_ALIASES: tuple[tuple[str, str], ...] = (
    ("lower back", "Back"),
    ("shoulders", "Shoulders"),
    ("shoulder", "Shoulders"),
    ("biceps", "Biceps"),
    ("bicep", "Biceps"),
    ("triceps", "Triceps"),
    ("tricep", "Triceps"),
    ("cardio", "Cardio"),
    ("chest", "Chest"),
    ("back", "Back"),
    ("legs", "Legs"),
    ("leg", "Legs"),
)


def detect_muscle_in_query(query: str) -> str | None:
    """Return a muscle tab name if the query references a specific muscle group."""
    q = query.casefold()
    for alias, muscle in _MUSCLE_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return muscle
    return None


def entries_for_muscle_tab(entries: list[WorkoutEntry], muscle: str) -> list[WorkoutEntry]:
    """Return only workouts logged on the given muscle tab."""
    return [e for e in entries if e.muscle == muscle]


def find_mislogged_entries(
    entries: list[WorkoutEntry],
    *,
    expected_muscle: str | None = None,
    logged_muscle: str | None = None,
) -> list[dict[str, str | float]]:
    """Find entries where the exercise catalog muscle does not match the logged tab.

    - expected_muscle: exercises that belong on this tab but were logged elsewhere
    - logged_muscle: exercises logged on this tab but belong elsewhere
    """
    results: list[dict[str, str | float]] = []
    for entry in entries:
        catalog = _catalog_for_entry(entry)
        if catalog is None:
            continue
        if catalog.primary_muscle == entry.muscle:
            continue

        if expected_muscle and catalog.primary_muscle == expected_muscle:
            results.append(_mislog_dict(entry, catalog.primary_muscle, kind="wrong_tab"))
        elif logged_muscle and entry.muscle == logged_muscle:
            results.append(
                _mislog_dict(entry, catalog.primary_muscle, kind="wrong_exercise_on_tab")
            )

    return results


def _mislog_dict(entry: WorkoutEntry, expected_muscle: str, *, kind: str) -> dict[str, str | float]:
    if kind == "wrong_tab":
        message = (
            f"'{entry.exercise}' belongs on the {expected_muscle} tab "
            f"but was logged on {entry.muscle} ({entry.source_row}). "
            f"Move this entry to the {expected_muscle} tab."
        )
    else:
        message = (
            f"'{entry.exercise}' belongs on the {expected_muscle} tab "
            f"but was logged on {entry.muscle} ({entry.source_row}). "
            f"Move this entry to the {expected_muscle} tab."
        )
    return {
        "exercise": entry.exercise,
        "logged_on_tab": entry.muscle,
        "expected_tab": expected_muscle,
        "date": str(entry.workout_date),
        "weight": entry.weight,
        "source_row": entry.source_row,
        "message": message,
    }


def _catalog_for_entry(entry: WorkoutEntry):
    if entry.exercise_id:
        match = exercise_by_id(entry.exercise_id)
        if match:
            return match
    return exercise_by_name(entry.exercise)
