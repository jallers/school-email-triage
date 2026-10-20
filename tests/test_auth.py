"""Unit tests for the authentication module."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from google.auth.exceptions import TransportError, RefreshError
from google.oauth2.credentials import Credentials

from school_email_triage.auth import get_credentials, AuthenticationError


def test_get_credentials_valid_token(tmp_path: Path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "abc", "refresh_token": "ref_abc"}')

    mock_creds = MagicMock(spec=Credentials)
    mock_creds.expired = False
    mock_creds.valid = True

    with patch("school_email_triage.auth.Credentials.from_authorized_user_file", return_value=mock_creds):
        creds = get_credentials(token_path=token_file)
        assert creds is mock_creds
        assert creds.valid


def test_get_credentials_expired_token_refreshes_successfully(tmp_path: Path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "abc", "refresh_token": "ref_abc"}')

    mock_creds = MagicMock(spec=Credentials)
    mock_creds.expired = True
    mock_creds.valid = False
    mock_creds.refresh_token = "ref_abc"
    mock_creds.to_json.return_value = '{"token": "new_abc", "refresh_token": "ref_abc"}'

    def do_refresh(request):
        mock_creds.expired = False
        mock_creds.valid = True

    mock_creds.refresh.side_effect = do_refresh

    with patch("school_email_triage.auth.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("school_email_triage.auth._save_token") as mock_save:
        creds = get_credentials(token_path=token_file)
        assert creds is mock_creds
        mock_creds.refresh.assert_called_once()
        mock_save.assert_called_once()


def test_get_credentials_transient_network_error_retries_and_preserves_token(tmp_path: Path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "abc", "refresh_token": "ref_abc"}')

    mock_creds = MagicMock(spec=Credentials)
    mock_creds.expired = True
    mock_creds.valid = False
    mock_creds.refresh_token = "ref_abc"
    mock_creds.refresh.side_effect = TransportError("Connection reset by peer (10054)")

    with patch("school_email_triage.auth.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(AuthenticationError) as exc_info:
            get_credentials(token_path=token_file)
        assert "Network error while refreshing OAuth token" in str(exc_info.value)
        assert mock_creds.refresh.call_count == 3
        assert mock_sleep.call_count == 2


def test_get_credentials_revoked_token_in_non_interactive_raises(tmp_path: Path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token": "abc", "refresh_token": "ref_abc"}')
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}')

    mock_creds = MagicMock(spec=Credentials)
    mock_creds.expired = True
    mock_creds.valid = False
    mock_creds.refresh_token = "ref_abc"
    mock_creds.refresh.side_effect = RefreshError("invalid_grant: Token has been expired or revoked.")

    with patch("school_email_triage.auth.Credentials.from_authorized_user_file", return_value=mock_creds), \
         patch("sys.stdin.isatty", return_value=False), \
         patch("sys.argv", ["school-email-triage"]):
        with pytest.raises(AuthenticationError) as exc_info:
            get_credentials(credentials_path=creds_file, token_path=token_file)
        assert "--auth-only" in str(exc_info.value)
