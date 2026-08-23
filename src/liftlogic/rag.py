"""RAG-lite — keyword retrieval over workout notes and exercise metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from liftlogic.constants import MUSCLE_TABS
from liftlogic.exercises import exercise_metric
from liftlogic.models import WorkoutEntry

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_SUBSTRING_LEN = 3


@dataclass(frozen=True)
class KnowledgeHit:
    """A workout entry ranked by relevance to a search query."""

    log_id: str
    workout_date: date
    muscle: str
    exercise: str
    note: str
    weight: float
    unit: str
    score: float

    def to_dict(self) -> dict[str, str | float]:
        result: dict[str, str | float] = {
            "date": str(self.workout_date),
            "muscle": self.muscle,
            "exercise": self.exercise,
            "logged_value": self.weight,
            "unit": self.unit,
            "relevance_score": round(self.score, 2),
        }
        if self.note:
            result["note"] = self.note
        return result


def search_workout_knowledge(
    query: str,
    entries: list[WorkoutEntry],
    *,
    limit: int = 5,
    as_of: date | None = None,
    lookback_days: int = 365,
    muscle_tab: str | None = None,
) -> list[KnowledgeHit]:
    """Return workout entries relevant to a natural-language query.

    Matches note text, exercise names, and muscle groups. Entries without
    notes are included when the query matches the exercise or muscle name
    (e.g. searching "shoulder" finds Shoulders workouts).
    """
    if not query.strip():
        return []

    today = as_of or date.today()
    cutoff = today - timedelta(days=lookback_days)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    candidates = [e for e in entries if e.workout_date >= cutoff]
    if muscle_tab:
        if muscle_tab not in MUSCLE_TABS:
            raise ValueError(f"Invalid muscle tab: {muscle_tab}")
        candidates = [e for e in candidates if e.muscle == muscle_tab]

    hits: list[KnowledgeHit] = []
    for entry in candidates:
        score = _score_entry(query, query_tokens, entry, as_of=today)
        if score > 0:
            unit = exercise_metric(entry.exercise_id or entry.exercise)
            hits.append(
                KnowledgeHit(
                    log_id=entry.log_id,
                    workout_date=entry.workout_date,
                    muscle=entry.muscle,
                    exercise=entry.exercise,
                    note=entry.notes.strip(),
                    weight=entry.weight,
                    unit=unit,
                    score=score,
                )
            )

    hits.sort(key=lambda h: (h.score, h.workout_date), reverse=True)
    return hits[:limit]


def looks_like_note_question(query: str) -> bool:
    """Heuristic: does this question likely need note retrieval?"""
    q = query.casefold()
    note_signals = (
        "note",
        "wrote",
        "said",
        "mention",
        "remember",
        "discomfort",
        "pain",
        "hurt",
        "sore",
        "injury",
        "felt",
        "feeling",
        "comment",
    )
    return any(signal in q for signal in note_signals)


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.casefold()))


def _field_match_count(field: str, query_tokens: set[str]) -> int:
    """Count query tokens matching a field via token overlap or substring."""
    field_cf = field.casefold()
    field_tokens = _tokenize(field_cf)
    count = len(query_tokens & field_tokens)
    for token in query_tokens:
        if len(token) >= _MIN_SUBSTRING_LEN and token in field_cf:
            count += 1
    return count


def _score_entry(
    query: str,
    query_tokens: set[str],
    entry: WorkoutEntry,
    *,
    as_of: date | None = None,
) -> float:
    note_text = entry.notes.strip()
    score = 0.0

    if note_text:
        note_tokens = _tokenize(note_text)
        score += float(len(query_tokens & note_tokens))
        if query.casefold() in note_text.casefold():
            score += 3.0

    # Exercise and muscle matches work even when notes are empty
    score += _field_match_count(entry.exercise, query_tokens) * 1.5
    score += _field_match_count(entry.muscle, query_tokens) * 1.5

    id_cf = entry.exercise_id.casefold()
    for token in query_tokens:
        if len(token) >= 2 and token in id_cf:
            score += 0.5

    if score <= 0:
        return 0.0

    reference = as_of or date.today()
    days_ago = (reference - entry.workout_date).days
    recency = max(0.0, 1.0 - days_ago / 365)
    score += recency * 0.5

    return score
