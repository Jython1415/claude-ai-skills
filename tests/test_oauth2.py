"""
Tests for OAuth2 functionality in credentials.py

This test suite covers OAuth2 token management including:
- Token caching and expiry
- Token refresh with 5-minute pre-expiry buffer
- Thread-safe token access
- Configuration parsing for Google services (Gmail, GCal, GDrive)
- Credential redaction for security
"""

import os
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

# Add server directory to path
server_dir = os.path.join(os.path.dirname(__file__), "..", "server")
sys.path.insert(0, os.path.abspath(server_dir))

# Mock the redactor before importing credentials module
mock_redactor = Mock()
mock_redactor.track_runtime_credential = Mock()

with patch("error_redaction.get_redactor", return_value=mock_redactor):
    from credentials import (
        KNOWN_SERVICES,
        CredentialStore,
        OAuth2Token,
        ServiceCredential,
    )


class TestOAuth2Token(unittest.TestCase):
    """Test OAuth2Token dataclass."""

    def test_oauth2_token_dataclass(self):
        """Test basic OAuth2Token creation."""
        token = OAuth2Token(access_token="test_access_token_abc123", expires_at=datetime.utcnow() + timedelta(hours=1))

        self.assertEqual(token.access_token, "test_access_token_abc123")
        self.assertIsInstance(token.expires_at, datetime)
        self.assertGreater(token.expires_at, datetime.utcnow())


