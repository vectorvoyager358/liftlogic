"""Dashboard service — computes analytics and writes to the Analytics sheet tab."""

from __future__ import annotations

from datetime import date
from typing import Any

from liftlogic.analytics import (
    DashboardSummary,
    Trend,
    TrendResult,
    build_dashboard_summary,
    detect_trend,
    exercise_progressions,
)
from liftlogic.constants import ANALYTICS_SHEET, DASHBOARD_LAST_REFRESHED_CELL
from liftlogic.models import WorkoutEntry
from liftlogic.sheets.client import SheetsClient


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_analytics(
    entries: list[WorkoutEntry],
    as_of: date | None = None,
) -> tuple[DashboardSummary, dict[str, TrendResult]]:
    """Return dashboard summary and per-exercise trend results."""
    summary = build_dashboard_summary(entries, as_of=as_of)
    progressions = exercise_progressions(entries)
    trends = {key: detect_trend(prog) for key, prog in progressions.items()}
    return summary, trends


def refresh_analytics_tab(
    client: SheetsClient,
    spreadsheet_id: str,
    entries: list[WorkoutEntry],
    as_of: date | None = None,
) -> None:
    """Clear and rewrite the Analytics sheet tab with computed stats.

    Also updates the Dashboard's last-refreshed timestamp so users can see
    when analytics were last computed.
    """
    today = as_of or date.today()
    summary, trends = compute_analytics(entries, as_of=as_of)
    rows = _build_analytics_rows(summary, trends, today)
    client.clear_values(spreadsheet_id, f"{ANALYTICS_SHEET}!A:Z")
    client.update_values(spreadsheet_id, f"{ANALYTICS_SHEET}!A1", rows)

    # Stamp the Dashboard subtitle with the refresh timestamp
    timestamp = f"Live · synced from muscle tabs · refreshed {today}  ·  {len(entries)} log entries"
    client.update_values(
        spreadsheet_id,
        DASHBOARD_LAST_REFRESHED_CELL,
        [[timestamp]],
    )


def format_stats(
    entries: list[WorkoutEntry],
    as_of: date | None = None,
) -> str:
    """Return a human-readable stats summary for terminal output."""
    if not entries:
        return "No workout data found. Log some workouts first."

    summary, trends = compute_analytics(entries, as_of=as_of)
    return _format_summary(summary, trends)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_summary(summary: DashboardSummary, trends: dict[str, TrendResult]) -> str:
    lines: list[str] = []

    lines.append("=" * 50)
    lines.append("  LiftLogic — Workout Stats")
    lines.append("=" * 50)

    lines.append("\nOverall")
    lines.append(f"  Total workouts      {summary.total_workouts}")
    lines.append(f"  This week           {summary.workouts_this_week}")
    lines.append(f"  This month          {summary.workouts_this_month}")
    lines.append(f"  Current streak      {summary.current_streak} day(s)")

    if summary.personal_records:
        lines.append("\nPersonal Records")
        for pr in summary.personal_records:
            lines.append(f"  {pr.exercise:<30} {pr.weight:>8.0f} {pr.unit:<8}  ({pr.workout_date})")

    if summary.recent_prs:
        lines.append("\nRecent PRs (last 30 days)")
        for pr in summary.recent_prs:
            lines.append(f"  {pr.exercise:<30} {pr.weight:>8.0f} {pr.unit:<8}  ({pr.workout_date})")

    if summary.muscle_session_counts:
        lines.append("\nMuscle Frequency (all time)")
        for muscle, count in sorted(summary.muscle_session_counts.items()):
            last = summary.last_trained_per_muscle.get(muscle)
            last_str = f"last: {last}" if last else ""
            lines.append(f"  {muscle:<14} {count:>3} session(s)  {last_str}")

    active_trends = {
        k: v
        for k, v in trends.items()
        if v.trend in (Trend.IMPROVING, Trend.DECLINING, Trend.PLATEAU)
    }
    if active_trends:
        lines.append("\nExercise Trends")
        for key, result in sorted(active_trends.items(), key=lambda x: x[0]):
            icon = {"improving": "↑", "declining": "↓", "plateau": "→"}.get(result.trend.value, " ")
            lines.append(f"  {icon} {result.message}")

    lines.append("=" * 50)
    return "\n".join(lines)


def _build_analytics_rows(
    summary: DashboardSummary,
    trends: dict[str, TrendResult],
    as_of: date,
) -> list[list[Any]]:
    rows: list[list[Any]] = []

    rows.append(["LiftLogic Analytics", f"Updated: {as_of}"])
    rows.append([])

    rows.append(["OVERALL STATISTICS"])
    rows.append(["Metric", "Value"])
    rows.append(["Total workouts", summary.total_workouts])
    rows.append(["Workouts this week", summary.workouts_this_week])
    rows.append(["Workouts this month", summary.workouts_this_month])
    rows.append(["Current streak (days)", summary.current_streak])
    rows.append([])

    rows.append(["PERSONAL RECORDS"])
    rows.append(["Exercise", "Best Value", "Unit", "Date"])
    for pr in summary.personal_records:
        rows.append([pr.exercise, pr.weight, pr.unit, str(pr.workout_date)])
    rows.append([])

    rows.append(["MUSCLE FREQUENCY"])
    rows.append(["Muscle", "Sessions", "Last Trained"])
    for muscle, count in sorted(summary.muscle_session_counts.items()):
        last = summary.last_trained_per_muscle.get(muscle, "")
        rows.append([muscle, count, str(last)])
    rows.append([])

    rows.append(["EXERCISE TRENDS"])
    rows.append(["Exercise", "Trend", "Change", "Sessions Analysed", "Detail"])
    for key, result in sorted(trends.items(), key=lambda x: x[0]):
        if result.trend == Trend.INSUFFICIENT_DATA:
            continue
        rows.append(
            [
                key,
                result.trend.value,
                round(result.weight_change, 1),
                result.sessions_analysed,
                result.message,
            ]
        )

    return rows
