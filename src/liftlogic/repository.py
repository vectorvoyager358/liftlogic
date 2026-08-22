"""Data access layer — no raw cell references outside this package."""

from __future__ import annotations

from liftlogic.analytics import calculate_personal_records
from liftlogic.constants import WORKOUT_LOG_COLUMNS, WORKOUT_LOG_SHEET
from liftlogic.models import PersonalRecord, WorkoutEntry, WorkoutInput
from liftlogic.parsing import parse_date, parse_weight
from liftlogic.sheets.client import SheetsClient
from liftlogic.validation import ValidationResult, validate_workout_input, validate_workout_log


class WorkoutRepository:
    """Read and write workout data from the Workout_Log sheet."""

    def __init__(self, client: SheetsClient, spreadsheet_id: str) -> None:
        self._client = client
        self._spreadsheet_id = spreadsheet_id

    def get_workouts(self) -> list[WorkoutEntry]:
        rows = self._client.get_values(
            self._spreadsheet_id,
            f"{WORKOUT_LOG_SHEET}!A2:H",
        )
        return [_parse_workout_row(row) for row in rows if _row_has_data(row)]

    def get_exercise_history(self, exercise_id: str) -> list[WorkoutEntry]:
        return [entry for entry in self.get_workouts() if entry.exercise_id == exercise_id]

    def get_personal_records(self) -> list[PersonalRecord]:
        return calculate_personal_records(self.get_workouts())

    def get_personal_record(self, exercise_id: str) -> PersonalRecord | None:
        for record in self.get_personal_records():
            if record.exercise_id == exercise_id:
                return record
        return None

    def validate_log(self) -> list[ValidationResult]:
        return validate_workout_log(self.get_workouts())

    def add_workout(
        self,
        *,
        workout_date: str | object,
        muscle: str,
        exercise: str,
        weight: str | float | int,
        notes: str = "",
        source_row: str = "",
    ) -> WorkoutEntry:
        result = validate_workout_input(
            workout_date=workout_date,
            muscle=muscle,
            exercise=exercise,
            weight=weight,
            notes=notes,
            source_row=source_row,
        )
        if not result.valid or result.input is None:
            raise ValueError(_format_issues(result))

        workout = result.input
        if not workout.log_id:
            workout = WorkoutInput(
                log_id=_next_log_id(self.get_workouts()),
                workout_date=workout.workout_date,
                muscle=workout.muscle,
                exercise_id=workout.exercise_id,
                exercise=workout.exercise,
                weight=workout.weight,
                notes=workout.notes,
                source_row=workout.source_row,
            )

        self._client.append_values(
            self._spreadsheet_id,
            f"{WORKOUT_LOG_SHEET}!A:H",
            [_to_row(workout)],
        )
        return _input_to_entry(workout)

    def update_workout(self, log_id: str, **fields: object) -> WorkoutEntry:
        entries = self.get_workouts()
        existing = next((entry for entry in entries if entry.log_id == log_id), None)
        if existing is None:
            raise ValueError(f"Workout not found: {log_id}")

        result = validate_workout_input(
            workout_date=fields.get("workout_date", existing.workout_date),
            muscle=fields.get("muscle", existing.muscle),
            exercise=fields.get("exercise", existing.exercise),
            weight=fields.get("weight", existing.weight),
            notes=fields.get("notes", existing.notes),
            source_row=fields.get("source_row", existing.source_row),
            log_id=log_id,
        )
        if not result.valid or result.input is None:
            raise ValueError(_format_issues(result))

        row_index = _find_row_index(entries, log_id)
        self._client.update_values(
            self._spreadsheet_id,
            f"{WORKOUT_LOG_SHEET}!A{row_index + 2}:H{row_index + 2}",
            [_to_row(result.input)],
        )
        return _input_to_entry(result.input)

    def delete_workout(self, log_id: str) -> None:
        entries = self.get_workouts()
        row_index = _find_row_index(entries, log_id)
        self._client.delete_rows(self._spreadsheet_id, WORKOUT_LOG_SHEET, [row_index + 2])

    def delete_workout_by_source(self, source_row: str) -> bool:
        entries = self.get_workouts()
        for index, entry in enumerate(entries):
            if entry.source_row == source_row:
                self._client.delete_rows(
                    self._spreadsheet_id,
                    WORKOUT_LOG_SHEET,
                    [index + 2],
                )
                return True
        return False

    def upsert_workout(
        self,
        *,
        workout_date: str | object,
        muscle: str,
        exercise: str,
        weight: str | float | int,
        notes: str = "",
        source_row: str = "",
    ) -> WorkoutEntry:
        """Insert or update by source_row — mirrors Apps Script sync behavior."""
        if source_row:
            entries = self.get_workouts()
            for entry in entries:
                if entry.source_row == source_row:
                    return self.update_workout(
                        entry.log_id,
                        workout_date=workout_date,
                        muscle=muscle,
                        exercise=exercise,
                        weight=weight,
                        notes=notes,
                        source_row=source_row,
                    )
        return self.add_workout(
            workout_date=workout_date,
            muscle=muscle,
            exercise=exercise,
            weight=weight,
            notes=notes,
            source_row=source_row,
        )


def _to_row(workout: WorkoutInput) -> list[object]:
    return [
        workout.log_id,
        workout.workout_date.isoformat(),
        workout.muscle,
        workout.exercise_id,
        workout.exercise,
        workout.weight,
        workout.notes,
        workout.source_row,
    ]


def _input_to_entry(workout: WorkoutInput) -> WorkoutEntry:
    return WorkoutEntry(
        log_id=workout.log_id,
        workout_date=workout.workout_date,
        muscle=workout.muscle,
        exercise_id=workout.exercise_id,
        exercise=workout.exercise,
        weight=workout.weight,
        notes=workout.notes,
        source_row=workout.source_row,
    )


def _next_log_id(entries: list[WorkoutEntry]) -> str:
    max_num = 0
    for entry in entries:
        if entry.log_id.startswith("L") and entry.log_id[1:].isdigit():
            max_num = max(max_num, int(entry.log_id[1:]))
    return f"L{max_num + 1:06d}"


def _find_row_index(entries: list[WorkoutEntry], log_id: str) -> int:
    for index, entry in enumerate(entries):
        if entry.log_id == log_id:
            return index
    raise ValueError(f"Workout not found: {log_id}")


def _format_issues(result: ValidationResult) -> str:
    return "; ".join(f"{issue.field}: {issue.message}" for issue in result.errors)


def _row_has_data(row: list[str]) -> bool:
    return len(row) >= 6 and any(str(cell).strip() for cell in row[1:6])


def _parse_workout_row(row: list[str]) -> WorkoutEntry:
    padded = row + [""] * (len(WORKOUT_LOG_COLUMNS) - len(row))
    (
        log_id,
        raw_date,
        muscle,
        exercise_id,
        exercise,
        raw_weight,
        notes,
        source_row,
    ) = padded[:8]

    parsed_date = parse_date(raw_date) or parse_date("1970-01-01")
    parsed_weight = parse_weight(raw_weight) or 0.0

    return WorkoutEntry(
        log_id=log_id,
        workout_date=parsed_date,
        muscle=muscle,
        exercise_id=exercise_id,
        exercise=exercise,
        weight=parsed_weight,
        notes=notes,
        source_row=source_row,
    )