class TestOAuth2TokenManagement(unittest.TestCase):
    """Test OAuth2 token fetching, caching, and refresh logic."""

    def setUp(self):
        """Set up test credential with OAuth2 configuration."""
        self.credential = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret_xyz",
            refresh_token="test_refresh_token_123",
            token_url="https://oauth2.googleapis.com/token",
        )

    def test_oauth2_initial_token_fetch(self):
        """Test initial OAuth2 token fetch from refresh token."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "mock_access_token_abc123",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            token = self.credential._get_oauth2_token()

            # Verify token was returned
            self.assertIsNotNone(token)
            self.assertEqual(token, "mock_access_token_abc123")

            # Verify POST was made with correct parameters
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertEqual(call_args[0][0], "https://oauth2.googleapis.com/token")

            posted_data = call_args[1]["data"]
            self.assertEqual(posted_data["grant_type"], "refresh_token")
            self.assertEqual(posted_data["client_id"], "test_client_id.apps.googleusercontent.com")
            self.assertEqual(posted_data["client_secret"], "test_client_secret_xyz")
            self.assertEqual(posted_data["refresh_token"], "test_refresh_token_123")

            # Verify token was cached
            self.assertIsNotNone(self.credential._oauth2_token)
            self.assertEqual(self.credential._oauth2_token.access_token, "mock_access_token_abc123")

    def test_oauth2_token_caching(self):
        """Test that valid cached tokens are reused without HTTP calls."""
        # Set up a cached token that expires in 10 minutes (well within safe zone)
        future_expiry = datetime.utcnow() + timedelta(minutes=10)
        self.credential._oauth2_token = OAuth2Token(access_token="cached_token_xyz789", expires_at=future_expiry)

        with patch("requests.post") as mock_post:
            token = self.credential._get_oauth2_token()

            # Should return cached token without making HTTP request
            self.assertEqual(token, "cached_token_xyz789")
            mock_post.assert_not_called()

    def test_oauth2_token_expiry_refresh(self):
        """Test that expired tokens trigger a refresh."""
        # Set up an expired token
        past_expiry = datetime.utcnow() - timedelta(minutes=5)
        self.credential._oauth2_token = OAuth2Token(access_token="expired_token_old", expires_at=past_expiry)

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "refreshed_token_new123", "expires_in": 3600}
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            token = self.credential._get_oauth2_token()

            # Should return new token
            self.assertEqual(token, "refreshed_token_new123")
            mock_post.assert_called_once()

            # Cached token should be updated
            self.assertEqual(self.credential._oauth2_token.access_token, "refreshed_token_new123")

    def test_oauth2_pre_expiry_refresh(self):
        """Test that tokens expiring within 5 minutes are proactively refreshed."""
        # Set up a token expiring in 3 minutes (within 5-minute buffer)
        near_expiry = datetime.utcnow() + timedelta(minutes=3)
        self.credential._oauth2_token = OAuth2Token(access_token="soon_to_expire_token", expires_at=near_expiry)

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "proactively_refreshed_token", "expires_in": 3600}
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            token = self.credential._get_oauth2_token()

            # Should refresh and return new token
            self.assertEqual(token, "proactively_refreshed_token")
            mock_post.assert_called_once()

    def test_oauth2_missing_credentials(self):
        """Test that missing OAuth2 credentials return None."""
        # Test missing client_id
        cred = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id=None,
            client_secret="secret",
            refresh_token="token",
            token_url="https://oauth2.googleapis.com/token",
        )
        self.assertIsNone(cred._get_oauth2_token())

        # Test missing client_secret
        cred = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id="client",
            client_secret=None,
            refresh_token="token",
            token_url="https://oauth2.googleapis.com/token",
        )
        self.assertIsNone(cred._get_oauth2_token())

        # Test missing refresh_token
        cred = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id="client",
            client_secret="secret",
            refresh_token=None,
            token_url="https://oauth2.googleapis.com/token",
        )
        self.assertIsNone(cred._get_oauth2_token())

    def test_oauth2_refresh_failure(self):
        """Test that OAuth2 refresh failures are handled gracefully."""
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("401 Unauthorized")

        with patch("requests.post", return_value=mock_response):
            token = self.credential._get_oauth2_token()
            self.assertIsNone(token)

    def test_oauth2_refresh_network_error(self):
        """Test that network errors during refresh are handled gracefully."""
        import requests as req

        with patch("requests.post", side_effect=req.exceptions.ConnectionError("Network error")):
            token = self.credential._get_oauth2_token()
            self.assertIsNone(token)


class TestOAuth2InjectAuth(unittest.TestCase):
    """Test OAuth2 authentication injection into requests."""

    def setUp(self):
        """Set up test credential with OAuth2 configuration."""
        self.credential = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret_xyz",
            refresh_token="test_refresh_token_123",
            token_url="https://oauth2.googleapis.com/token",
        )

    def test_oauth2_inject_auth(self):
        """Test that inject_auth sets Bearer token in Authorization header."""
        # Set up a valid cached token
        future_expiry = datetime.utcnow() + timedelta(hours=1)
        self.credential._oauth2_token = OAuth2Token(access_token="bearer_token_xyz123", expires_at=future_expiry)

        headers = {"Content-Type": "application/json"}
        url = "https://www.googleapis.com/gmail/v1/users/me/messages"

        with patch("requests.post"):
            modified_headers, modified_url = self.credential.inject_auth(headers, url)

            # Should add Authorization header with Bearer token
            self.assertIn("Authorization", modified_headers)
            self.assertEqual(modified_headers["Authorization"], "Bearer bearer_token_xyz123")

            # URL should be unchanged
            self.assertEqual(modified_url, url)

            # Original headers should be preserved
            self.assertEqual(modified_headers["Content-Type"], "application/json")

    def test_oauth2_inject_auth_no_token(self):
        """Test that inject_auth handles missing token gracefully."""
        headers = {"Content-Type": "application/json"}
        url = "https://www.googleapis.com/gmail/v1/users/me/messages"

        with patch.object(self.credential, "_get_oauth2_token", return_value=None):
            modified_headers, modified_url = self.credential.inject_auth(headers, url)

            # Should not add Authorization header if token fetch fails
            self.assertNotIn("Authorization", modified_headers)


class TestOAuth2CustomTokenUrl(unittest.TestCase):
    """Test OAuth2 with custom token URL."""

    def test_oauth2_custom_token_url(self):
        """Test that custom token_url is used in POST request."""
        custom_url = "https://custom.oauth.provider/token"
        credential = ServiceCredential(
            service_type="oauth2",
            base_url="https://api.custom.service",
            client_id="custom_client_id",
            client_secret="custom_secret",
            refresh_token="custom_refresh",
            token_url=custom_url,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "custom_token", "expires_in": 7200}
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            credential._get_oauth2_token()

            # Verify custom token URL was used
            mock_post.assert_called_once()
            self.assertEqual(mock_post.call_args[0][0], custom_url)


class TestOAuth2ConfigParsing(unittest.TestCase):
    """Test parsing of OAuth2 configurations."""

    def test_parse_oauth2_known_service(self):
        """Test parsing OAuth2 config for known Google services."""
        store = CredentialStore.__new__(CredentialStore)
        store._credentials = {}

        config = {
            "client_id": "123.apps.googleusercontent.com",
            "client_secret": "secret_xyz",
            "refresh_token": "refresh_abc123",
        }

        # Test Gmail
        cred = store._parse_service_config("gmail", config)
        self.assertIsNotNone(cred)
        self.assertEqual(cred.service_type, "oauth2")
        self.assertEqual(cred.base_url, "https://gmail.googleapis.com")
        self.assertEqual(cred.client_id, "123.apps.googleusercontent.com")
        self.assertEqual(cred.client_secret, "secret_xyz")
        self.assertEqual(cred.refresh_token, "refresh_abc123")
        self.assertEqual(cred.token_url, "https://oauth2.googleapis.com/token")

    def test_parse_oauth2_custom_service(self):
        """Test parsing OAuth2 config with explicit type and URLs."""
        store = CredentialStore.__new__(CredentialStore)
        store._credentials = {}

        config = {
            "type": "oauth2",
            "base_url": "https://api.myservice.com",
            "token_url": "https://auth.myservice.com/oauth/token",
            "client_id": "my_client_id",
            "client_secret": "my_secret",
            "refresh_token": "my_refresh_token",
        }

        cred = store._parse_service_config("myservice", config)
        self.assertIsNotNone(cred)
        self.assertEqual(cred.service_type, "oauth2")
        self.assertEqual(cred.base_url, "https://api.myservice.com")
        self.assertEqual(cred.token_url, "https://auth.myservice.com/oauth/token")
        self.assertEqual(cred.client_id, "my_client_id")
        self.assertEqual(cred.client_secret, "my_secret")
        self.assertEqual(cred.refresh_token, "my_refresh_token")

    def test_parse_oauth2_type_inference(self):
        """Test that presence of refresh_token infers oauth2 type."""
        store = CredentialStore.__new__(CredentialStore)
        store._credentials = {}

        config = {
            "base_url": "https://api.example.com",
            "client_id": "inferred_client",
            "client_secret": "inferred_secret",
            "refresh_token": "inferred_refresh",  # This should trigger oauth2 type inference
        }

        cred = store._parse_service_config("inferred", config)
        self.assertIsNotNone(cred)
        self.assertEqual(cred.service_type, "oauth2")


class TestKnownServicesGoogle(unittest.TestCase):
    """Test KNOWN_SERVICES entries for Google services."""

    def test_known_services_google(self):
        """Test that Gmail, Google Calendar, and Google Drive are in KNOWN_SERVICES."""
        # Gmail
        self.assertIn("gmail", KNOWN_SERVICES)
        gmail = KNOWN_SERVICES["gmail"]
        self.assertEqual(gmail["type"], "oauth2")
        self.assertEqual(gmail["base_url"], "https://gmail.googleapis.com")

        # Google Calendar
        self.assertIn("gcal", KNOWN_SERVICES)
        gcal = KNOWN_SERVICES["gcal"]
        self.assertEqual(gcal["type"], "oauth2")
        self.assertEqual(gcal["base_url"], "https://www.googleapis.com/calendar/v3")

        # Google Drive
        self.assertIn("gdrive", KNOWN_SERVICES)
        gdrive = KNOWN_SERVICES["gdrive"]
        self.assertEqual(gdrive["type"], "oauth2")
        self.assertEqual(gdrive["base_url"], "https://www.googleapis.com/drive/v3")


class TestOAuth2Redaction(unittest.TestCase):
    """Test that OAuth2 tokens are tracked for redaction."""

    def setUp(self):
        """Set up test credential with OAuth2 configuration."""
        self.credential = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret_xyz",
            refresh_token="test_refresh_token_123",
            token_url="https://oauth2.googleapis.com/token",
        )

    def test_redactor_tracks_oauth2_token(self):
        """Test that redactor.track_runtime_credential is called with access token."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "sensitive_token_should_be_redacted",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = Mock()

        patched_redactor = Mock()

        with (
            patch("credentials.requests.post", return_value=mock_response),
            patch("credentials.redactor", patched_redactor),
        ):
            self.credential._get_oauth2_token()

            # Verify redactor was called with the access token
            patched_redactor.track_runtime_credential.assert_called_with("sensitive_token_should_be_redacted")


