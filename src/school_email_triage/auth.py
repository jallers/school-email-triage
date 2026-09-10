"""OAuth 2.0 authentication manager for Gmail and Calendar APIs."""

from __future__ import annotations

import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import DEFAULT_CREDENTIALS_PATH, DEFAULT_TOKEN_PATH, SCOPES

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication setup or token refresh fails."""
    pass


def get_credentials(
    credentials_path: Path | str = DEFAULT_CREDENTIALS_PATH,
    token_path: Path | str = DEFAULT_TOKEN_PATH,
    headless: bool = False,
) -> Credentials:
    """Load or generate OAuth 2.0 credentials for Gmail and Calendar.

    Args:
        credentials_path: Path to the client secrets credentials.json.
        token_path: Path to store/load the cached token.json.
        headless: If True, uses console-based authentication flow.

    Returns:
        Valid google.oauth2.credentials.Credentials instance.

    Raises:
        AuthenticationError: If credentials.json is missing or auth flow fails.
    """
    credentials_path = Path(credentials_path)
    token_path = Path(token_path)
    creds: Credentials | None = None

    # Step 1: Attempt to load cached token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            logger.debug(f"Loaded credentials from {token_path}")
        except Exception as e:
            logger.warning(f"Failed to load cached token from {token_path}: {e}")
            creds = None

    # Step 2: Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info("Cached token expired. Refreshing token...")
            creds.refresh(Request())
            _save_token(creds, token_path)
            return creds
        except Exception as e:
            logger.warning(f"Could not refresh token: {e}. Re-authenticating...")
            creds = None

    # If valid, return
    if creds and creds.valid:
        return creds

    # Step 3: Run interactive flow
    if not credentials_path.exists():
        raise AuthenticationError(
            f"Credentials file not found at '{credentials_path}'.\n"
            "Please follow these steps:\n"
            "1. Go to Google Cloud Console (https://console.cloud.google.com)\n"
            "2. Enable 'Gmail API' and 'Google Calendar API'\n"
            "3. Create OAuth 2.0 Client ID (Application type: Desktop App)\n"
            f"4. Download the JSON file and save it as '{credentials_path.resolve()}'"
        )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path),
            scopes=SCOPES,
        )
        if headless:
            logger.info("Starting console OAuth flow...")
            creds = flow.run_console()
        else:
            logger.info("Opening browser for OAuth authorization...")
            creds = flow.run_local_server(port=0)

        _save_token(creds, token_path)
        return creds
    except Exception as e:
        raise AuthenticationError(f"OAuth flow failed: {e}") from e


def _save_token(creds: Credentials, token_path: Path) -> None:
    """Save credentials to disk."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    logger.info(f"Saved OAuth token to {token_path}")
