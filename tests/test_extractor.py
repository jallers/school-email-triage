"""Unit tests for Gemini extractor and Pydantic models."""

import datetime
from unittest.mock import MagicMock
import pytest
from school_email_triage.models import CalendarEvent, EmailTriageResult
from school_email_triage.extractor import GeminiExtractor, build_system_instruction


def test_calendar_event_model():
    ev = CalendarEvent(
        title="Math Olympiad",
        start_iso="2026-09-20T09:00:00",
        end_iso="2026-09-20T12:00:00",
        notes="Room 204",
    )
    assert ev.title == "Math Olympiad"
    assert ev.start_iso == "2026-09-20T09:00:00"
    assert ev.notes == "Room 204"


def test_email_triage_result_validation():
    data = {
        "target_child": "daughter",
        "action_items": ["Return signed waiver by Sept 10"],
        "calendar_events": [
            {
                "title": "Robotics Club Kickoff",
                "start_iso": "2026-09-12T15:30:00",
                "end_iso": "2026-09-12T16:30:00",
                "notes": "Lab B",
            }
        ],
        "summary": "Robotics club schedule and waiver requirement.",
    }
    result = EmailTriageResult.model_validate(data)
    assert result.target_child == "daughter"
    assert len(result.action_items) == 1
    assert len(result.calendar_events) == 1
    assert result.calendar_events[0].title == "Robotics Club Kickoff"


def test_build_system_instruction():
    ref_dt = datetime.datetime(2026, 9, 4, 10, 0, 0, tzinfo=datetime.timezone.utc)
    instruction = build_system_instruction(
        ref_time=ref_dt,
        daughter_name="Alice",
        son_name="Bob",
        daughter_school="Elementary",
        son_school="High School",
        daughter_teachers="Mrs. Green",
        son_teachers="Coach Taylor",
    )
    assert "2026-09-04" in instruction
    assert "Alice" in instruction
    assert "Bob" in instruction
    assert "Mrs. Green" in instruction
    assert "Coach Taylor" in instruction
    assert "target_child" in instruction



def test_gemini_extractor_mocked_response():
    mock_client = MagicMock()
    mock_response = MagicMock()
    json_payload = """
    {
        "target_child": "son",
        "action_items": ["Bring athletic shoes tomorrow"],
        "calendar_events": [
            {
                "title": "Soccer Tryouts",
                "start_iso": "2026-09-08T15:30:00",
                "end_iso": "2026-09-08T17:00:00",
                "notes": "Main Field"
            }
        ],
        "summary": "Soccer tryouts announcement for middle school."
    }
    """
    mock_response.text = json_payload
    mock_response.parsed = None
    mock_client.models.generate_content.return_value = mock_response

    extractor = GeminiExtractor(api_key="fake-key", client=mock_client)
    res = extractor.extract_from_email(
        subject="Boys Soccer Tryouts",
        sender="coach@schooldistrict.org",
        date_str="Fri, 04 Sep 2026 08:00:00 -0400",
        body_text="Soccer tryouts will be held next Tuesday on the main field.",
    )

    assert res.target_child == "son"
    assert "Bring athletic shoes tomorrow" in res.action_items
    assert len(res.calendar_events) == 1
    assert res.calendar_events[0].title == "Soccer Tryouts"
    assert res.calendar_events[0].start_iso == "2026-09-08T15:30:00"
