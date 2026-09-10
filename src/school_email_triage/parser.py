"""MIME email parser for extracting plain text and metadata from Gmail messages."""

from __future__ import annotations

import base64
import email
from email import policy
import logging
from typing import Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def decode_base64_url(data_str: str) -> bytes:
    """Safely decode URL-safe base64 data with proper padding."""
    if not data_str:
        return b""
    # Replace URL-safe chars if needed and add base64 padding
    clean_str = data_str.replace("-", "+").replace("_", "/")
    padding = len(clean_str) % 4
    if padding != 0:
        clean_str += "=" * (4 - padding)
    return base64.b64decode(clean_str)


def decode_payload_body(body_dict: dict[str, Any], default_charset: str = "utf-8") -> str:
    """Decode raw bytes from a Gmail API body dictionary."""
    data = body_dict.get("data")
    if not data:
        return ""
    try:
        raw_bytes = decode_base64_url(data)
        return raw_bytes.decode(default_charset, errors="replace")
    except Exception as e:
        logger.warning(f"Failed to decode body payload: {e}")
        return ""


def clean_html_to_text(html_content: str) -> str:
    """Convert HTML content into clean readable plain text."""
    if not html_content or not html_content.strip():
        return ""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style tags
    for tag in soup(["script", "style", "head", "title", "meta", "noscript"]):
        tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]):
        block.insert_after(soup.new_string("\n"))

    text = soup.get_text()
    # Normalize lines
    lines = [line.strip() for line in text.splitlines()]
    non_empty = []
    prev_blank = False
    for line in lines:
        if line:
            non_empty.append(line)
            prev_blank = False
        elif not prev_blank:
            non_empty.append("")
            prev_blank = True
    return "\n".join(non_empty).strip()




def extract_parts_recursively(part: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Recursively extract plain text and html parts from a Gmail payload part.

    Returns:
        tuple of (list of plain text parts, list of html parts)
    """
    plain_parts: list[str] = []
    html_parts: list[str] = []

    mime_type = part.get("mimeType", "")
    body = part.get("body", {})

    # Extract charset from headers if present
    charset = "utf-8"
    for header in part.get("headers", []):
        if header.get("name", "").lower() == "content-type":
            val = header.get("value", "").lower()
            if "charset=" in val:
                charset = val.split("charset=")[-1].split(";")[0].strip(' "\'')
            break

    if mime_type == "text/plain" and body.get("data"):
        text = decode_payload_body(body, charset)
        if text.strip():
            plain_parts.append(text)
    elif mime_type == "text/html" and body.get("data"):
        html_text = decode_payload_body(body, charset)
        if html_text.strip():
            html_parts.append(html_text)

    # Recurse into sub-parts
    for subpart in part.get("parts", []):
        sub_plain, sub_html = extract_parts_recursively(subpart)
        plain_parts.extend(sub_plain)
        html_parts.extend(sub_html)

    return plain_parts, html_parts


def parse_gmail_message(message_dict: dict[str, Any]) -> dict[str, Any]:
    """Parse a message dict returned by the Gmail REST API (users.messages.get).

    Returns a dict with:
        message_id, thread_id, subject, sender, date_str, snippet, plain_text
    """
    msg_id = message_dict.get("id", "")
    thread_id = message_dict.get("threadId", "")
    snippet = message_dict.get("snippet", "")
    payload = message_dict.get("payload", {})
    headers = payload.get("headers", [])

    header_map: dict[str, str] = {}
    for h in headers:
        header_map[h.get("name", "").lower()] = h.get("value", "")

    subject = header_map.get("subject", "(No Subject)")
    sender = header_map.get("from", "")
    date_str = header_map.get("date", "")

    # Extract text from payload parts
    plain_parts, html_parts = extract_parts_recursively(payload)

    plain_content = "\n\n".join(plain_parts).strip()
    html_content = "\n\n".join(html_parts).strip()

    # Prioritize plain text if it contains substantial body, otherwise use converted HTML
    if len(plain_content) >= 50:
        extracted_text = plain_content
    elif html_content:
        converted = clean_html_to_text(html_content)
        extracted_text = converted if len(converted) > len(plain_content) else plain_content
    else:
        extracted_text = plain_content or snippet

    return {
        "message_id": msg_id,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "date_str": date_str,
        "snippet": snippet,
        "plain_text": extracted_text,
    }


def parse_raw_mime_message(raw_bytes_or_str: bytes | str) -> dict[str, Any]:
    """Fallback parser for standard RFC 822 MIME email string or bytes."""
    if isinstance(raw_bytes_or_str, str):
        msg = email.message_from_string(raw_bytes_or_str, policy=policy.default)
    else:
        msg = email.message_from_bytes(raw_bytes_or_str, policy=policy.default)

    subject = msg.get("Subject", "(No Subject)")
    sender = msg.get("From", "")
    date_str = msg.get("Date", "")

    plain_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition", ""))
            if "attachment" in cdispo:
                continue
            if ctype == "text/plain" and not plain_body:
                plain_body = part.get_content()
            elif ctype == "text/html" and not html_body:
                html_body = part.get_content()
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            plain_body = msg.get_content()
        elif ctype == "text/html":
            html_body = msg.get_content()

    if len(plain_body.strip()) >= 50:
        final_text = plain_body.strip()
    elif html_body.strip():
        final_text = clean_html_to_text(html_body)
    else:
        final_text = plain_body.strip()

    return {
        "message_id": msg.get("Message-ID", ""),
        "thread_id": "",
        "subject": subject,
        "sender": sender,
        "date_str": date_str,
        "snippet": final_text[:200] if final_text else "",
        "plain_text": final_text,
    }
