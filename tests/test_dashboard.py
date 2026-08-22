"""Tests for the dashboard service."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call

from liftlogic.analytics import Trend
from liftlogic.dashboard import (
    compute_analytics,
    format_stats,
    refresh_analytics_tab,
    _build_analytics_rows,
)
from liftlogic.models import WorkoutEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    exercise_id: str,
    exercise: str,
    weight: float,
    workout_date: date,
    muscle: str = "Chest",
    notes: str = "",
) -> WorkoutEntry:
    return WorkoutEntry(
        log_id="L000001",
        workout_date=workout_date,
        muscle=muscle,
        exercise_id=exercise_id,
        exercise=exercise,
        weight=weight,
        notes=notes,
        source_row="Chest!A2",
    )


D = date(2024, 1, 1)


def _bench(weight: float, delta_days: int = 0) -> WorkoutEntry:
    return _entry(
        "EX001", "Bench Press", weight, D + __import__("datetime").timedelta(days=delta_days)
    )


# ---------------------------------------------------------------------------
# compute_analytics
# ---------------------------------------------------------------------------


class TestComputeAnalytics:
    def test_returns_summary_and_trends(self):
        entries = [_bench(100, 0), _bench(110, 1), _bench(120, 2), _bench(125, 3)]
        summary, trends = compute_analytics(
            entries, as_of=D + __import__("datetime").timedelta(days=3)
        )

        assert summary.total_workouts == 4
        assert "EX001" in trends or "Bench Press" in trends

    def test_empty_entries(self):
        summary, trends = compute_analytics([])
        assert summary.total_workouts == 0
        assert trends == {}

    def test_trends_improving(self):
        from datetime import timedelta

        entries = [_bench(100 + i * 5, i) for i in range(5)]
        _, trends = compute_analytics(entries, as_of=D + timedelta(days=4))
        result = trends.get("EX001") or trends.get("Bench Press")
        assert result is not None
        assert result.trend == Trend.IMPROVING

    def test_trends_plateau(self):
        from datetime import timedelta

        entries = [_bench(100, i) for i in range(5)]
        _, trends = compute_analytics(entries, as_of=D + timedelta(days=4))
        result = trends.get("EX001") or trends.get("Bench Press")
        assert result is not None
        assert result.trend == Trend.PLATEAU


# ---------------------------------------------------------------------------
# format_stats
# ---------------------------------------------------------------------------


class TestFormatStats:
    def test_empty_returns_helpful_message(self):
        output = format_stats([])
        assert "No workout data" in output

    def test_contains_overview_section(self):
        from datetime import timedelta

        entries = [_bench(100 + i * 5, i) for i in range(4)]
        output = format_stats(entries, as_of=D + timedelta(days=3))
        assert "Total workouts" in output
        assert "Personal Records" in output

    def test_contains_trend_section_when_enough_data(self):
        from datetime import timedelta

        entries = [_bench(100 + i * 10, i) for i in range(5)]
        output = format_stats(entries, as_of=D + timedelta(days=4))
        assert "Exercise Trends" in output
        assert "↑" in output

    def test_contains_muscle_frequency(self):
        from datetime import timedelta

        entries = [
            _entry("EX001", "Bench", 100, D, muscle="Chest"),
            _entry("EX002", "Row", 80, D + timedelta(days=1), muscle="Back"),
        ]
        output = format_stats(entries, as_of=D + timedelta(days=1))
        assert "Chest" in output
        assert "Back" in output

    def test_no_decline_icon_when_improving(self):
        from datetime import timedelta

        entries = [_bench(100 + i * 10, i) for i in range(5)]
        output = format_stats(entries, as_of=D + timedelta(days=4))
        assert "↓" not in output


# ---------------------------------------------------------------------------
# _build_analytics_rows
# ---------------------------------------------------------------------------


class TestBuildAnalyticsRows:
    def _make_summary_and_trends(self):
        from datetime import timedelta

        entries = [
            _entry("EX001", "Bench Press", 100 + i * 5, D + timedelta(days=i), muscle="Chest")
            for i in range(5)
        ]
        return compute_analytics(entries, as_of=D + timedelta(days=4))

    def test_returns_list_of_rows(self):
        summary, trends = self._make_summary_and_trends()
        rows = _build_analytics_rows(summary, trends, D)
        assert isinstance(rows, list)
        assert len(rows) > 0
        assert all(isinstance(r, list) for r in rows)

    def test_header_row_contains_title(self):
        summary, trends = self._make_summary_and_trends()
        rows = _build_analytics_rows(summary, trends, D)
        header = rows[0]
        assert "LiftLogic Analytics" in header

    def test_pr_section_present(self):
        summary, trends = self._make_summary_and_trends()
        rows = _build_analytics_rows(summary, trends, D)
        flat = [cell for row in rows for cell in row if isinstance(cell, str)]
        assert "PERSONAL RECORDS" in flat

    def test_trends_section_present(self):
        summary, trends = self._make_summary_and_trends()
        rows = _build_analytics_rows(summary, trends, D)
        flat = [cell for row in rows for cell in row if isinstance(cell, str)]
        assert "EXERCISE TRENDS" in flat

    def test_insufficient_data_rows_excluded(self):
        from liftlogic.analytics import TrendResult
        from liftlogic.analytics import DashboardSummary

        summary = DashboardSummary(
            total_workouts=1,
            workouts_this_week=1,
            workouts_this_month=1,
            current_streak=1,
            personal_records=[],
            muscle_session_counts={},
            last_trained_per_muscle={},
            recent_prs=[],
        )
        trends = {
            "EX001": TrendResult(
                trend=Trend.INSUFFICIENT_DATA,
                sessions_analysed=1,
                weight_change=0.0,
                message="Not enough data to detect a trend",
            )
        }
        rows = _build_analytics_rows(summary, trends, D)
        flat = [cell for row in rows for cell in row if isinstance(cell, str)]
        assert "Not enough data to detect a trend" not in flat


# ---------------------------------------------------------------------------
# refresh_analytics_tab
# ---------------------------------------------------------------------------


class TestRefreshAnalyticsTab:
    def _make_client(self):
        client = MagicMock()
        return client

    def test_calls_clear_then_update(self):
        from datetime import timedelta

        entries = [_bench(100 + i * 5, i) for i in range(4)]
        client = self._make_client()
        spreadsheet_id = "sheet123"

        refresh_analytics_tab(client, spreadsheet_id, entries, as_of=D + timedelta(days=3))

        client.clear_values.assert_called_once()
        # update_values is called twice: once for Analytics tab, once for Dashboard timestamp
        assert client.update_values.call_count == 2

    def test_clear_called_before_update(self):
        from datetime import timedelta

        entries = [_bench(100, i) for i in range(4)]
        client = self._make_client()
        manager = MagicMock()
        client.clear_values = manager.clear
        client.update_values = manager.update

        refresh_analytics_tab(client, "sheet123", entries, as_of=D + timedelta(days=3))

        assert manager.mock_calls[0] == call.clear("sheet123", "Analytics!A:Z")
        assert manager.mock_calls[1][0] == "update"

    def test_correct_spreadsheet_id_used(self):
        from datetime import timedelta

        entries = [_bench(100, i) for i in range(4)]
        client = self._make_client()

        refresh_analytics_tab(client, "my-sheet-id", entries, as_of=D + timedelta(days=3))

        assert client.clear_values.call_args[0][0] == "my-sheet-id"
        assert client.update_values.call_args[0][0] == "my-sheet-id"
