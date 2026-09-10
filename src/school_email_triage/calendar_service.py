"""Google Calendar API service wrapper for inserting school events with 24h popup reminders."""

from __future__ import annotations

import datetime
import logging
from typing import Any
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials

from .models import CalendarEvent

logger = logging.getLogger(__name__)


def _format_event_datetime(iso_str: str) -> dict[str, str]:
    """Parse ISO string and return calendar API start/end dict with valid timezone.

    Supports:
    - Date-time: '2026-09-15T18:00:00', '2026-09-15T18:00:00Z', etc. -> {'dateTime': ...}
    - All-day date: '2026-09-15' -> {'date': '2026-09-15'}
    """
    iso_clean = iso_str.strip()
    if "T" in iso_clean:
        try:
            dt = datetime.datetime.fromisoformat(iso_clean)
            if dt.tzinfo is None:
                # Attach local system timezone so Google Calendar doesn't reject it
                local_tz = datetime.datetime.now().astimezone().tzinfo
                dt = dt.replace(tzinfo=local_tz)
            return {"dateTime": dt.isoformat()}
        except Exception:
            # Fallback to local offset if ISO parsing failed
            local_offset = datetime.datetime.now().astimezone().strftime("%z")
            formatted_offset = f"{local_offset[:3]}:{local_offset[3:]}" if len(local_offset) == 5 else local_offset
            return {"dateTime": f"{iso_clean}{formatted_offset}"}
    else:
        # All-day event
        return {"date": iso_clean}


def build_calendar_event_body(event: CalendarEvent) -> dict[str, Any]:
    """Construct Google Calendar event resource payload with a 24h pop-up reminder."""
    start_dict = _format_event_datetime(event.start_iso)
    end_dict = _format_event_datetime(event.end_iso)

    # Ensure end is valid; if end is same as or before start for timed event, add 1 hour
    if "dateTime" in start_dict and "dateTime" in end_dict:
        try:
            start_dt = datetime.datetime.fromisoformat(start_dict["dateTime"])
            end_dt = datetime.datetime.fromisoformat(end_dict["dateTime"])
            if end_dt <= start_dt:
                end_dt = start_dt + datetime.timedelta(hours=1)
                end_dict = {"dateTime": end_dt.isoformat()}
        except Exception:
            pass


    return {
        "summary": event.title,
        "description": event.notes or "Added by School Email Triage",
        "start": start_dict,
        "end": end_dict,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {
                    "method": "popup",
                    "minutes": 1440,  # 24 hours * 60 minutes = 1440
                }
            ],
        },
    }


class CalendarService:
    """Wrapper around Google Calendar API."""

    def __init__(self, credentials: Credentials, service: Resource | None = None):
        self.service: Resource = service or build("calendar", "v3", credentials=credentials)

    def insert_event(
        self,
        event: CalendarEvent,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Insert an event into the target calendar with 24-hour popup reminder.

        Returns:
            The created event resource dict (includes 'id' and 'htmlLink').
        """
        body = build_calendar_event_body(event)
        logger.info(
            f"Inserting calendar event: '{event.title}' on {event.start_iso} "
            f"into calendar '{calendar_id}'"
        )
        try:
            created = (
                self.service.events()
                .insert(calendarId=calendar_id, body=body)
                .execute()
            )
            logger.info(f"Event created successfully. ID: {created.get('id')}")
            return created
        except Exception as e:
            logger.error(f"Failed to insert calendar event '{event.title}': {e}")
            raise
