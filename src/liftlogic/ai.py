"""AI coach — NVIDIA NIM integration for workout insights and Q&A."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from liftlogic.analytics import (
    DashboardSummary,
    ExerciseProgression,
    Trend,
    TrendResult,
    calculate_personal_records,
    detect_trend,
    exercise_progressions,
)
from liftlogic.constants import AI_INSIGHTS_SHEET, MUSCLE_TABS
from liftlogic.dashboard import compute_analytics
from liftlogic.exercises import exercise_display_name, exercise_metric
from liftlogic.models import WorkoutEntry
from liftlogic.muscle_context import (
    detect_muscle_in_query,
    entries_for_muscle_tab,
    find_mislogged_entries,
)
from liftlogic.rag import looks_like_note_question, search_workout_knowledge
from liftlogic.sheets.client import SheetsClient

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NIM_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"

SYSTEM_PROMPT = """You are LiftLogic, a knowledgeable and encouraging fitness coach.

You receive structured workout analytics computed by a backend engine — never raw spreadsheet rows.
When retrieved_notes are provided, use them to answer questions about what the user wrote in their logs.
Use only the provided context to answer. If data is missing, say so clearly.

Guidelines:
- Be concise and actionable (2–4 short paragraphs unless the user asks for detail).
- Reference specific exercises, weights/units, dates, and trends from the context.
- Do not invent numbers or workouts not present in the context.
- If retrieved_notes entries have no "note" field, they are exercise/muscle matches only — do not describe note content for them.
- When muscle_scope is provided, list exercises ONLY from muscle_scope.workouts (the tab where they were logged). Never include exercises from other tabs, even if they work the same muscle secondarily or appear in global personal_records.
- When the user asks what exercises they did, list every row in muscle_scope.workouts — do not collapse or deduplicate by exercise name; include multiple entries on the same date if present.
- If mislogged_entries are present, call them out as possible logging mistakes and tell the user which tab each entry belongs on.
- Respond with your final answer only — no reasoning steps, no thinking process, no bullet analysis.
- For medical or injury questions, recommend consulting a professional.
"""


@dataclass(frozen=True)
class NimConfig:
    api_key: str
    model: str = DEFAULT_NIM_MODEL
    base_url: str = NIM_BASE_URL
    temperature: float = 1.0
    top_p: float = 0.95
    max_tokens: int = 1024


def load_nim_config(credentials_dir: str | Path = "credentials") -> NimConfig:
    """Load NVIDIA NIM credentials from credentials/nim.json or NVIDIA_API_KEY env."""
    base = Path(credentials_dir)
    config_path = _find_nim_config_path(base)

    api_key: str | None = None
    model = DEFAULT_NIM_MODEL
    base_url = NIM_BASE_URL
    temperature = 1.0
    top_p = 0.95
    max_tokens = 1024

    if config_path and config_path.exists():
        text = config_path.read_text().strip()
        if text.startswith("{"):
            data = json.loads(text)
            api_key = data.get("api_key") or data.get("NVIDIA_API_KEY")
            model = data.get("model", model)
            base_url = data.get("base_url", base_url)
            temperature = float(data.get("temperature", temperature))
            top_p = float(data.get("top_p", top_p))
            max_tokens = int(data.get("max_tokens", max_tokens))
        else:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key in ("NVIDIA_API_KEY", "api_key"):
                    api_key = value
                elif key == "model":
                    model = value
                elif key == "base_url":
                    base_url = value

    if not api_key:
        api_key = os.environ.get("NVIDIA_API_KEY")

    if not api_key:
        raise FileNotFoundError(
            f"No NVIDIA API key found. Save it to {base / 'nim.json'} "
            '(JSON: {"api_key": "nvapi-..."} or line: NVIDIA_API_KEY=nvapi-...) '
            "or set the NVIDIA_API_KEY environment variable."
        )

    return NimConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )


def build_workout_context(
    entries: list[WorkoutEntry],
    as_of: date | None = None,
    *,
    question: str | None = None,
) -> dict[str, Any]:
    """Serialize pre-computed analytics into a JSON-safe context for the LLM."""
    today = as_of or date.today()
    muscle_filter = detect_muscle_in_query(question) if question else None

    summary, trends = compute_analytics(entries, as_of=today)
    progressions = exercise_progressions(entries)

    neglected = _neglected_muscles(summary, today)
    recent_notes = _recent_notes(entries, today, limit=10)
    exercise_history = _exercise_session_history(progressions, limit_per_exercise=8)
    personal_records = calculate_personal_records(entries)
    recent_prs = summary.recent_prs

    retrieved_notes: list[dict[str, str | float]] = []
    if question:
        hits = search_workout_knowledge(
            question,
            entries,
            as_of=today,
            muscle_tab=muscle_filter,
        )
        if hits and (looks_like_note_question(question) or hits[0].score >= 1.5):
            retrieved_notes = [hit.to_dict() for hit in hits]

    muscle_scope: dict[str, Any] | None = None
    mislogged_entries: list[dict[str, str | float]] = []
    if muscle_filter:
        tab_entries = entries_for_muscle_tab(entries, muscle_filter)
        tab_progressions = exercise_progressions(tab_entries)
        tab_trends = {key: detect_trend(prog) for key, prog in tab_progressions.items()}
        tab_prs = calculate_personal_records(tab_entries)

        exercise_history = _exercise_session_history(tab_progressions, limit_per_exercise=8)
        trends = tab_trends
        personal_records = tab_prs
        recent_prs = [pr for pr in tab_prs if pr.workout_date >= today - timedelta(days=30)]
        recent_notes = _recent_notes(tab_entries, today, limit=10)

        muscle_scope = {
            "muscle": muscle_filter,
            "rule": (
                f"Only exercises logged on the {muscle_filter} tab count as "
                f"{muscle_filter.lower()} exercises."
            ),
            "session_count": summary.muscle_session_counts.get(muscle_filter, 0),
            "last_trained": str(summary.last_trained_per_muscle.get(muscle_filter, "")),
            "personal_records": [
                {
                    "exercise": pr.exercise,
                    "value": pr.weight,
                    "unit": pr.unit,
                    "date": str(pr.workout_date),
                }
                for pr in tab_prs
            ],
            "exercise_history": _exercise_session_history(tab_progressions, limit_per_exercise=8),
            "exercise_trends": _serialize_trends(tab_trends, tab_progressions),
            "workouts": [
                {
                    "date": str(e.workout_date),
                    "exercise": e.exercise,
                    "weight": e.weight,
                    "unit": exercise_metric(e.exercise_id or e.exercise),
                    "notes": e.notes.strip(),
                }
                for e in sorted(tab_entries, key=lambda x: x.workout_date, reverse=True)[:20]
            ],
        }

        mislogged_entries = _dedupe_mislogged(
            find_mislogged_entries(entries, expected_muscle=muscle_filter)
            + find_mislogged_entries(entries, logged_muscle=muscle_filter)
        )

    context: dict[str, Any] = {
        "as_of": str(today),
        "summary": {
            "total_workouts": summary.total_workouts,
            "workouts_this_week": summary.workouts_this_week,
            "workouts_this_month": summary.workouts_this_month,
            "current_streak_days": summary.current_streak,
        },
        "personal_records": [
            {
                "exercise": pr.exercise,
                "value": pr.weight,
                "unit": pr.unit,
                "date": str(pr.workout_date),
            }
            for pr in personal_records
        ],
        "recent_prs_last_30_days": [
            {
                "exercise": pr.exercise,
                "value": pr.weight,
                "unit": pr.unit,
                "date": str(pr.workout_date),
            }
            for pr in recent_prs
        ],
        "muscle_frequency": {
            muscle: {
                "sessions": count,
                "last_trained": str(summary.last_trained_per_muscle.get(muscle, "")),
            }
            for muscle, count in sorted(summary.muscle_session_counts.items())
        },
        "neglected_muscles": neglected,
        "exercise_trends": _serialize_trends(trends, progressions),
        "exercise_history": exercise_history,
        "recent_notes": recent_notes,
        "retrieved_notes": retrieved_notes,
    }
    if muscle_scope is not None:
        context["muscle_scope"] = muscle_scope
    if mislogged_entries:
        context["mislogged_entries"] = mislogged_entries
    return context


def ask_question(
    question: str,
    entries: list[WorkoutEntry],
    config: NimConfig | None = None,
    credentials_dir: str | Path = "credentials",
    as_of: date | None = None,
) -> str:
    """Answer a natural-language question using structured workout analytics."""
    if not entries:
        return "No workout data found. Log some workouts first, then try again."

    cfg = config or load_nim_config(credentials_dir)
    context = build_workout_context(entries, as_of=as_of, question=question.strip())
    context_json = json.dumps(context, indent=2)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Workout analytics context (JSON):\n{context_json}\n\nQuestion: {question.strip()}"
            ),
        },
    ]
    return _chat(cfg, messages)


def generate_insights(
    entries: list[WorkoutEntry],
    config: NimConfig | None = None,
    credentials_dir: str | Path = "credentials",
    as_of: date | None = None,
) -> str:
    """Generate a full coaching summary from structured analytics."""
    if not entries:
        return "No workout data found. Log some workouts first, then try again."

    cfg = config or load_nim_config(credentials_dir)
    context = build_workout_context(entries, as_of=as_of)
    context_json = json.dumps(context, indent=2)

    prompt = (
        "Based on the workout analytics context below, write a coaching summary with:\n"
        "1. Overall training consistency (streak, frequency this week/month)\n"
        "2. Highlights — recent PRs and improving exercises\n"
        "3. Areas needing attention — plateaus, declining trends, neglected muscles\n"
        "4. 2–3 specific, actionable recommendations for the next 1–2 weeks\n\n"
        f"Workout analytics context (JSON):\n{context_json}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return _chat(cfg, messages)


def write_ai_insights_tab(
    client: SheetsClient,
    spreadsheet_id: str,
    content: str,
    as_of: date | None = None,
) -> None:
    """Write generated insights to the AI_Insights tab and unhide it."""
    today = as_of or date.today()
    rows: list[list[Any]] = [
        ["LiftLogic AI Insights", f"Generated: {today}"],
        [],
    ]
    for paragraph in content.strip().split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            rows.append([paragraph])

    sheet_id = client.get_sheet_id(spreadsheet_id, AI_INSIGHTS_SHEET)
    client._sheets.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet_id, "hidden": False},
                        "fields": "hidden",
                    }
                }
            ]
        },
    ).execute()

    client.clear_values(spreadsheet_id, f"{AI_INSIGHTS_SHEET}!A:Z")
    client.update_values(spreadsheet_id, f"{AI_INSIGHTS_SHEET}!A1", rows)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_nim_config_path(credentials_dir: Path) -> Path | None:
    """Return path to nim.json, tolerating accidental trailing spaces in the filename."""
    exact = credentials_dir / "nim.json"
    if exact.exists():
        return exact
    for candidate in credentials_dir.glob("nim.json*"):
        if candidate.is_file():
            return candidate
    return exact  # for error messages when missing


def _chat(config: NimConfig, messages: list[dict[str, str]]) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            'NVIDIA NIM support requires the openai package. Install with: pip install -e ".[ai]"'
        ) from exc

    client = OpenAI(base_url=config.base_url, api_key=config.api_key)
    response = client.chat.completions.create(
        model=config.model,
        messages=messages,
        temperature=config.temperature,
        top_p=config.top_p,
        max_tokens=config.max_tokens,
        stream=False,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    message = response.choices[0].message
    content = message.content
    if not content:
        raise RuntimeError("NIM returned an empty response")
    return _sanitize_response(content.strip())


def _sanitize_response(content: str) -> str:
    """Strip leaked Nemotron reasoning traces if thinking was not fully disabled."""
    if "Here's a thinking process:" not in content and "**Analyze User Input:**" not in content:
        return content

    draft_markers = ("Draft:\n", "Draft:")
    for marker in draft_markers:
        if marker in content:
            tail = content.rsplit(marker, 1)[-1].strip()
            if tail.startswith('"'):
                tail = tail[1:]
            if tail.endswith('"'):
                tail = tail[:-1]
            if tail:
                return tail.strip()

    return content


def _dedupe_mislogged(
    items: list[dict[str, str | float]],
) -> list[dict[str, str | float]]:
    seen: set[str] = set()
    result: list[dict[str, str | float]] = []
    for item in items:
        key = f"{item['source_row']}|{item['exercise']}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _exercise_session_history(
    progressions: dict[str, ExerciseProgression],
    *,
    limit_per_exercise: int = 8,
    max_exercises: int = 15,
) -> dict[str, list[dict[str, Any]]]:
    """Last N sessions per exercise for comparison-style questions."""
    ranked = sorted(
        progressions.values(),
        key=lambda p: p.last_performed or date.min,
        reverse=True,
    )[:max_exercises]

    history: dict[str, list[dict[str, Any]]] = {}
    for prog in ranked:
        if prog.session_count < 1:
            continue
        ordered = sorted(prog.sessions, key=lambda s: s.workout_date, reverse=True)
        recent = ordered[:limit_per_exercise]
        unit = exercise_metric(prog.exercise)
        history[prog.exercise] = [
            {
                "date": str(s.workout_date),
                "value": s.weight,
                "unit": unit,
                "notes": s.notes.strip(),
            }
            for s in reversed(recent)  # chronological order for the LLM
        ]
    return history


def _neglected_muscles(
    summary: DashboardSummary, today: date, threshold_days: int = 14
) -> list[str]:
    cutoff = today - timedelta(days=threshold_days)
    neglected: list[str] = []
    for muscle in MUSCLE_TABS:
        last = summary.last_trained_per_muscle.get(muscle)
        if last is None or last < cutoff:
            neglected.append(muscle)
    return neglected


def _recent_notes(
    entries: list[WorkoutEntry], today: date, limit: int = 10
) -> list[dict[str, str]]:
    cutoff = today - timedelta(days=30)
    noted = [e for e in entries if e.notes.strip() and e.workout_date >= cutoff]
    noted.sort(key=lambda e: e.workout_date, reverse=True)
    return [
        {
            "date": str(e.workout_date),
            "exercise": e.exercise,
            "muscle": e.muscle,
            "note": e.notes.strip(),
        }
        for e in noted[:limit]
    ]


def _serialize_trends(
    trends: dict[str, TrendResult],
    progressions: dict[str, ExerciseProgression],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key, trend in sorted(trends.items()):
        if trend.trend == Trend.INSUFFICIENT_DATA:
            continue
        prog = progressions.get(key)
        exercise_name = prog.exercise if prog else exercise_display_name(key)
        unit = exercise_metric(exercise_name)
        result.append(
            {
                "exercise": exercise_name,
                "trend": trend.trend.value,
                "change": trend.weight_change,
                "unit": unit,
                "sessions_analysed": trend.sessions_analysed,
                "detail": trend.message,
            }
        )
    return result
