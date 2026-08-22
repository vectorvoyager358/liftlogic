"""Reconciliation — detect drift between muscle tabs and Workout_Log."""

from __future__ import annotations

from dataclasses import dataclass, field

from liftlogic.constants import MUSCLE_TABS, WORKOUT_ENTRY_COLUMNS
from liftlogic.models import WorkoutEntry, WorkoutInput
from liftlogic.sheets.client import SheetsClient
from liftlogic.validation import validate_workout_input


@dataclass
class ReconciliationIssue:
    source_row: str
    code: str
    message: str


@dataclass
class ReconciliationReport:
    missing_in_log: list[ReconciliationIssue] = field(default_factory=list)
    orphaned_in_log: list[ReconciliationIssue] = field(default_factory=list)
    mismatched: list[ReconciliationIssue] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.missing_in_log and not self.orphaned_in_log and not self.mismatched

    @property
    def issue_count(self) -> int:
        return len(self.missing_in_log) + len(self.orphaned_in_log) + len(self.mismatched)


def reconcile_workout_log(
    client: SheetsClient,
    spreadsheet_id: str,
    log_entries: list[WorkoutEntry],
) -> ReconciliationReport:
    """Compare muscle-tab rows against Workout_Log entries by Source Row."""
    report = ReconciliationReport()
    log_by_source = {entry.source_row: entry for entry in log_entries if entry.source_row}

    seen_sources: set[str] = set()

    for muscle in MUSCLE_TABS:
        rows = client.get_values(spreadsheet_id, f"{muscle}!A2:D1000")
        for row_index, row in enumerate(rows, start=2):
            padded = row + [""] * (len(WORKOUT_ENTRY_COLUMNS) - len(row))
            raw_date, exercise, weight, notes = padded[:4]

            if not any(str(cell).strip() for cell in [raw_date, exercise, weight, notes]):
                continue

            source_row = f"{muscle}!A{row_index}"
            seen_sources.add(source_row)

            if not str(raw_date).strip() or not str(exercise).strip():
                continue

            validation = validate_workout_input(
                workout_date=raw_date,
                muscle=muscle,
                exercise=str(exercise),
                weight=weight,
                notes=str(notes) if notes else "",
                source_row=source_row,
            )
            if not validation.valid or validation.input is None:
                continue

            tab_entry = validation.input
            log_entry = log_by_source.get(source_row)

            if log_entry is None:
                report.missing_in_log.append(
                    ReconciliationIssue(
                        source_row=source_row,
                        code="missing_in_log",
                        message=f"Muscle tab row exists but no Workout_Log entry for {source_row}",
                    )
                )
                continue

            if not _entries_match(tab_entry, log_entry):
                report.mismatched.append(
                    ReconciliationIssue(
                        source_row=source_row,
                        code="mismatched",
                        message=_mismatch_message(tab_entry, log_entry),
                    )
                )

    for source_row, log_entry in log_by_source.items():
        if source_row not in seen_sources:
            report.orphaned_in_log.append(
                ReconciliationIssue(
                    source_row=source_row,
                    code="orphaned_in_log",
                    message=(
                        f"Workout_Log entry {log_entry.log_id} references "
                        f"cleared or missing source row {source_row}"
                    ),
                )
            )

    return report


def _entries_match(tab: WorkoutInput, log: WorkoutEntry) -> bool:
    return (
        tab.workout_date == log.workout_date
        and tab.exercise.casefold() == log.exercise.casefold()
        and tab.weight == log.weight
        and tab.notes == log.notes
        and tab.muscle == log.muscle
    )


def _mismatch_message(tab: WorkoutInput, log: WorkoutEntry) -> str:
    parts: list[str] = []
    if tab.workout_date != log.workout_date:
        parts.append(f"date tab={tab.workout_date} log={log.workout_date}")
    if tab.exercise.casefold() != log.exercise.casefold():
        parts.append(f"exercise tab={tab.exercise!r} log={log.exercise!r}")
    if tab.weight != log.weight:
        parts.append(f"weight tab={tab.weight} log={log.weight}")
    if tab.notes != log.notes:
        parts.append("notes differ")
    if tab.muscle != log.muscle:
        parts.append(f"muscle tab={tab.muscle} log={log.muscle}")
    return f"Data mismatch at {tab.source_row}: {', '.join(parts)}"
