"""Gmail API service wrapper for search, message retrieval, and label management."""

from __future__ import annotations

import logging
from typing import Any
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class GmailService:
    """Wrapper around Google Gmail API."""

    def __init__(self, credentials: Credentials, service: Resource | None = None):
        self.service: Resource = service or build("gmail", "v1", credentials=credentials)
        self._label_cache: dict[str, str] = {}  # name -> id

    def list_messages(self, query: str, max_results: int = 50) -> list[dict[str, str]]:
        """List messages matching the search query.

        Returns:
            List of message reference dicts: [{'id': '...', 'threadId': '...'}, ...]
        """
        logger.info(f"Querying Gmail with: '{query}' (limit={max_results})")
        try:
            response = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = response.get("messages", [])
            logger.info(f"Found {len(messages)} matching email(s).")
            return messages
        except Exception as e:
            logger.error(f"Error querying Gmail messages: {e}")
            raise

    def get_message(self, message_id: str) -> dict[str, Any]:
        """Fetch the full payload for a specific message ID."""
        try:
            return (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except Exception as e:
            logger.error(f"Error retrieving message {message_id}: {e}")
            raise

    def get_all_labels(self) -> dict[str, str]:
        """Fetch and cache all user and system labels (name -> id)."""
        if self._label_cache:
            return self._label_cache
        try:
            response = self.service.users().labels().list(userId="me").execute()
            labels = response.get("labels", [])
            self._label_cache = {l["name"]: l["id"] for l in labels}
            return self._label_cache
        except Exception as e:
            logger.error(f"Error fetching Gmail labels: {e}")
            raise

    def get_or_create_label(self, label_name: str) -> str:
        """Retrieve existing label ID or create it if missing."""
        labels = self.get_all_labels()
        if label_name in labels:
            return labels[label_name]

        logger.info(f"Creating missing Gmail label: '{label_name}'")
        try:
            body = {
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            new_label = (
                self.service.users()
                .labels()
                .create(userId="me", body=body)
                .execute()
            )
            label_id = new_label["id"]
            self._label_cache[label_name] = label_id
            return label_id
        except Exception as e:
            logger.error(f"Failed to create label '{label_name}': {e}")
            raise

    def apply_labels_and_mark_read(
        self,
        message_id: str,
        add_label_names: list[str],
        mark_as_read: bool = True,
        archive: bool = True,
    ) -> None:
        """Add specified labels, remove UNREAD, and remove INBOX if archive is True."""
        add_ids = [self.get_or_create_label(name) for name in add_label_names if name]
        remove_ids: list[str] = []
        if mark_as_read:
            remove_ids.append("UNREAD")
        if archive:
            remove_ids.append("INBOX")

        body: dict[str, list[str]] = {}
        if add_ids:
            body["addLabelIds"] = add_ids
        if remove_ids:
            body["removeLabelIds"] = remove_ids

        logger.info(
            f"Modifying message {message_id}: adding labels {add_label_names}, "
            f"mark_as_read={mark_as_read}, archive={archive}"
        )
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body=body,
            ).execute()

        except Exception as e:
            logger.error(f"Failed to modify labels on message {message_id}: {e}")
            raise
