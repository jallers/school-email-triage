"""Unit tests for the end-to-end TriagePipeline."""

import base64
from unittest.mock import MagicMock
from school_email_triage import config
from school_email_triage.pipeline import TriagePipeline
from school_email_triage.models import EmailTriageResult, CalendarEvent


def create_fake_gmail_message(msg_id: str, subject: str, sender: str, body: str) -> dict:
    b64_body = base64.urlsafe_b64encode(body.encode()).decode()
    return {
        "id": msg_id,
        "threadId": f"thread_{msg_id}",
        "snippet": body[:100],
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "Date", "value": "Fri, 04 Sep 2026 09:00:00 -0400"},
            ],
            "mimeType": "text/plain",
            "body": {"data": b64_body},
        },
    }


def test_pipeline_dry_run():
    mock_gmail = MagicMock()
    mock_calendar = MagicMock()
    mock_extractor = MagicMock()

    mock_gmail.list_messages.return_value = [{"id": "msg_001", "threadId": "thr_001"}]
    mock_gmail.get_message.return_value = create_fake_gmail_message(
        "msg_001",
        "5th Grade Science Fair",
        "teacher@schooldistrict.org",
        "Please join us for the 5th Grade Science Fair on Friday, Oct 2 from 5-7pm.",
    )

    mock_extractor.extract_from_email.return_value = EmailTriageResult(
        target_child="daughter",
        summary="5th grade science fair details.",
        action_items=["Submit project boards by Thursday, Oct 1"],
        calendar_events=[
            CalendarEvent(
                title="5th Grade Science Fair",
                start_iso="2026-10-02T17:00:00",
                end_iso="2026-10-02T19:00:00",
                notes="Gymnasium",
            )
        ],
    )

    pipeline = TriagePipeline(
        gmail_service=mock_gmail,
        calendar_service=mock_calendar,
        extractor=mock_extractor,
        dry_run=True,
    )

    results = pipeline.run(query="from:schooldistrict.org", limit=5)

    assert len(results) == 1
    assert results[0].triage_result.target_child == "daughter"
    assert "School/Processed" in results[0].applied_labels
    assert any(config.LABEL_DAUGHTER in label for label in results[0].applied_labels)

    # Dry-run must NOT mutate Gmail or Calendar
    mock_calendar.insert_event.assert_not_called()
    mock_gmail.apply_labels_and_mark_read.assert_not_called()


def test_pipeline_live_run():
    mock_gmail = MagicMock()
    mock_calendar = MagicMock()
    mock_extractor = MagicMock()

    mock_gmail.list_messages.return_value = [{"id": "msg_002", "threadId": "thr_002"}]
    mock_gmail.get_message.return_value = create_fake_gmail_message(
        "msg_002",
        "ParentSquare: Track & Field Practice",
        "notifications@parentsquare.com",
        "Boys track and field practice starts Monday at 3:30pm.",
    )

    mock_calendar.insert_event.return_value = {"id": "cal_evt_999"}
    mock_extractor.extract_from_email.return_value = EmailTriageResult(
        target_child="son",
        summary="Track and field practice schedule.",
        action_items=["Bring water bottle and running shoes"],
        calendar_events=[
            CalendarEvent(
                title="Track & Field Practice",
                start_iso="2026-09-07T15:30:00",
                end_iso="2026-09-07T17:00:00",
                notes="Track Field",
            )
        ],
    )

    pipeline = TriagePipeline(
        gmail_service=mock_gmail,
        calendar_service=mock_calendar,
        extractor=mock_extractor,
        dry_run=False,
    )

    results = pipeline.run(query="from:parentsquare.com", limit=5)

    assert len(results) == 1
    assert results[0].triage_result.target_child == "son"
    assert any(config.LABEL_SON in label for label in results[0].applied_labels)

    # Live run MUST call Calendar and Gmail modifications
    mock_calendar.insert_event.assert_called_once()
    mock_gmail.apply_labels_and_mark_read.assert_called_once()


def test_pipeline_tasks_integration():
    mock_gmail = MagicMock()
    mock_calendar = MagicMock()
    mock_extractor = MagicMock()
    mock_tasks = MagicMock()

    mock_gmail.list_messages.return_value = [{"id": "msg_003", "threadId": "thr_003"}]
    mock_gmail.get_message.return_value = create_fake_gmail_message(
        "msg_003",
        "Permission Slip Reminder",
        "teacher@schooldistrict.org",
        "Please sign the permission slip for the upcoming field trip.",
    )

    mock_extractor.extract_from_email.return_value = EmailTriageResult(
        target_child="daughter",
        summary="Permission slip reminder.",
        action_items=["Sign and return field trip permission slip"],
        calendar_events=[],
    )

    pipeline = TriagePipeline(
        gmail_service=mock_gmail,
        calendar_service=mock_calendar,
        extractor=mock_extractor,
        tasks_service=mock_tasks,
        dry_run=False,
    )

    results = pipeline.run(query="from:schooldistrict.org", limit=5)

    assert len(results) == 1
    mock_tasks.insert_task.assert_called_once()
    call_kwargs = mock_tasks.insert_task.call_args.kwargs
    assert call_kwargs["title"] == "Sign and return field trip permission slip"
    expected_tasklist = f"School - {config.DAUGHTER_NAME or 'Child 1'}"
    assert call_kwargs["tasklist_name"] == expected_tasklist


