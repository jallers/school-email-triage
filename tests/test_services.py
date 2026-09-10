"""Unit tests for GmailService and CalendarService."""

from unittest.mock import MagicMock
from school_email_triage.models import CalendarEvent
from school_email_triage.calendar_service import CalendarService, build_calendar_event_body
from school_email_triage.gmail_service import GmailService


def test_build_calendar_event_body_popup_reminder():
    event = CalendarEvent(
        title="Curriculum Night",
        start_iso="2026-09-16T18:00:00",
        end_iso="2026-09-16T19:30:00",
        notes="High School Cafeteria",
    )
    body = build_calendar_event_body(event)
    assert body["summary"] == "Curriculum Night"
    assert "2026-09-16T18:00:00" in body["start"]["dateTime"]
    assert "2026-09-16T19:30:00" in body["end"]["dateTime"]
    assert body["description"] == "High School Cafeteria"


    # Verify 24-hour pop-up reminder (1440 minutes)
    reminders = body.get("reminders", {})
    assert reminders.get("useDefault") is False
    overrides = reminders.get("overrides", [])
    assert len(overrides) == 1
    assert overrides[0] == {"method": "popup", "minutes": 1440}


def test_build_calendar_event_body_all_day():
    event = CalendarEvent(
        title="Staff Development - No School",
        start_iso="2026-10-12",
        end_iso="2026-10-12",
        notes="Holiday",
    )
    body = build_calendar_event_body(event)
    assert body["start"] == {"date": "2026-10-12"}
    assert body["end"] == {"date": "2026-10-12"}


def test_calendar_service_insert_event():
    mock_resource = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_insert.execute.return_value = {
        "id": "event_12345",
        "htmlLink": "https://calendar.google.com/event?eid=12345",
    }
    mock_events.insert.return_value = mock_insert
    mock_resource.events.return_value = mock_events

    cal_service = CalendarService(credentials=None, service=mock_resource)
    event = CalendarEvent(
        title="Band Concert",
        start_iso="2026-12-10T19:00:00",
        end_iso="2026-12-10T20:30:00",
        notes="Main Auditorium",
    )
    res = cal_service.insert_event(event)
    assert res["id"] == "event_12345"
    mock_events.insert.assert_called_once()


def test_gmail_service_label_caching_and_creation():
    mock_resource = MagicMock()
    mock_users = MagicMock()
    mock_labels = MagicMock()
    mock_messages = MagicMock()

    mock_resource.users.return_value = mock_users
    mock_users.labels.return_value = mock_labels
    mock_users.messages.return_value = mock_messages

    # Initial list labels returns only INBOX
    mock_list_labels = MagicMock()
    mock_list_labels.execute.return_value = {
        "labels": [{"id": "Label_INBOX", "name": "INBOX"}]
    }
    mock_labels.list.return_value = mock_list_labels

    # Creation of School/Daughter
    mock_create_label = MagicMock()
    mock_create_label.execute.return_value = {
        "id": "Label_Daughter",
        "name": "School/Daughter",
    }
    mock_labels.create.return_value = mock_create_label

    gmail_service = GmailService(credentials=None, service=mock_resource)

    # First call creates the label
    label_id = gmail_service.get_or_create_label("School/Daughter")
    assert label_id == "Label_Daughter"
    assert mock_labels.create.call_count == 1

    # Second call returns from cache without calling create again
    cached_id = gmail_service.get_or_create_label("School/Daughter")
    assert cached_id == "Label_Daughter"
    assert mock_labels.create.call_count == 1


def test_gmail_service_apply_labels_and_mark_read():
    mock_resource = MagicMock()
    mock_users = MagicMock()
    mock_labels = MagicMock()
    mock_messages = MagicMock()

    mock_resource.users.return_value = mock_users
    mock_users.labels.return_value = mock_labels
    mock_users.messages.return_value = mock_messages

    # Pre-load label cache
    mock_list_labels = MagicMock()
    mock_list_labels.execute.return_value = {
        "labels": [
            {"id": "Label_Processed", "name": "School/Processed"},
            {"id": "Label_Son", "name": "School/Son"},
        ]
    }
    mock_labels.list.return_value = mock_list_labels

    mock_modify = MagicMock()
    mock_modify.execute.return_value = {"id": "msg_001"}
    mock_messages.modify.return_value = mock_modify

    gmail_service = GmailService(credentials=None, service=mock_resource)
    gmail_service.apply_labels_and_mark_read(
        message_id="msg_001",
        add_label_names=["School/Processed", "School/Son"],
        mark_as_read=True,
        archive=True,
    )

    mock_messages.modify.assert_called_once_with(
        userId="me",
        id="msg_001",
        body={
            "addLabelIds": ["Label_Processed", "Label_Son"],
            "removeLabelIds": ["UNREAD", "INBOX"],
        },
    )


def test_tasks_service_insert_task():
    from school_email_triage.tasks_service import TasksService
    mock_resource = MagicMock()
    mock_tasklists = MagicMock()
    mock_tasks = MagicMock()

    mock_resource.tasklists.return_value = mock_tasklists
    mock_resource.tasks.return_value = mock_tasks

    # Mock tasklists.list
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "items": [{"id": "list_123", "title": "School - Child 2"}]
    }
    mock_tasklists.list.return_value = mock_list

    # Mock tasks.insert
    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "task_abc", "title": "Finish science lab"}
    mock_tasks.insert.return_value = mock_insert

    service = TasksService(credentials=None, service=mock_resource)
    res = service.insert_task(
        title="Finish science lab",
        notes="From email",
        tasklist_name="School - Child 2",
        due_iso="2026-09-15",
    )
    assert res["id"] == "task_abc"
    mock_tasks.insert.assert_called_once()


