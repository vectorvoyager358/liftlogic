"""Domain models for workout data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class WorkoutInput:
    """Validated, normalized workout data ready for persistence."""

    workout_date: date
    muscle: str
    exercise: str
    weight: float
    exercise_id: str = ""
    notes: str = ""
    source_row: str = ""
    log_id: str = ""


@dataclass(frozen=True)
class WorkoutEntry:
    log_id: str
    workout_date: date
    muscle: str
    exercise_id: str
    exercise: str
    weight: float
    notes: str
    source_row: str


@dataclass(frozen=True)
class PersonalRecord:
    exercise_id: str
    exercise: str
    weight: float
    workout_date: date
    unit: str = "lb"  # metric for the logged value (lb, steps, minutes, miles, …)


@dataclass(frozen=True)
class Goal:
    goal_id: str
    goal_type: str  # Exercise | Muscle
    exercise: str
    muscle: str
    target: float
    unit: str
    target_date: date | None
    status: str
    notes: str


@dataclass(frozen=True)
class GoalProgress:
    goal_id: str
    goal_type: str
    label: str
    target: float
    current: float
    unit: str
    progress_pct: float
    status: str  # completed | on_track | behind | paused
    target_date: date | None
    detail: str
