"""School Email Triage - Automated school email triage via Gmail, Calendar, and Gemini."""

from .cli import main
from .models import EmailTriageResult, CalendarEvent, ProcessedEmail

__version__ = "0.1.0"
__all__ = ["main", "EmailTriageResult", "CalendarEvent", "ProcessedEmail"]