class TestOAuth2ThreadSafety(unittest.TestCase):
    """Test thread-safety of OAuth2 token management."""

    def test_oauth2_concurrent_access(self):
        """Test that concurrent token requests are thread-safe."""
        credential = ServiceCredential(
            service_type="oauth2",
            base_url="https://www.googleapis.com/gmail/v1",
            client_id="test_client_id",
            client_secret="test_secret",
            refresh_token="test_refresh",
            token_url="https://oauth2.googleapis.com/token",
        )

        # Counter to track how many times refresh is called
        call_count = [0]
        lock = threading.Lock()

        def mock_post_with_delay(*args, **kwargs):
            """Mock POST that simulates network delay."""
            with lock:
                call_count[0] += 1
            time.sleep(0.1)  # Simulate network delay

            response = MagicMock()
            response.json.return_value = {"access_token": f"token_{call_count[0]}", "expires_in": 3600}
            response.raise_for_status = Mock()
            return response

        with patch("requests.post", side_effect=mock_post_with_delay):
            # Launch multiple threads trying to get token simultaneously
            threads = []
            results = []

            def get_token():
                token = credential._get_oauth2_token()
                results.append(token)

            for _ in range(5):
                thread = threading.Thread(target=get_token)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            # All threads should get a token
            self.assertEqual(len(results), 5)
            for token in results:
                self.assertIsNotNone(token)

            # Due to locking, POST should only be called once (or very few times)
            # This verifies the lock prevents redundant refreshes
            self.assertLessEqual(call_count[0], 2)


if __name__ == "__main__":
    unittest.main()
