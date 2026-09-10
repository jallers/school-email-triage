"""Unit tests for MIME email parsing."""

import base64
from school_email_triage.parser import (
    decode_base64_url,
    clean_html_to_text,
    extract_parts_recursively,
    parse_gmail_message,
    parse_raw_mime_message,
)


def test_decode_base64_url():
    original = "Hello, world! Special chars: &?="
    # Standard url-safe base64 without padding
    encoded = base64.urlsafe_b64encode(original.encode()).decode().rstrip("=")
    decoded = decode_base64_url(encoded).decode()
    assert decoded == original


def test_clean_html_to_text():
    html = """
    <html>
        <head><title>Test Title</title></head>
        <style>body { color: red; }</style>
        <body>
            <h1>School Announcement</h1>
            <p>Back to School Night is on <strong>Thursday at 6 PM</strong>.</p>
            <script>alert("ignore");</script>
        </body>
    </html>
    """
    cleaned = clean_html_to_text(html)
    assert "School Announcement" in cleaned
    assert "Back to School Night is on Thursday at 6 PM." in cleaned
    assert "alert" not in cleaned
    assert "Test Title" not in cleaned
    assert "color: red" not in cleaned


def test_parse_gmail_message_multipart():
    body_plain = "Hello Parents,\nField trip permission slip is due on Friday.\nThanks, Teacher"
    body_html = "<p>Hello Parents,<br>Field trip permission slip is due on Friday.<br>Thanks, Teacher</p>"

    b64_plain = base64.urlsafe_b64encode(body_plain.encode()).decode()
    b64_html = base64.urlsafe_b64encode(body_html.encode()).decode()

    mock_msg = {
        "id": "18a1b2c3d4e5f6",
        "threadId": "18a1b2c3d4e5f6",
        "snippet": "Hello Parents, Field trip permission...",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "5th Grade Field Trip Info"},
                {"name": "From", "value": "teacher@schooldistrict.org"},
                {"name": "Date", "value": "Thu, 3 Sep 2026 14:00:00 -0400"},
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "headers": [{"name": "Content-Type", "value": "text/plain; charset=UTF-8"}],
                    "body": {"data": b64_plain},
                },
                {
                    "mimeType": "text/html",
                    "headers": [{"name": "Content-Type", "value": "text/html; charset=UTF-8"}],
                    "body": {"data": b64_html},
                },
            ],
        },
    }

    parsed = parse_gmail_message(mock_msg)
    assert parsed["message_id"] == "18a1b2c3d4e5f6"
    assert parsed["subject"] == "5th Grade Field Trip Info"
    assert parsed["sender"] == "teacher@schooldistrict.org"
    assert "permission slip is due on Friday" in parsed["plain_text"]


def test_parse_gmail_message_html_only():
    body_html = "<div><h3>District Notice</h3><p>Schools are closed next Monday for Labor Day.</p></div>"
    b64_html = base64.urlsafe_b64encode(body_html.encode()).decode()

    mock_msg = {
        "id": "msg_html_only",
        "threadId": "thr_001",
        "snippet": "District Notice...",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Holiday Reminder"},
                {"name": "From", "value": "superintendent@schooldistrict.org"},
                {"name": "Date", "value": "Thu, 3 Sep 2026 10:00:00 -0400"},
            ],
            "mimeType": "text/html",
            "body": {"data": b64_html},
        },
    }

    parsed = parse_gmail_message(mock_msg)
    assert parsed["subject"] == "Holiday Reminder"
    assert "Schools are closed next Monday" in parsed["plain_text"]


def test_parse_raw_mime_message():
    raw_email = (
        "From: admin@parentsquare.com\r\n"
        "To: parent@example.com\r\n"
        "Subject: ParentSquare Notice: Picture Day\r\n"
        "Date: Thu, 03 Sep 2026 12:00:00 +0000\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Please remember that tomorrow is Picture Day at Lincoln Elementary.\r\n"
    )

    parsed = parse_raw_mime_message(raw_email)
    assert parsed["subject"] == "ParentSquare Notice: Picture Day"
    assert "Picture Day at Lincoln Elementary" in parsed["plain_text"]
