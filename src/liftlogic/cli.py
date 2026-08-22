"""CLI entry points for LiftLogic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from liftlogic.reconcile import reconcile_workout_log
from liftlogic.repository import WorkoutRepository
from liftlogic.setup import setup_spreadsheet
from liftlogic.sheets.client import SheetsClient


def main() -> None:
    parser = argparse.ArgumentParser(description="LiftLogic — workout data backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Bootstrap a LiftLogic Google Sheet")
    setup_parser.add_argument("--spreadsheet-id", help="Existing spreadsheet ID to configure")
    setup_parser.add_argument("--credentials-dir", default="credentials")
    setup_parser.add_argument(
        "--write-config",
        action="store_true",
        help="Write spreadsheet ID to credentials/spreadsheet.json",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate Workout_Log data quality")
    validate_parser.add_argument("--credentials-dir", default="credentials")
    validate_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Compare muscle tabs against Workout_Log",
    )
    reconcile_parser.add_argument("--credentials-dir", default="credentials")
    reconcile_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")

    args = parser.parse_args()

    if args.command == "setup":
        _cmd_setup(args)
    elif args.command == "validate":
        _cmd_validate(args)
    elif args.command == "reconcile":
        _cmd_reconcile(args)


def _load_spreadsheet_id(args: argparse.Namespace) -> str:
    if getattr(args, "spreadsheet_id", None):
        return args.spreadsheet_id

    config_path = Path(args.credentials_dir) / "spreadsheet.json"
    if not config_path.exists():
        raise SystemExit(
            "No spreadsheet ID found. Run `liftlogic setup --write-config` first "
            "or pass --spreadsheet-id."
        )
    return json.loads(config_path.read_text())["spreadsheet_id"]


def _cmd_setup(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = setup_spreadsheet(client, spreadsheet_id=args.spreadsheet_id)

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    print(f"LiftLogic sheet ready: {url}")

    if args.write_config:
        config_path = Path(args.credentials_dir) / "spreadsheet.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"spreadsheet_id": spreadsheet_id}, indent=2))
        print(f"Saved spreadsheet ID to {config_path}")

    print("\nNext step: install Apps Script sync from apps-script/Code.gs")


def _cmd_validate(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)

    entries = repo.get_workouts()
    results = repo.validate_log()

    error_count = 0
    warning_count = 0

    print(f"Validating {len(entries)} Workout_Log entries...\n")

    for entry, result in zip(entries, results, strict=True):
        if result.errors:
            error_count += len(result.errors)
            for issue in result.errors:
                print(f"ERROR  [{entry.log_id}] {issue.field}: {issue.message}")
        if result.warnings:
            warning_count += len(result.warnings)
            for issue in result.warnings:
                print(f"WARN   [{entry.log_id}] {issue.field}: {issue.message}")

    if error_count == 0 and warning_count == 0:
        print("All entries passed validation.")
    else:
        print(f"\n{error_count} error(s), {warning_count} warning(s)")

    raise SystemExit(1 if error_count else 0)


def _cmd_reconcile(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)

    report = reconcile_workout_log(client, spreadsheet_id, repo.get_workouts())

    if report.is_clean:
        print("Reconciliation clean — muscle tabs and Workout_Log are in sync.")
        return

    for issue in report.missing_in_log:
        print(f"MISSING  {issue.source_row}: {issue.message}")
    for issue in report.mismatched:
        print(f"MISMATCH {issue.source_row}: {issue.message}")
    for issue in report.orphaned_in_log:
        print(f"ORPHAN   {issue.source_row}: {issue.message}")

    print(f"\n{report.issue_count} reconciliation issue(s)")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
