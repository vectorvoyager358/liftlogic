"""Goal tracking — read goals from the sheet and compute progress."""

from __future__ import annotations

from datetime import date, timedelta

from liftlogic.analytics import calculate_personal_records, count_workouts_in_range
from liftlogic.constants import GOAL_COLUMNS
from liftlogic.exercises import exercise_by_name, exercise_metric
from liftlogic.models import Goal, GoalProgress, WorkoutEntry
from liftlogic.parsing import parse_date, parse_weight


def get_goals(client, spreadsheet_id: str) -> list[Goal]:
    from liftlogic.constants import GOALS_SHEET

    rows = client.get_values(spreadsheet_id, f"{GOALS_SHEET}!A2:I")
    goals: list[Goal] = []
    for row in rows:
        goal = parse_goal_row(row)
        if goal is not None:
            goals.append(goal)
    return goals


def parse_goal_row(row: list[str]) -> Goal | None:
    padded = row + [""] * (len(GOAL_COLUMNS) - len(row))
    (
        goal_id,
        goal_type,
        exercise,
        muscle,
        raw_target,
        unit,
        raw_target_date,
        status,
        notes,
    ) = padded[:9]

    goal_type = goal_type.strip()
    if not goal_type:
        return None

    target = parse_weight(raw_target)
    if target is None or target <= 0:
        return None

    normalized_type = goal_type.casefold()
    if normalized_type == "exercise" and not exercise.strip():
        return None
    if normalized_type == "muscle" and not muscle.strip():
        return None

    return Goal(
        goal_id=goal_id.strip(),
        goal_type=goal_type.strip(),
        exercise=exercise.strip(),
        muscle=muscle.strip(),
        target=target,
        unit=unit.strip() or _default_unit(goal_type),
        target_date=parse_date(raw_target_date),
        status=status.strip() or "Active",
        notes=notes.strip(),
    )


def compute_goal_progress(
    goal: Goal,
    entries: list[WorkoutEntry],
    *,
    as_of: date | None = None,
) -> GoalProgress:
    today = as_of or date.today()

    if goal.status.casefold() == "paused":
        return GoalProgress(
            goal_id=goal.goal_id,
            goal_type=goal.goal_type,
            label=_goal_label(goal),
            target=goal.target,
            current=0.0,
            unit=goal.unit,
            progress_pct=0.0,
            status="paused",
            target_date=goal.target_date,
            detail="Goal is paused.",
        )

    normalized_type = goal.goal_type.casefold()
    if normalized_type == "exercise":
        return _exercise_goal_progress(goal, entries, today=today)
    if normalized_type == "muscle":
        return _muscle_goal_progress(goal, entries, today=today)
    return GoalProgress(
        goal_id=goal.goal_id,
        goal_type=goal.goal_type,
        label=_goal_label(goal),
        target=goal.target,
        current=0.0,
        unit=goal.unit,
        progress_pct=0.0,
        status="behind",
        target_date=goal.target_date,
        detail=f"Unknown goal type: {goal.goal_type}",
    )


def compute_all_goal_progress(
    goals: list[Goal],
    entries: list[WorkoutEntry],
    *,
    as_of: date | None = None,
) -> list[GoalProgress]:
    active = [goal for goal in goals if goal.status.casefold() != "paused"]
    return [compute_goal_progress(goal, entries, as_of=as_of) for goal in active]


def format_goal_progress(progress: GoalProgress) -> str:
    label = progress.label
    if progress.status == "completed":
        return f"{label}: {progress.current:g} {progress.unit} — goal reached (target {progress.target:g})"
    if progress.status == "paused":
        return f"{label}: paused"
    return (
        f"{label}: {progress.current:g}/{progress.target:g} {progress.unit} "
        f"({progress.progress_pct:.0f}%) — {progress.detail}"
    )


def _exercise_goal_progress(
    goal: Goal,
    entries: list[WorkoutEntry],
    *,
    today: date,
) -> GoalProgress:
    catalog = exercise_by_name(goal.exercise)
    exercise_id = catalog.exercise_id if catalog else ""
    unit = goal.unit or exercise_metric(exercise_id or goal.exercise)

    matching = [entry for entry in entries if _matches_exercise(entry, goal.exercise, exercise_id)]
    prs = calculate_personal_records(matching)
    current = prs[0].weight if prs else 0.0
    progress_pct = min(100.0, (current / goal.target) * 100) if goal.target > 0 else 0.0
    status = _progress_status(current, goal.target, goal.target_date, today=today)

    if current >= goal.target:
        detail = f"Personal record is {current:g} {unit}."
    else:
        remaining = goal.target - current
        detail = f"{remaining:g} {unit} to go (current PR: {current:g} {unit})."

    return GoalProgress(
        goal_id=goal.goal_id,
        goal_type=goal.goal_type,
        label=goal.exercise,
        target=goal.target,
        current=current,
        unit=unit,
        progress_pct=progress_pct,
        status=status,
        target_date=goal.target_date,
        detail=detail,
    )


def _muscle_goal_progress(
    goal: Goal,
    entries: list[WorkoutEntry],
    *,
    today: date,
) -> GoalProgress:
    week_start = today - timedelta(days=today.weekday())
    muscle_entries = [entry for entry in entries if entry.muscle == goal.muscle]
    current = float(count_workouts_in_range(muscle_entries, week_start, today))
    progress_pct = min(100.0, (current / goal.target) * 100) if goal.target > 0 else 0.0
    status = _progress_status(current, goal.target, goal.target_date, today=today)

    if current >= goal.target:
        detail = f"Trained {goal.muscle} {int(current)} time(s) this week."
    else:
        remaining = goal.target - current
        detail = (
            f"{remaining:g} more session(s) needed this week "
            f"({int(current)}/{int(goal.target)} so far)."
        )

    return GoalProgress(
        goal_id=goal.goal_id,
        goal_type=goal.goal_type,
        label=goal.muscle,
        target=goal.target,
        current=current,
        unit=goal.unit or "sessions/week",
        progress_pct=progress_pct,
        status=status,
        target_date=goal.target_date,
        detail=detail,
    )


def _matches_exercise(entry: WorkoutEntry, exercise_name: str, exercise_id: str) -> bool:
    if exercise_id and entry.exercise_id == exercise_id:
        return True
    return entry.exercise.casefold() == exercise_name.casefold()


def _goal_label(goal: Goal) -> str:
    if goal.goal_type.casefold() == "muscle":
        return goal.muscle
    return goal.exercise


def _default_unit(goal_type: str) -> str:
    return "sessions/week" if goal_type.casefold() == "muscle" else "lb"


def _progress_status(
    current: float,
    target: float,
    target_date: date | None,
    *,
    today: date,
) -> str:
    if current >= target:
        return "completed"
    if target_date and target_date < today:
        return "behind"
    if target <= 0:
        return "behind"
    ratio = current / target
    if ratio >= 0.75:
        return "on_track"
    if target_date:
        days_left = (target_date - today).days
        if days_left <= 14 and ratio < 0.5:
            return "behind"
    return "behind" if ratio < 0.5 else "on_track"
