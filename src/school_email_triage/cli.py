"""Command-line interface for school email triage."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .config import (
    DEFAULT_QUERY,
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_TOKEN_PATH,
    DEFAULT_GEMINI_MODEL,
    SYNC_GOOGLE_TASKS,
)
from .auth import get_credentials, AuthenticationError
from .gmail_service import GmailService
from .calendar_service import CalendarService
from .tasks_service import TasksService
from .extractor import GeminiExtractor
from .pipeline import TriagePipeline
from .models import EmailTriageResult, CalendarEvent, ProcessedEmail


# Ensure stdout supports UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(highlight=False)


def render_results(processed_emails: list[ProcessedEmail], dry_run: bool) -> None:
    """Print beautifully formatted summary tables to the terminal."""
    if not processed_emails:
        console.print("[yellow]No emails were processed.[/yellow]")
        return

    mode_tag = "[bold yellow][DRY-RUN MODE][/bold yellow] " if dry_run else "[bold green][LIVE MODE][/bold green] "
    console.print(Panel.fit(f"{mode_tag}Triaged {len(processed_emails)} school email(s)", border_style="blue"))

    table = Table(title="Triage Results Summary", show_lines=True)
    table.add_column("Child", style="cyan", width=12)
    table.add_column("Subject & Sender", style="white", ratio=2)
    table.add_column("Action Items & Deadlines", style="magenta", ratio=2)
    table.add_column("Calendar Events", style="green", ratio=2)
    table.add_column("Labels Applied", style="dim", ratio=1)

    for item in processed_emails:
        res = item.triage_result
        if not res:
            table.add_row("Unknown", item.subject, "None", "None", ", ".join(item.applied_labels))
            continue

        # Format child badge
        child_color = "red" if res.target_child == "daughter" else "blue" if res.target_child == "son" else "yellow"
        child_badge = f"[{child_color}]{res.target_child.upper()}[/{child_color}]"

        # Format subject + sender
        subj_text = f"[bold]{item.subject}[/bold]\n[dim]{item.sender}[/dim]"

        # Format action items
        if res.action_items:
            actions_text = "\n".join(f"- {act}" for act in res.action_items)
        else:
            actions_text = "[dim]No action items[/dim]"

        # Format calendar events
        if res.calendar_events:
            events_text = "\n".join(
                f"[bold]{e.title}[/bold]\n  {e.start_iso} to {e.end_iso}"
                for e in res.calendar_events
            )
        else:
            events_text = "[dim]No events[/dim]"

        labels_text = "\n".join(item.applied_labels)

        table.add_row(child_badge, subj_text, actions_text, events_text, labels_text)

    console.print(table)



def run_mock_verification() -> int:
    """Run an offline mock simulation to verify parsing, schemas, and dry-run execution."""
    console.print(Panel("[bold cyan]Running Offline Mock Simulation & Verification[/bold cyan]", border_style="cyan"))

    sample_email_daughter = {
        "subject": "5th Grade Back to School Night & Permission Slip Due Friday",
        "sender": "Ms. Miller <j.miller@schooldistrict.org>",
        "date_str": "Fri, 04 Sep 2026 09:00:00 -0400",
        "body": """
        Dear 5th Grade Parents of Lincoln Elementary,

        Welcome to the 2026 school year!
        1. Back to School Night will be held on Thursday, September 17, 2026 from 6:00 PM to 7:30 PM in the auditorium.
        2. Field trip permission slip for the Science Museum is due by Friday, September 11, 2026. Please return the signed form with $15.
        3. Picture Day is scheduled for Friday, September 25, 2026.

        Best regards,
        Ms. Miller
        Lincoln Elementary 5th Grade
        """,
    }

    sample_email_son = {
        "subject": "ParentSquare: Middle School Soccer Practice Schedule",
        "sender": "Coach Davis <notifications@parentsquare.com>",
        "date_str": "Fri, 04 Sep 2026 10:15:00 -0400",
        "body": """
        Middle School Boys Soccer Parents:

        Mandatory player meeting on Monday, September 14, 2026 from 3:30 PM to 4:30 PM in the gymnasium.
        Please ensure all physical examination forms are uploaded to the portal before September 10, 2026.

        Coach Davis
        """,
    }

    console.print("[green]Simulating triage extraction on sample emails...[/green]\n")

    mock_result_daughter = EmailTriageResult(
        target_child="daughter",
        summary="5th grade updates regarding Back to School Night, permission slip, and picture day.",
        action_items=[
            "Return signed Science Museum permission slip with $15 by Friday, September 11, 2026",
            "Attend Back to School Night on Thursday, September 17, 2026",
        ],
        calendar_events=[
            CalendarEvent(
                title="Lincoln Elementary 5th Grade Back to School Night",
                start_iso="2026-09-17T18:00:00",
                end_iso="2026-09-17T19:30:00",
                notes="Auditorium",
            ),
            CalendarEvent(
                title="Lincoln Elementary Picture Day",
                start_iso="2026-09-25",
                end_iso="2026-09-25",
                notes="All-day event",
            ),
        ],
    )

    mock_result_son = EmailTriageResult(
        target_child="son",
        summary="Middle school soccer team meeting schedule and physical exam submission deadline.",
        action_items=[
            "Upload physical examination forms to portal before September 10, 2026"
        ],
        calendar_events=[
            CalendarEvent(
                title="Boys Soccer Mandatory Player Meeting",
                start_iso="2026-09-14T15:30:00",
                end_iso="2026-09-14T16:30:00",
                notes="Middle School Gymnasium",
            )
        ],
    )

    mock_processed = [
        ProcessedEmail(
            message_id="mock_msg_001",
            thread_id="mock_thread_001",
            subject=sample_email_daughter["subject"],
            sender=sample_email_daughter["sender"],
            date_str=sample_email_daughter["date_str"],
            snippet=sample_email_daughter["body"][:100],
            plain_text=sample_email_daughter["body"],
            triage_result=mock_result_daughter,
            created_events=["dry-run:Lincoln Elementary 5th Grade Back to School Night", "dry-run:Lincoln Elementary Picture Day"],
            applied_labels=["School/Processed", "School/Daughter"],
        ),
        ProcessedEmail(
            message_id="mock_msg_002",
            thread_id="mock_thread_002",
            subject=sample_email_son["subject"],
            sender=sample_email_son["sender"],
            date_str=sample_email_son["date_str"],
            snippet=sample_email_son["body"][:100],
            plain_text=sample_email_son["body"],
            triage_result=mock_result_son,
            created_events=["dry-run:Boys Soccer Mandatory Player Meeting"],
            applied_labels=["School/Processed", "School/Son"],
        ),
    ]

    render_results(mock_processed, dry_run=True)
    console.print("[bold green][OK] Mock verification completed successfully![/bold green]\n")
    return 0



def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="school-email-triage",
        description="Automate triage of school emails via Gmail, Google Calendar, and Gemini.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without modifying Gmail labels or creating Calendar events.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=DEFAULT_QUERY,
        help=f"Gmail query for searching school emails. Default: '{DEFAULT_QUERY}'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of unread emails to process in this run. Default: 20",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to OAuth 2.0 client credentials.json. Default: '{DEFAULT_CREDENTIALS_PATH}'",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help=f"Path to cached OAuth 2.0 token.json. Default: '{DEFAULT_TOKEN_PATH}'",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Perform OAuth 2.0 authorization and save token.json without running triage.",
    )
    parser.add_argument(
        "--mock-test",
        action="store_true",
        help="Run offline mock simulation and verify parsing, schema validation, and rendering.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable detailed debug logging.",
    )

    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.mock_test:
        return run_mock_verification()

    console.print(
        Panel.fit(
            "[bold cyan]School Email Triage Tool[/bold cyan]\n"
            "Gmail • Google Calendar • Gemini Structured Extraction",
            border_style="cyan",
        )
    )

    # Handle --auth-only
    if args.auth_only:
        console.print("[cyan]Initiating OAuth 2.0 authentication...[/cyan]")
        try:
            get_credentials(args.credentials, args.token)
            console.print(f"[bold green]Authentication successful! Token saved to: {args.token.resolve()}[/bold green]")
            return 0
        except AuthenticationError as e:
            console.print(f"[bold red]Authentication Error:[/bold red]\n{e}")
            return 1

    # Normal execution flow
    try:
        credentials = get_credentials(args.credentials, args.token)
    except AuthenticationError as e:
        console.print(f"[bold red]Authentication Error:[/bold red]\n{e}")
        console.print("\n[yellow]Tip: Run with --mock-test to test the workflow without credentials.[/yellow]")
        return 1

    # Initialize Gemini Extractor
    extractor = GeminiExtractor()
    if not extractor.is_available():
        console.print(
            "[bold red]Error: GEMINI_API_KEY environment variable is not set.[/bold red]\n"
            "Please set GEMINI_API_KEY in your environment or a .env file.\n"
            "Example: GEMINI_API_KEY=AIzaSy..."
        )
        return 1

    gmail_service = GmailService(credentials)
    calendar_service = CalendarService(credentials)
    tasks_service = TasksService(credentials) if SYNC_GOOGLE_TASKS else None

    pipeline = TriagePipeline(
        gmail_service=gmail_service,
        calendar_service=calendar_service,
        extractor=extractor,
        tasks_service=tasks_service,
        dry_run=args.dry_run,
        console=console,
    )


    with console.status("[cyan]Triaging school emails...[/cyan]"):
        results = pipeline.run(query=args.query, limit=args.limit)

    render_results(results, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
