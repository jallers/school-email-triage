"""Configuration settings and constants for school-email-triage."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# OAuth scopes for Gmail, Google Calendar, and Google Tasks
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
]

# Google Tasks sync toggle
SYNC_GOOGLE_TASKS: bool = os.getenv("SYNC_GOOGLE_TASKS", "true").lower() in ("true", "1", "yes")


# Default search query for school emails
DEFAULT_QUERY: str = os.getenv(
    "SCHOOL_EMAIL_QUERY",
    "from:(*@schooldistrict.org OR *parentsquare.com) is:unread",
)

# Label definitions
LABEL_PROCESSED: str = os.getenv("LABEL_PROCESSED", "School/Processed")
LABEL_DAUGHTER: str = os.getenv("LABEL_DAUGHTER", "School - Child 1")
LABEL_SON: str = os.getenv("LABEL_SON", "School - Child 2")
LABEL_GENERAL: str = os.getenv("LABEL_GENERAL", "School/General")

LABEL_MAPPING: dict[str, str] = {
    "daughter": LABEL_DAUGHTER,
    "son": LABEL_SON,
    "general": LABEL_GENERAL,
}

DAUGHTER_CURRENT_GRADE: str = os.getenv("DAUGHTER_CURRENT_GRADE", "10th Grade")
SON_CURRENT_GRADE: str = os.getenv("SON_CURRENT_GRADE", "8th Grade")


# Default credentials and token paths
DEFAULT_CREDENTIALS_PATH: Path = Path(os.getenv("CREDENTIALS_PATH", "credentials.json"))
DEFAULT_TOKEN_PATH: Path = Path(os.getenv("TOKEN_PATH", "token.json"))

# Gemini LLM configuration
DEFAULT_GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Optional child hints to help disambiguate
DAUGHTER_NAME: str = os.getenv("DAUGHTER_NAME", "")
SON_NAME: str = os.getenv("SON_NAME", "")
DAUGHTER_SCHOOL: str = os.getenv("DAUGHTER_SCHOOL", "")
SON_SCHOOL: str = os.getenv("SON_SCHOOL", "")
DAUGHTER_TEACHERS: str = os.getenv("DAUGHTER_TEACHERS", "")
SON_TEACHERS: str = os.getenv("SON_TEACHERS", "")
DAUGHTER_KEYWORDS: str = os.getenv("DAUGHTER_KEYWORDS", "")
SON_KEYWORDS: str = os.getenv("SON_KEYWORDS", "")

