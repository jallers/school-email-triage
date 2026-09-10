"""Google Tasks API service wrapper for inserting school action items."""

from __future__ import annotations

import logging
from typing import Any
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class TasksService:
    """Wrapper around Google Tasks API."""

    def __init__(self, credentials: Credentials, service: Resource | None = None):
        self.credentials = credentials
        self._service: Resource | None = service
        self._tasklist_cache: dict[str, str] = {}  # title -> id

    @property
    def service(self) -> Resource:
        if self._service is None:
            self._service = build("tasks", "v1", credentials=self.credentials)
        return self._service

    def get_or_create_tasklist(self, list_title: str = "School Tasks") -> str:
        """Find an existing task list by title or create one if not found."""
        if list_title in self._tasklist_cache:
            return self._tasklist_cache[list_title]

        try:
            res = self.service.tasklists().list(maxResults=50).execute()
            for item in res.get("items", []):
                self._tasklist_cache[item["title"]] = item["id"]
                if item["title"] == list_title:
                    return item["id"]

            # Create list if missing
            logger.info(f"Creating Google Tasks list: '{list_title}'")
            created = self.service.tasklists().insert(body={"title": list_title}).execute()
            self._tasklist_cache[list_title] = created["id"]
            return created["id"]
        except Exception as e:
            logger.warning(f"Could not access/create custom tasklist '{list_title}', falling back to default: {e}")
            return "@default"

    def insert_task(
        self,
        title: str,
        notes: str = "",
        tasklist_name: str = "School Tasks",
        due_iso: str | None = None,
    ) -> dict[str, Any]:
        """Insert an action item into Google Tasks."""
        tasklist_id = self.get_or_create_tasklist(tasklist_name)
        body: dict[str, Any] = {
            "title": title,
            "notes": notes,
        }
        if due_iso:
            # Google Tasks expects RFC 3339 format, e.g. 2026-09-15T00:00:00.000Z
            if "T" not in due_iso:
                body["due"] = f"{due_iso}T00:00:00.000Z"
            elif not due_iso.endswith("Z"):
                body["due"] = due_iso

        logger.info(f"Inserting Google Task: '{title}' into list '{tasklist_name}'")
        try:
            created = self.service.tasks().insert(tasklist=tasklist_id, body=body).execute()
            return created
        except Exception as e:
            logger.error(f"Failed to create Google Task '{title}': {e}")
            raise
