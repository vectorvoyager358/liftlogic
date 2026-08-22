"""Workout analytics — PR detection, streaks, trends, and plateau detection."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from liftlogic.exercises import exercise_metric
from liftlogic.models import PersonalRecord, WorkoutEntry


# ---------------------------------------------------------------------------
# Personal records
# ---------------------------------------------------------------------------


def calculate_personal_records(entries: list[WorkoutEntry]) -> list[PersonalRecord]:
    """Return the max-weight PR per exercise. Most recent date wins on ties."""
    best: dict[str, PersonalRecord] = {}

    for entry in entries:
        if entry.weight <= 0:
            continue

        key = entry.exercise_id or entry.exercise
        current = best.get(key)
        unit = exercise_metric(entry.exercise_id or entry.exercise)

        if current is None:
            best[key] = PersonalRecord(
                exercise_id=entry.exercise_id,
                exercise=entry.exercise,
                weight=entry.weight,
                workout_date=entry.workout_date,
                unit=unit,
            )
            continue

        if entry.weight > current.weight or (
            entry.weight == current.weight and entry.workout_date > current.workout_date
        ):
            best[key] = PersonalRecord(
                exercise_id=entry.exercise_id,
                exercise=entry.exercise,
                weight=entry.weight,
                workout_date=entry.workout_date,
                unit=unit,
            )

    return sorted(best.values(), key=lambda pr: (pr.unit, pr.exercise))


# ---------------------------------------------------------------------------
# Workout counts
# ---------------------------------------------------------------------------


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


def last_trained_per_muscle(entries: list[WorkoutEntry]) -> dict[str, date]:
    """Return the most recent session date per muscle group."""
    latest: dict[str, date] = {}
    for entry in entries:
        if entry.muscle not in latest or entry.workout_date > latest[entry.muscle]:
            latest[entry.muscle] = entry.workout_date
    return latest


# ---------------------------------------------------------------------------
# Training streak
# ---------------------------------------------------------------------------


def calculate_streak(entries: list[WorkoutEntry], as_of: date | None = None) -> int:
    """Return the current consecutive-day training streak ending on or before as_of."""
    if not entries:
        return 0

    reference = as_of or date.today()
    workout_dates = sorted({entry.workout_date for entry in entries}, reverse=True)

    # Allow streak to include today or yesterday (don't break streak just because
    # today's workout hasn't been logged yet).
    if workout_dates[0] < reference - timedelta(days=1):
        return 0

    streak = 1
    for i in range(1, len(workout_dates)):
        if workout_dates[i - 1] - workout_dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# Exercise progression
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExerciseSession:
    workout_date: date
    weight: float
    notes: str


@dataclass
class ExerciseProgression:
    exercise_id: str
    exercise: str
    sessions: list[ExerciseSession] = field(default_factory=list)

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def best_weight(self) -> float:
        return max((s.weight for s in self.sessions), default=0.0)

    @property
    def latest_weight(self) -> float:
        if not self.sessions:
            return 0.0
        return sorted(self.sessions, key=lambda s: s.workout_date)[-1].weight

    @property
    def previous_weight(self) -> float:
        ordered = sorted(self.sessions, key=lambda s: s.workout_date)
        if len(ordered) < 2:
            return 0.0
        return ordered[-2].weight

    @property
    def last_performed(self) -> date | None:
        if not self.sessions:
            return None
        return max(s.workout_date for s in self.sessions)

    @property
    def weight_change(self) -> float:
        """Change from previous session to latest session."""
        return self.latest_weight - self.previous_weight


def exercise_progressions(entries: list[WorkoutEntry]) -> dict[str, ExerciseProgression]:
    """Build a progression timeline per exercise (keyed by exercise_id or name)."""
    progressions: dict[str, ExerciseProgression] = {}

    for entry in entries:
        if entry.weight <= 0:
            continue
        key = entry.exercise_id or entry.exercise
        if key not in progressions:
            progressions[key] = ExerciseProgression(
                exercise_id=entry.exercise_id,
                exercise=entry.exercise,
            )
        progressions[key].sessions.append(
            ExerciseSession(
                workout_date=entry.workout_date,
                weight=entry.weight,
                notes=entry.notes,
            )
        )

    return progressions


# ---------------------------------------------------------------------------
# Trend and plateau detection
# ---------------------------------------------------------------------------


class Trend(Enum):
    IMPROVING = "improving"
    DECLINING = "declining"
    PLATEAU = "plateau"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class TrendResult:
    trend: Trend
    sessions_analysed: int
    weight_change: float  # latest - first in window
    message: str


def detect_trend(
    progression: ExerciseProgression,
    window: int = 4,
) -> TrendResult:
    """
    Analyse the last `window` sessions for a single exercise.

    - IMPROVING  : latest weight > first weight in window
    - DECLINING  : latest weight < first weight in window
    - PLATEAU    : all weights within ±2.5 lb/kg of each other across window
    - INSUFFICIENT_DATA : fewer than 2 sessions available
    """
    ordered = sorted(progression.sessions, key=lambda s: s.workout_date)
    recent = ordered[-window:]

    if len(recent) < 2:
        return TrendResult(
            trend=Trend.INSUFFICIENT_DATA,
            sessions_analysed=len(recent),
            weight_change=0.0,
            message="Not enough data to detect a trend",
        )

    weights = [s.weight for s in recent]
    change = weights[-1] - weights[0]
    spread = max(weights) - min(weights)

    if spread <= 2.5:
        return TrendResult(
            trend=Trend.PLATEAU,
            sessions_analysed=len(recent),
            weight_change=change,
            message=(
                f"Weight has stayed within {spread:.1f} lb across the last {len(recent)} sessions"
            ),
        )

    if change > 0:
        return TrendResult(
            trend=Trend.IMPROVING,
            sessions_analysed=len(recent),
            weight_change=change,
            message=f"Up {change:+.1f} lb over last {len(recent)} sessions",
        )

    return TrendResult(
        trend=Trend.DECLINING,
        sessions_analysed=len(recent),
        weight_change=change,
        message=f"Down {change:+.1f} lb over last {len(recent)} sessions",
    )


def detect_plateau(
    progression: ExerciseProgression,
    min_sessions: int = 3,
    tolerance: float = 2.5,
) -> bool:
    """Return True if the last min_sessions have all been within tolerance of each other."""
    ordered = sorted(progression.sessions, key=lambda s: s.workout_date)
    recent = ordered[-min_sessions:]
    if len(recent) < min_sessions:
        return False
    weights = [s.weight for s in recent]
    return (max(weights) - min(weights)) <= tolerance


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


@dataclass
class DashboardSummary:
    total_workouts: int
    workouts_this_week: int
    workouts_this_month: int
    current_streak: int
    personal_records: list[PersonalRecord]
    muscle_session_counts: dict[str, int]
    last_trained_per_muscle: dict[str, date]
    recent_prs: list[PersonalRecord]  # PRs set in last 30 days


def build_dashboard_summary(
    entries: list[WorkoutEntry],
    as_of: date | None = None,
) -> DashboardSummary:
    today = as_of or date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    prs = calculate_personal_records(entries)
    recent_cutoff = today - timedelta(days=30)
    recent_prs = [pr for pr in prs if pr.workout_date >= recent_cutoff]

    return DashboardSummary(
        total_workouts=count_unique_workout_dates(entries),
        workouts_this_week=count_workouts_in_range(entries, week_start, today),
        workouts_this_month=count_workouts_in_range(entries, month_start, today),
        current_streak=calculate_streak(entries, as_of=today),
        personal_records=prs,
        muscle_session_counts=muscle_session_counts(entries),
        last_trained_per_muscle=last_trained_per_muscle(entries),
        recent_prs=recent_prs,
    )
