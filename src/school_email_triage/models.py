"""Data models for school email triage structured extraction."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """Represents a calendar event extracted from an email."""

    title: str = Field(
        ...,
        description="Clear and concise title of the event (e.g. 'Back to School Night', '5th Grade Field Trip')",
    )
    start_iso: str = Field(
        ...,
        description="ISO 8601 formatted start date/time (e.g. '2026-09-15T18:00:00' or '2026-09-15' for all-day)",
    )
    end_iso: str = Field(
        ...,
        description="ISO 8601 formatted end date/time (e.g. '2026-09-15T19:30:00' or '2026-09-15' for all-day)",
    )
    notes: str = Field(
        default="",
        description="Additional context, location, zoom link, or details for the calendar event",
    )


class EmailTriageResult(BaseModel):
    """Structured extraction result for a school email."""

    target_child: Literal["daughter", "son", "general"] = Field(
        ...,
        description="Attribution of the email: 'daughter' if pertaining to daughter, 'son' if pertaining to son, or 'general' if whole-school/district or unassigned",
    )
    grade_level: str | None = Field(
        default=None,
        description="Detected grade level such as '6th Grade', '7th Grade', '8th Grade', '9th Grade', '10th Grade' if mentioned in the email or implied by course/date",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="List of actionable tasks or deadlines (e.g. 'Sign and return permission slip by Sept 12')",
    )

    calendar_events: list[CalendarEvent] = Field(
        default_factory=list,
        description="List of scheduled events, assemblies, meetings, or key dates found in the email",
    )
    summary: str = Field(
        default="",
        description="A 1-2 sentence executive summary of the email content",
    )


class ProcessedEmail(BaseModel):
    """Container for email metadata, extracted text, and extraction result."""

    message_id: str
    thread_id: str
    subject: str
    sender: str
    date_str: str
    snippet: str
    plain_text: str
    triage_result: EmailTriageResult | None = None
    created_events: list[str] = Field(default_factory=list)
    applied_labels: list[str] = Field(default_factory=list)
