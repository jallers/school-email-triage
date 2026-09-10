"""Gemini structured data extraction using Google GenAI SDK and Pydantic."""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from google import genai
from google.genai import types

from .config import (
    DEFAULT_GEMINI_MODEL,
    DAUGHTER_NAME,
    SON_NAME,
    DAUGHTER_SCHOOL,
    SON_SCHOOL,
    DAUGHTER_TEACHERS,
    SON_TEACHERS,
    DAUGHTER_KEYWORDS,
    SON_KEYWORDS,
)
from .models import EmailTriageResult

logger = logging.getLogger(__name__)


def build_system_instruction(
    ref_time: datetime.datetime | None = None,
    daughter_name: str = DAUGHTER_NAME,
    son_name: str = SON_NAME,
    daughter_school: str = DAUGHTER_SCHOOL,
    son_school: str = SON_SCHOOL,
    daughter_teachers: str = DAUGHTER_TEACHERS,
    son_teachers: str = SON_TEACHERS,
    daughter_keywords: str = DAUGHTER_KEYWORDS,
    son_keywords: str = SON_KEYWORDS,
) -> str:
    """Construct system instructions with anchor date and child disambiguation context."""
    if ref_time is None:
        ref_time = datetime.datetime.now().astimezone()

    now_str = ref_time.strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    year = ref_time.year

    hints = []
    if daughter_name:
        hints.append(f"- Daughter's name: {daughter_name}")
    if daughter_school:
        hints.append(f"- Daughter's school/grade: {daughter_school}")
    if daughter_teachers:
        hints.append(f"- Daughter's teachers: {daughter_teachers}")
    if daughter_keywords:
        hints.append(f"- Daughter's courses/subjects: {daughter_keywords}")

    if son_name:
        hints.append(f"- Son's name: {son_name}")
    if son_school:
        hints.append(f"- Son's school/grade: {son_school}")
    if son_teachers:
        hints.append(f"- Son's teachers: {son_teachers}")
    if son_keywords:
        hints.append(f"- Son's courses/subjects: {son_keywords}")

    hint_section = "\n".join(hints) if hints else "- No specific child/teacher names provided; infer from context or use 'general'."

    return f"""You are an executive assistant specializing in triaging school emails for a parent.
The current reference time is: {now_str}.
The current school year is based around year: {year}.

Family Context:
{hint_section}
- Teacher names can appear as first names, last names, or honorifics (e.g. 'Sarah', 'Daniels', 'H-DANIELS', 'Mr. Miller'). Match on any form.
- Also match on specific courses, instruments, music/band/chorus programs, sports, or clubs mentioned in the hints.


Your task is to analyze the provided school email and extract:
1. target_child:
   - "daughter": if the email is specifically addressed to, about, or relevant to the daughter (e.g. her grade, teacher, class, sport, team, or name).
   - "son": if the email is specifically addressed to, about, or relevant to the son.
   - "general": if the email is a district-wide newsletter, whole-school announcement, administrative notification, or if it cannot be determined with confidence.

2. grade_level:
   - The grade level associated with this email, formatted like '6th Grade', '7th Grade', '8th Grade', '9th Grade', '10th Grade'.
   - Determine this from explicit mentions (e.g. '7th Grade Life Science', '8th Grade Trip') or infer from the email date and student:
     - Son: 8th Grade (2025-2026), 7th Grade (2024-2025), 6th Grade (2023-2024).
     - Daughter: 10th Grade (2025-2026), 9th Grade (2024-2025), 8th Grade (2023-2024).
   - Return null if no specific grade can be determined.

3. action_items:
   - Specific tasks required of the parent or student (e.g., signing permission slips, paying fees, ordering lunch, sending supplies).
   - ALWAYS include the specific deadline or due date in the action item string if mentioned (e.g. 'Submit science fair proposal by Sept 18').
   - If there are no required actions, return an empty list.


3. calendar_events:
   - Real scheduled events (e.g. Back-to-School Night, Minimum Days, Parent-Teacher Conferences, Sports Games, Picture Day, Field Trips, Concerts).
   - Do NOT create events for vague suggestions or open-ended reading periods.
   - start_iso and end_iso MUST be strictly formatted ISO 8601 strings:
     - For timed events: 'YYYY-MM-DDTHH:MM:SS' (e.g. '2026-09-15T18:00:00')
     - For full-day events: 'YYYY-MM-DD' (e.g. '2026-09-15')
   - If an end time is not given, default to 1 hour after the start time for timed events, or the same date for all-day events.
   - Calculate relative dates (e.g. 'this Friday', 'next Tuesday', 'tomorrow') accurately using the reference time ({now_str}).
   - notes: include location (e.g. 'School Auditorium' or 'Zoom link: ...'), dress code, what to bring, or event details.

4. summary:
   - A concise 1-2 sentence overview of the email.
"""


def is_transient_gemini_error(exc: BaseException) -> bool:
    """Check if exception is a transient error suitable for retry."""
    from google.genai import errors
    if isinstance(exc, errors.APIError):
        return exc.code in (429, 500, 502, 503, 504)
    err_str = str(exc)
    return any(
        phrase in err_str
        for phrase in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "high demand", "rate limit")
    )


class GeminiExtractor:
    """Wrapper around Google GenAI client for structured extraction."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_GEMINI_MODEL,
        client: genai.Client | None = None,
    ):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        if client:
            self.client = client
        elif self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def is_available(self) -> bool:
        """Check whether the Gemini client has been initialized."""
        return self.client is not None

    def extract_from_email(
        self,
        subject: str,
        sender: str,
        date_str: str,
        body_text: str,
        ref_time: datetime.datetime | None = None,
    ) -> EmailTriageResult:
        """Extract structured triage data from email content using Gemini."""
        if not self.client:
            raise RuntimeError(
                "Gemini client is not initialized. Ensure GEMINI_API_KEY is set in the environment or .env."
            )

        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

        system_instruction = build_system_instruction(ref_time=ref_time)

        user_content = f"""Subject: {subject}
From: {sender}
Date: {date_str}

Email Body:
\"\"\"
{body_text}
\"\"\"
"""

        logger.info(f"Sending email '{subject}' to Gemini ({self.model_name}) for structured extraction...")

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=EmailTriageResult,
            temperature=0.1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        @retry(
            retry=retry_if_exception(is_transient_gemini_error),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            before_sleep=lambda rs: logger.warning(
                f"Gemini server busy (503/429). Retrying attempt {rs.attempt_number}/5 in {rs.next_action.sleep:.1f}s..."
            ),
            reraise=True,
        )
        def _call_gemini():
            return self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=config,
            )

        response = _call_gemini()

        # Parse structured result
        if hasattr(response, "parsed") and isinstance(response.parsed, EmailTriageResult):
            return response.parsed
        elif response.text:
            return EmailTriageResult.model_validate_json(response.text)
        else:
            raise ValueError("Empty or invalid response received from Gemini model")

