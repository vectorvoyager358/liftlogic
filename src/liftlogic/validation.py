"""Workout data validation — authoritative backend rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from liftlogic.constants import MUSCLE_TABS
from liftlogic.exercises import exercise_by_name
from liftlogic.models import WorkoutEntry, WorkoutInput
from liftlogic.parsing import parse_date, parse_weight

MAX_NOTES_LENGTH = 500


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class ValidationResult:
    valid: bool
    input: WorkoutInput | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


def validate_workout_input(
    *,
    workout_date: str | date | None,
    muscle: str,
    exercise: str,
    weight: str | float | int | None,
    notes: str = "",
    source_row: str = "",
    log_id: str = "",
) -> ValidationResult:
    """Validate raw workout input and return a normalized WorkoutInput or issues."""
    issues: list[ValidationIssue] = []

    muscle_clean = muscle.strip()
    if not muscle_clean:
        issues.append(ValidationIssue("muscle", "required", "Muscle group is required"))
    elif muscle_clean not in MUSCLE_TABS:
        issues.append(
            ValidationIssue(
                "muscle",
                "invalid_muscle",
                f"Muscle must be one of: {', '.join(MUSCLE_TABS)}",
            )
        )

    parsed_date = parse_date(workout_date) if workout_date is not None else None
    if parsed_date is None:
        issues.append(ValidationIssue("date", "required", "A valid date is required"))

    exercise_clean = exercise.strip()
    if not exercise_clean:
        issues.append(ValidationIssue("exercise", "required", "Exercise is required"))

    parsed_weight = parse_weight(weight)
    if parsed_weight is None:
        issues.append(ValidationIssue("weight", "required", "Weight must be a number"))
    elif parsed_weight < 0:
        issues.append(ValidationIssue("weight", "negative", "Weight cannot be negative"))
    elif muscle_clean in MUSCLE_TABS and muscle_clean != "Cardio" and parsed_weight == 0:
        issues.append(
            ValidationIssue(
                "weight",
                "zero_weight",
                "Weight must be greater than zero for strength exercises",
            )
        )

    notes_clean = notes.strip() if notes else ""
    if len(notes_clean) > MAX_NOTES_LENGTH:
        issues.append(
            ValidationIssue(
                "notes",
                "too_long",
                f"Notes must be at most {MAX_NOTES_LENGTH} characters",
            )
        )

    exercise_id = ""
    if exercise_clean:
        match = exercise_by_name(exercise_clean)
        if match:
            exercise_id = match.exercise_id
            if muscle_clean and match.primary_muscle != muscle_clean:
                issues.append(
                    ValidationIssue(
                        "exercise",
                        "muscle_mismatch",
                        (
                            f"Exercise '{exercise_clean}' belongs to "
                            f"{match.primary_muscle}, not {muscle_clean}"
                        ),
                        severity="warning",
                    )
                )
        else:
            issues.append(
                ValidationIssue(
                    "exercise",
                    "unknown_exercise",
                    f"Exercise '{exercise_clean}' is not in the catalog",
                    severity="warning",
                )
            )

    if issues and any(issue.severity == "error" for issue in issues):
        return ValidationResult(valid=False, issues=issues)

    assert parsed_date is not None
    assert parsed_weight is not None

    normalized = WorkoutInput(
        log_id=log_id,
        workout_date=parsed_date,
        muscle=muscle_clean,
        exercise_id=exercise_id,
        exercise=exercise_clean,
        weight=parsed_weight,
        notes=notes_clean,
        source_row=source_row.strip(),
    )
    return ValidationResult(valid=True, input=normalized, issues=issues)


def validate_workout_entry(entry: WorkoutEntry) -> ValidationResult:
    """Validate an existing Workout_Log row."""
    return validate_workout_input(
        workout_date=entry.workout_date,
        muscle=entry.muscle,
        exercise=entry.exercise,
        weight=entry.weight,
        notes=entry.notes,
        source_row=entry.source_row,
        log_id=entry.log_id,
    )


def validate_workout_log(entries: list[WorkoutEntry]) -> list[ValidationResult]:
    """Validate every row in the workout log."""
    return [validate_workout_entry(entry) for entry in entries]
