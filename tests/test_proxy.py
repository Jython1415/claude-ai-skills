"""
Unit tests for proxy security logic.

Tests path traversal prevention, header filtering, and error handling
in server/proxy.py using mocks (no real HTTP requests).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

# Add server/ to sys.path so proxy.py's unqualified imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from server.proxy import filter_request_headers, filter_response_headers, forward_request

# =============================================================================
# Helper: mock credential store
# =============================================================================


def make_credential_store(services=None):
    """Create a mock CredentialStore with optional services."""
    store = MagicMock()

    if services is None:
        services = {"test_svc": {"base_url": "https://api.example.com", "service_type": "bearer"}}

    def mock_get(service):
        if service in services:
            cred = MagicMock()
            cred.base_url = services[service]["base_url"]
            cred.inject_auth = MagicMock(side_effect=lambda h, u: (h, u))
            return cred
        return None

    store.get = MagicMock(side_effect=mock_get)
    return store


# =============================================================================
# Path traversal tests
# =============================================================================


class TestPathTraversal:
    """Tests for path traversal prevention in forward_request."""

    def test_raw_dotdot_blocked(self):
        """Raw '..' in path should be rejected."""
        store = make_credential_store()
        resp = forward_request("test_svc", "../etc/passwd", "GET", {}, None, "", store)
        assert resp.status_code == 400
        assert b"path traversal" in resp.data.lower()

    def test_encoded_dotdot_blocked(self):
        """URL-encoded '..' (%2e%2e) should be rejected after decoding."""
        store = make_credential_store()
        resp = forward_request("test_svc", "%2e%2e/etc/passwd", "GET", {}, None, "", store)
        assert resp.status_code == 400
        assert b"path traversal" in resp.data.lower()

    def test_mid_path_dotdot_blocked(self):
        """'foo/../bar' should be rejected."""
        store = make_credential_store()
        resp = forward_request("test_svc", "foo/../bar", "GET", {}, None, "", store)
        assert resp.status_code == 400
        assert b"path traversal" in resp.data.lower()

    @patch("server.proxy.requests.request")
    def test_normal_path_allowed(self, mock_request):
        """Normal paths without traversal should be forwarded."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.iter_content = MagicMock(return_value=[b'{"ok": true}'])
        mock_request.return_value = mock_response

        app = Flask(__name__)
        store = make_credential_store()
        with app.test_request_context():
            resp = forward_request("test_svc", "v1/users/123", "GET", {}, None, "", store)
            assert resp.status_code == 200


# =============================================================================
# Header filtering tests
# =============================================================================


class TestHeaderFiltering:
    """Tests for request and response header filtering."""

    def test_allowed_headers_pass(self):
        """Allowed headers should be forwarded."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "test-agent",
        }
        filtered = filter_request_headers(headers)
        assert "Content-Type" in filtered
        assert "Accept" in filtered
        assert "User-Agent" in filtered

    def test_auth_headers_stripped(self):
        """Auth and internal headers should NOT be forwarded."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret",
            "X-Session-Id": "abc123",
            "X-Auth-Key": "secret-key",
            "Cookie": "session=xyz",
            "Host": "localhost:8443",
        }
        filtered = filter_request_headers(headers)
        assert "Content-Type" in filtered
        assert "Authorization" not in filtered
        assert "X-Session-Id" not in filtered
        assert "X-Auth-Key" not in filtered
        assert "Cookie" not in filtered
        assert "Host" not in filtered

    def test_response_headers_filtered(self):
        """Excluded response headers should be stripped."""
        headers = {
            "Content-Type": "application/json",
            "X-Custom": "value",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
            "Keep-Alive": "timeout=5",
        }
        filtered = filter_response_headers(headers)
        assert "Content-Type" in filtered
        assert "X-Custom" in filtered
        assert "Connection" not in filtered
        assert "Transfer-Encoding" not in filtered
        assert "Keep-Alive" not in filtered


# =============================================================================
# Error handling tests
# =============================================================================


class TestErrorHandling:
    """Tests for proxy error handling."""

    def test_unknown_service_returns_404(self):
        """Requesting an unknown service should return 404."""
        store = make_credential_store()
        resp = forward_request("nonexistent", "path", "GET", {}, None, "", store)
        assert resp.status_code == 404
        assert b"unknown service" in resp.data.lower()

    @patch("server.proxy.requests.request")
    def test_upstream_timeout_returns_504(self, mock_request):
        """Upstream timeout should return 504."""
        import requests

        mock_request.side_effect = requests.exceptions.Timeout("timed out")

        store = make_credential_store()
        resp = forward_request("test_svc", "v1/slow", "GET", {}, None, "", store)
        assert resp.status_code == 504
        assert b"timeout" in resp.data.lower()

    @patch("server.proxy.requests.request")
    def test_connection_error_returns_502(self, mock_request):
        """Upstream connection error should return 502."""
        import requests

        mock_request.side_effect = requests.exceptions.ConnectionError("refused")

        store = make_credential_store()
        resp = forward_request("test_svc", "v1/down", "GET", {}, None, "", store)
        assert resp.status_code == 502
        assert b"connection" in resp.data.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
