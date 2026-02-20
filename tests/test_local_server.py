"""Tests for the local MCP server's test_proxy tool."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add mcp/ directory to path so we can import local_server
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from local_server import _load_proxy_config, _test_proxy_impl


class TestLoadProxyConfig:
    """Tests for _load_proxy_config helper."""

    def test_loads_key_and_default_port(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PROXY_SECRET_KEY=test-secret-key\n")

        with patch("local_server._PROJECT_DIR", tmp_path):
            base_url, key = _load_proxy_config()

        assert base_url == "http://localhost:8443"
        assert key == "test-secret-key"

    def test_loads_custom_port(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PROXY_SECRET_KEY=key\nPORT=9999\n")

        with patch("local_server._PROJECT_DIR", tmp_path):
            base_url, key = _load_proxy_config()

        assert base_url == "http://localhost:9999"

    def test_raises_on_missing_env(self, tmp_path):
        with patch("local_server._PROJECT_DIR", tmp_path):
            with pytest.raises(RuntimeError, match=".env not found"):
                _load_proxy_config()

    def test_raises_on_missing_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("PORT=8443\n")

        with patch("local_server._PROJECT_DIR", tmp_path):
            with pytest.raises(RuntimeError, match="PROXY_SECRET_KEY not set"):
                _load_proxy_config()


class TestTestProxy:
    """Tests for the test_proxy MCP tool."""

    def _mock_response(self, status_code=200, json_data=None, text="", content_type="application/json"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"content-type": content_type}
        resp.json.return_value = json_data or {}
        resp.text = text or json.dumps(json_data or {})
        return resp

    @patch("local_server.requests.request")
    @patch("local_server._load_proxy_config")
    def test_get_with_admin_key(self, mock_config, mock_request):
        """GET requests send X-Auth-Key header by default."""
        mock_config.return_value = ("http://localhost:8443", "secret")
        mock_request.return_value = self._mock_response(json_data={"status": "healthy"})

        result = _test_proxy_impl("GET", "/health")

        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["X-Auth-Key"] == "secret"
        assert call_kwargs["url"] == "http://localhost:8443/health"
        assert "200" in result

    @patch("local_server.requests.request")
    @patch("local_server._load_proxy_config")
    def test_get_with_session_id(self, mock_config, mock_request):
        """When session_id is provided, sends X-Session-Id instead of X-Auth-Key."""
        mock_config.return_value = ("http://localhost:8443", "secret")
        mock_request.return_value = self._mock_response(json_data={"feed": []})

        _test_proxy_impl("GET", "/proxy/bsky/app.bsky.feed.getTimeline", session_id="sess-123")

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["X-Session-Id"] == "sess-123"
        assert "X-Auth-Key" not in call_kwargs["headers"]

    @patch("local_server.requests.request")
    @patch("local_server._load_proxy_config")
    def test_post_with_json_body(self, mock_config, mock_request):
        """POST requests forward JSON body."""
        mock_config.return_value = ("http://localhost:8443", "secret")
        mock_request.return_value = self._mock_response(json_data={"session_id": "new-sess"})

        _test_proxy_impl("POST", "/sessions", body='{"services": ["bsky"], "ttl_minutes": 30}')

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["json"] == {"services": ["bsky"], "ttl_minutes": 30}
        assert call_kwargs["method"] == "POST"

    @patch("local_server._load_proxy_config")
    def test_invalid_json_body(self, mock_config):
        """Invalid JSON body returns error."""
        mock_config.return_value = ("http://localhost:8443", "secret")

        result = _test_proxy_impl("POST", "/sessions", body="not json")

        assert "Invalid JSON body" in result

    @patch("local_server.requests.request")
    @patch("local_server._load_proxy_config")
    def test_connection_error(self, mock_config, mock_request):
        """Connection error returns helpful message."""
        import requests as req

        mock_config.return_value = ("http://localhost:8443", "secret")
        mock_request.side_effect = req.exceptions.ConnectionError("refused")

        result = _test_proxy_impl("GET", "/health")

        assert "Could not connect" in result
        assert "service_status" in result

    @patch("local_server._load_proxy_config")
    def test_missing_env(self, mock_config):
        """Missing .env returns error."""
        mock_config.side_effect = RuntimeError(".env not found at /fake/.env")

        result = _test_proxy_impl("GET", "/health")

        assert ".env not found" in result

    @patch("local_server.requests.request")
    @patch("local_server._load_proxy_config")
    def test_non_json_response(self, mock_config, mock_request):
        """Non-JSON responses return raw text."""
        mock_config.return_value = ("http://localhost:8443", "secret")
        mock_request.return_value = self._mock_response(
            status_code=404,
            text="Not Found",
            content_type="text/plain",
        )

        result = _test_proxy_impl("GET", "/nonexistent")

        assert "404" in result
        assert "Not Found" in result
