"""CLI entry points for LiftLogic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from liftlogic.ai import ask_question, generate_insights, write_ai_insights_tab
from liftlogic.muscle_context import detect_muscle_in_query
from liftlogic.rag import search_workout_knowledge
from liftlogic.constants import AI_INSIGHTS_SHEET
from liftlogic.dashboard import format_stats, refresh_analytics_tab
from liftlogic.reconcile import reconcile_workout_log
from liftlogic.repository import WorkoutRepository
from liftlogic.setup import (
    format_analytics_tab,
    format_dashboard,
    format_workout_tabs,
    setup_spreadsheet,
)
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

    stats_parser = subparsers.add_parser("stats", help="Print workout stats to the terminal")
    stats_parser.add_argument("--credentials-dir", default="credentials")
    stats_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")

    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Write computed analytics to the Analytics sheet tab",
    )
    refresh_parser.add_argument("--credentials-dir", default="credentials")
    refresh_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")

    format_parser = subparsers.add_parser(
        "format",
        help="Apply visual formatting to the Dashboard and muscle tabs",
    )
    format_parser.add_argument("--credentials-dir", default="credentials")
    format_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")

    ask_parser = subparsers.add_parser(
        "ask", help="Ask a natural-language question about your workouts"
    )
    ask_parser.add_argument("question", help="Your question in quotes")
    ask_parser.add_argument("--credentials-dir", default="credentials")
    ask_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")

    insights_parser = subparsers.add_parser(
        "insights",
        help="Generate AI coaching summary and write to AI_Insights tab",
    )
    insights_parser.add_argument("--credentials-dir", default="credentials")
    insights_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")
    insights_parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print insights to terminal without writing to the sheet",
    )

    search_parser = subparsers.add_parser(
        "search-notes",
        help="Search workout notes by keyword (RAG retrieval preview)",
    )
    search_parser.add_argument("query", help="Search terms in quotes")
    search_parser.add_argument("--credentials-dir", default="credentials")
    search_parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID")
    search_parser.add_argument("--limit", type=int, default=5, help="Max results (default 5)")

    args = parser.parse_args()

    if args.command == "setup":
        _cmd_setup(args)
    elif args.command == "validate":
        _cmd_validate(args)
    elif args.command == "reconcile":
        _cmd_reconcile(args)
    elif args.command == "stats":
        _cmd_stats(args)
    elif args.command == "refresh":
        _cmd_refresh(args)
    elif args.command == "format":
        _cmd_format(args)
    elif args.command == "ask":
        _cmd_ask(args)
    elif args.command == "insights":
        _cmd_insights(args)
    elif args.command == "search-notes":
        _cmd_search_notes(args)


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


def _cmd_stats(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)
    entries = repo.get_workouts()
    print(format_stats(entries))


def _cmd_refresh(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)
    entries = repo.get_workouts()

    if not entries:
        print("No workout data found — Analytics tab not updated.")
        return

    refresh_analytics_tab(client, spreadsheet_id, entries)
    print(f"Analytics tab refreshed with data from {len(entries)} log entries.")


def _cmd_format(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)

    print("Formatting Dashboard tab…")
    format_dashboard(client, spreadsheet_id)

    print("Formatting muscle tabs…")
    format_workout_tabs(client, spreadsheet_id)

    print("Formatting Analytics tab…")
    format_analytics_tab(client, spreadsheet_id)

    print("Done. Open the sheet to see the updated layout.")


def _cmd_ask(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)
    entries = repo.get_workouts()

    answer = ask_question(args.question, entries, credentials_dir=args.credentials_dir)
    print(answer)


def _cmd_insights(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)
    entries = repo.get_workouts()

    insights = generate_insights(entries, credentials_dir=args.credentials_dir)
    print(insights)

    if not args.print_only and entries:
        write_ai_insights_tab(client, spreadsheet_id, insights)
        print(f"\nInsights written to {AI_INSIGHTS_SHEET} tab.")


def _cmd_search_notes(args: argparse.Namespace) -> None:
    client = SheetsClient.from_oauth(args.credentials_dir)
    spreadsheet_id = _load_spreadsheet_id(args)
    repo = WorkoutRepository(client, spreadsheet_id)
    entries = repo.get_workouts()

    hits = search_workout_knowledge(
        args.query,
        entries,
        limit=args.limit,
        muscle_tab=detect_muscle_in_query(args.query),
    )
    if not hits:
        print("No matching entries found.")
        return

    print(f"Found {len(hits)} result(s) for: {args.query!r}\n")
    for hit in hits:
        print(f"  [{hit.workout_date}] {hit.muscle} — {hit.exercise}")
        if hit.note:
            print(f"  {hit.note}")
        else:
            print(f"  {hit.weight:g} {hit.unit} (no notes)")
        print(f"  (score: {hit.score:.1f}, log: {hit.log_id})\n")


if __name__ == "__main__":
    main()
