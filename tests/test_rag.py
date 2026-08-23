"""Tests for workout note retrieval (RAG-lite)."""

from __future__ import annotations

from datetime import date

from liftlogic.models import WorkoutEntry
from liftlogic.rag import looks_like_note_question, search_workout_knowledge


def _entry(
    exercise: str,
    weight: float,
    workout_date: date,
    muscle: str = "Shoulders",
    notes: str = "",
    exercise_id: str = "SH001",
    log_id: str = "L000001",
) -> WorkoutEntry:
    return WorkoutEntry(
        log_id=log_id,
        workout_date=workout_date,
        muscle=muscle,
        exercise_id=exercise_id,
        exercise=exercise,
        weight=weight,
        notes=notes,
        source_row="Shoulders!A2",
    )


def test_search_finds_matching_note():
    entries = [
        _entry(
            "Lateral Raise",
            20,
            date(2026, 8, 10),
            notes="Shoulder felt tight on the left side",
            log_id="L000001",
        ),
        _entry(
            "Overhead Press",
            95,
            date(2026, 8, 12),
            notes="Strong session",
            log_id="L000002",
        ),
    ]
    hits = search_workout_knowledge("shoulder discomfort", entries, as_of=date(2026, 8, 15))
    assert len(hits) >= 1
    assert hits[0].note == "Shoulder felt tight on the left side"


def test_search_finds_muscle_match_without_notes():
    entries = [
        _entry("Lateral Raise", 25, date(2026, 8, 18), muscle="Shoulders", notes=""),
        _entry("Barbell Bench Press", 185, date(2026, 8, 18), muscle="Chest", notes=""),
    ]
    hits = search_workout_knowledge("shoulder", entries, as_of=date(2026, 8, 20))
    assert len(hits) >= 1
    assert hits[0].muscle == "Shoulders"
    assert hits[0].note == ""


def test_search_ranks_better_matches_higher():
    entries = [
        _entry("Bench Press", 185, date(2026, 8, 1), muscle="Chest", notes="Chest pump"),
        _entry(
            "Incline Press",
            135,
            date(2026, 8, 5),
            muscle="Chest",
            notes="Shoulder pinching on incline bench",
            exercise_id="CH002",
            log_id="L000002",
        ),
    ]
    hits = search_workout_knowledge("shoulder pinching incline", entries, as_of=date(2026, 8, 10))
    assert hits[0].exercise == "Incline Press"


def test_looks_like_note_question_detects_note_queries():
    assert looks_like_note_question("What did I write about shoulder pain?")
    assert not looks_like_note_question("How is my bench press progressing?")
