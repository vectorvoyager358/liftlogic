"""Tests for NVIDIA NIM AI integration."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from liftlogic.ai import (
    DEFAULT_NIM_MODEL,
    NimConfig,
    _sanitize_response,
    ask_question,
    build_workout_context,
    generate_insights,
    load_nim_config,
    write_ai_insights_tab,
)
from liftlogic.models import Goal, WorkoutEntry


def _entry(
    exercise: str,
    weight: float,
    workout_date: date,
    muscle: str = "Chest",
    notes: str = "",
    exercise_id: str = "CH001",
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


class TestLoadNimConfig:
    def test_loads_json_format(self, tmp_path):
        config_path = tmp_path / "nim.json"
        config_path.write_text(
            json.dumps(
                {
                    "api_key": "nvapi-test-key",
                    "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                }
            )
        )
        cfg = load_nim_config(tmp_path)
        assert cfg.api_key == "nvapi-test-key"
        assert cfg.model == "nvidia/nemotron-3.5-lightning-30b-a3b"

    def test_loads_env_style_format(self, tmp_path):
        config_path = tmp_path / "nim.json"
        config_path.write_text("NVIDIA_API_KEY=nvapi-env-key\n")
        cfg = load_nim_config(tmp_path)
        assert cfg.api_key == "nvapi-env-key"
        assert cfg.model == DEFAULT_NIM_MODEL

    def test_finds_file_with_trailing_space_in_name(self, tmp_path):
        config_path = tmp_path / "nim.json "
        config_path.write_text("NVIDIA_API_KEY=nvapi-spaced-key\n")
        cfg = load_nim_config(tmp_path)
        assert cfg.api_key == "nvapi-spaced-key"

    def test_missing_key_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No NVIDIA API key"):
            load_nim_config(tmp_path)


class TestBuildWorkoutContext:
    def test_includes_summary_and_trends(self):
        entries = [
            _entry("Barbell Bench Press", 185, date(2026, 8, 1)),
            _entry("Barbell Bench Press", 200, date(2026, 8, 10)),
        ]
        ctx = build_workout_context(entries, as_of=date(2026, 8, 10))
        assert ctx["summary"]["total_workouts"] == 2
        assert len(ctx["personal_records"]) == 1
        assert ctx["personal_records"][0]["unit"] == "lb"
        assert "exercise_trends" in ctx

    def test_includes_recent_notes(self):
        entries = [
            _entry("Barbell Bench Press", 185, date(2026, 8, 1), notes="Felt strong"),
        ]
        ctx = build_workout_context(entries, as_of=date(2026, 8, 1))
        assert len(ctx["recent_notes"]) == 1
        assert ctx["recent_notes"][0]["note"] == "Felt strong"

    def test_empty_entries(self):
        ctx = build_workout_context([], as_of=date(2026, 8, 1))
        assert ctx["summary"]["total_workouts"] == 0
        assert ctx["personal_records"] == []

    def test_trends_use_exercise_names_not_ids(self):
        entries = [
            _entry("Lat Pulldown", 85, date(2026, 8, 1), muscle="Back", exercise_id="BK001"),
            _entry("Lat Pulldown", 85, date(2026, 8, 10), muscle="Back", exercise_id="BK001"),
        ]
        ctx = build_workout_context(entries, as_of=date(2026, 8, 10))
        assert ctx["exercise_trends"]
        assert ctx["exercise_trends"][0]["exercise"] == "Lat Pulldown"
        assert "BK001" not in ctx["exercise_trends"][0]["exercise"]

    def test_includes_exercise_history(self):
        entries = [
            _entry("Barbell Bench Press", 185, date(2026, 8, 1)),
            _entry("Barbell Bench Press", 195, date(2026, 8, 10)),
            _entry("Barbell Bench Press", 200, date(2026, 8, 15)),
        ]
        ctx = build_workout_context(entries, as_of=date(2026, 8, 15))
        assert "Barbell Bench Press" in ctx["exercise_history"]
        assert len(ctx["exercise_history"]["Barbell Bench Press"]) == 3

    def test_retrieved_notes_for_note_question(self):
        entries = [
            _entry(
                "Lateral Raise",
                20,
                date(2026, 8, 10),
                muscle="Shoulders",
                notes="Shoulder felt tight",
            ),
        ]
        ctx = build_workout_context(
            entries,
            as_of=date(2026, 8, 15),
            question="What did I say about shoulder discomfort?",
        )
        assert len(ctx["retrieved_notes"]) >= 1

    def test_muscle_scope_limits_context_to_tab(self):
        entries = [
            _entry("Lateral Raise", 25, date(2026, 8, 21), muscle="Shoulders", exercise_id="SH002"),
            _entry("T-Bar", 55, date(2026, 8, 20), muscle="Back", exercise_id="BK999"),
        ]
        ctx = build_workout_context(
            entries,
            as_of=date(2026, 8, 22),
            question="What shoulder exercises have I done recently?",
        )
        assert ctx["muscle_scope"]["muscle"] == "Shoulders"
        scoped_exercises = {w["exercise"] for w in ctx["muscle_scope"]["workouts"]}
        assert scoped_exercises == {"Lateral Raise"}
        assert "T-Bar" not in {pr["exercise"] for pr in ctx["personal_records"]}

    def test_goal_progress_in_context(self):
        entries = [
            _entry("Barbell Bench Press", 185, date(2026, 8, 20)),
        ]
        goals = [
            Goal(
                goal_id="G001",
                goal_type="Exercise",
                exercise="Barbell Bench Press",
                muscle="",
                target=225,
                unit="lb",
                target_date=date(2026, 12, 31),
                status="Active",
                notes="",
            )
        ]
        ctx = build_workout_context(entries, as_of=date(2026, 8, 21), goals=goals)
        assert len(ctx["goal_progress"]) == 1
        assert ctx["goal_progress"][0]["label"] == "Barbell Bench Press"
        assert ctx["goal_progress"][0]["current"] == 185


class TestSanitizeResponse:
    def test_passes_through_normal_answer(self):
        assert _sanitize_response("Your back looks good.") == "Your back looks good."

    def test_extracts_draft_from_thinking_trace(self):
        raw = (
            "Here's a thinking process:\n\n1. Analyze...\n\n"
            'Draft:\n"Your back training looks consistent."'
        )
        assert _sanitize_response(raw) == "Your back training looks consistent."


class TestAskQuestion:
    def test_empty_entries_returns_message(self):
        result = ask_question("How am I doing?", [], config=_test_config())
        assert "No workout data" in result

    @patch("liftlogic.ai._chat")
    def test_calls_chat_with_question(self, mock_chat):
        mock_chat.return_value = "Your chest is progressing well."
        entries = [_entry("Barbell Bench Press", 185, date(2026, 8, 1))]
        result = ask_question(
            "How is my chest?",
            entries,
            config=_test_config(),
            as_of=date(2026, 8, 1),
        )
        assert result == "Your chest is progressing well."
        mock_chat.assert_called_once()
        messages = mock_chat.call_args[0][1]
        assert messages[-1]["role"] == "user"
        assert "How is my chest?" in messages[-1]["content"]


class TestGenerateInsights:
    def test_empty_entries_returns_message(self):
        result = generate_insights([], config=_test_config())
        assert "No workout data" in result

    @patch("liftlogic.ai._chat")
    def test_calls_chat_for_summary(self, mock_chat):
        mock_chat.return_value = "Great consistency this week."
        entries = [_entry("Barbell Bench Press", 185, date(2026, 8, 1))]
        result = generate_insights(entries, config=_test_config(), as_of=date(2026, 8, 1))
        assert result == "Great consistency this week."
        messages = mock_chat.call_args[0][1]
        assert "coaching summary" in messages[-1]["content"].lower()


class TestWriteAiInsightsTab:
    def test_writes_and_unhides_tab(self):
        client = MagicMock()
        client.get_sheet_id.return_value = 42
        client._sheets.spreadsheets.return_value.batchUpdate.return_value.execute.return_value = {}

        write_ai_insights_tab(
            client,
            "sheet123",
            "Line one.\n\nLine two.",
            as_of=date(2026, 8, 22),
        )

        client.clear_values.assert_called_once()
        client.update_values.assert_called_once()
        rows = client.update_values.call_args[0][2]
        assert rows[0][0] == "LiftLogic AI Insights"
        assert rows[2] == ["Line one."]
        assert rows[3] == ["Line two."]


def _test_config() -> NimConfig:
    return NimConfig(api_key="nvapi-test")
