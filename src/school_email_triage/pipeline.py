"""Pipeline orchestrator for school email triage."""

from __future__ import annotations

import logging
from typing import Callable
from rich.console import Console

from .config import (
    LABEL_MAPPING,
    LABEL_PROCESSED,
    DEFAULT_QUERY,
    DAUGHTER_CURRENT_GRADE,
    SON_CURRENT_GRADE,
)
from .models import EmailTriageResult, ProcessedEmail

from .parser import parse_gmail_message
from .gmail_service import GmailService
from .calendar_service import CalendarService
from .tasks_service import TasksService
from .extractor import GeminiExtractor

logger = logging.getLogger(__name__)


class TriagePipeline:
    """Orchestrates email fetching, LLM extraction, calendar creation, tasks, and labeling."""

    def __init__(
        self,
        gmail_service: GmailService,
        calendar_service: CalendarService,
        extractor: GeminiExtractor,
        tasks_service: TasksService | None = None,
        dry_run: bool = False,
        console: Console | None = None,
    ):
        self.gmail = gmail_service
        self.calendar = calendar_service
        self.tasks = tasks_service
        self.extractor = extractor
        self.dry_run = dry_run
        self.console = console or Console()


    def run(
        self,
        query: str = DEFAULT_QUERY,
        limit: int = 20,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[ProcessedEmail]:
        """Execute the full triage workflow.

        Args:
            query: Gmail search query.
            limit: Max emails to process in this run.
            progress_callback: Optional progress reporter.

        Returns:
            List of ProcessedEmail objects.
        """
        if progress_callback:
            progress_callback(f"Querying Gmail: '{query}'")

        messages = self.gmail.list_messages(query=query, max_results=limit)
        if not messages:
            logger.info("No matching unread emails found.")
            return []

        processed_results: list[ProcessedEmail] = []

        for idx, msg_stub in enumerate(messages, 1):
            msg_id = msg_stub["id"]
            if progress_callback:
                progress_callback(f"Processing email {idx}/{len(messages)} (ID: {msg_id})")

            try:
                # 1. Fetch full message
                full_msg = self.gmail.get_message(msg_id)
                parsed = parse_gmail_message(full_msg)

                # 2. Extract structured data with Gemini
                triage_res: EmailTriageResult = self.extractor.extract_from_email(
                    subject=parsed["subject"],
                    sender=parsed["sender"],
                    date_str=parsed["date_str"],
                    body_text=parsed["plain_text"],
                )

                # 3. Determine labels
                labels_to_apply = [LABEL_PROCESSED]
                if triage_res.target_child in ("daughter", "son"):
                    child_base = LABEL_MAPPING[triage_res.target_child]
                    labels_to_apply.append(child_base)

                    # Determine grade sublabel
                    grade = triage_res.grade_level
                    if not grade:
                        grade = (
                            DAUGHTER_CURRENT_GRADE
                            if triage_res.target_child == "daughter"
                            else SON_CURRENT_GRADE
                        )

                    if grade:
                        grade_clean = grade.strip()
                        if not grade_clean.lower().endswith("grade"):
                            grade_clean += " Grade"
                        labels_to_apply.append(f"{child_base}/{grade_clean}")
                else:
                    labels_to_apply.append(LABEL_MAPPING["general"])

                created_events: list[str] = []

                # 4. Handle calendar events
                for event in triage_res.calendar_events:
                    if self.dry_run:
                        event_desc = f"[DRY-RUN] Would create: '{event.title}' ({event.start_iso} to {event.end_iso})"
                        logger.info(event_desc)
                        created_events.append(f"dry-run:{event.title}")
                    else:
                        created = self.calendar.insert_event(event)
                        created_events.append(created.get("id", "created"))

                # 5. Handle action items -> Google Tasks
                if triage_res.action_items and self.tasks:
                    tasklist_name = (
                        f"School - {config.SON_NAME or 'Child 2'}"
                        if triage_res.target_child == "son"
                        else f"School - {config.DAUGHTER_NAME or 'Child 1'}"
                        if triage_res.target_child == "daughter"
                        else "School Tasks"
                    )
                    for item in triage_res.action_items:
                        if self.dry_run:
                            logger.info(f"[DRY-RUN] Would create Google Task in '{tasklist_name}': {item}")
                        else:
                            try:
                                self.tasks.insert_task(
                                    title=item,
                                    notes=f"Source Email: {parsed['subject']}\nFrom: {parsed['sender']}",
                                    tasklist_name=tasklist_name,
                                )
                            except Exception as task_err:
                                logger.warning(f"Could not create Google Task '{item}': {task_err}")

                # 6. Handle Gmail labeling, mark as read, and archive from INBOX
                if self.dry_run:
                    logger.info(
                        f"[DRY-RUN] Would apply labels {labels_to_apply}, remove UNREAD, and remove INBOX (archive) on msg {msg_id}"
                    )

                else:
                    self.gmail.apply_labels_and_mark_read(
                        message_id=msg_id,
                        add_label_names=labels_to_apply,
                        mark_as_read=True,
                        archive=True,
                    )


                processed = ProcessedEmail(
                    message_id=msg_id,
                    thread_id=parsed["thread_id"],
                    subject=parsed["subject"],
                    sender=parsed["sender"],
                    date_str=parsed["date_str"],
                    snippet=parsed["snippet"],
                    plain_text=parsed["plain_text"],
                    triage_result=triage_res,
                    created_events=created_events,
                    applied_labels=labels_to_apply,
                )
                processed_results.append(processed)

            except Exception as e:
                logger.error(f"Error triaging message {msg_id}: {e}", exc_info=True)
                if progress_callback:
                    progress_callback(f"Failed to process message {msg_id}: {e}")

        return processed_results
