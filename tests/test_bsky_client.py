"""Tests for the shared Bluesky API client module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add skills/bluesky to path so we can import bsky_client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "bluesky"))

from bsky_client import (
    AuthRequiredError,
    _classify,
    api,
    resolve_did_to_handle,
    resolve_handle_to_did,
    url_to_at_uri,
)

# ---------------------------------------------------------------------------
# Endpoint classification
# ---------------------------------------------------------------------------


class TestClassify:
    def test_public_only_endpoints(self):
        assert _classify("app.bsky.actor.getProfile") == "public_only"
        assert _classify("app.bsky.feed.searchPosts") == "public_only"
        assert _classify("com.atproto.identity.resolveHandle") == "public_only"
        assert _classify("app.bsky.unspecced.getTrendingTopics") == "public_only"
        assert _classify("app.bsky.feed.getPosts") == "public_only"
        assert _classify("app.bsky.feed.getPostThread") == "public_only"
        assert _classify("app.bsky.feed.getAuthorFeed") == "public_only"
        assert _classify("app.bsky.actor.searchActors") == "public_only"

    def test_auth_preferred_endpoints(self):
        assert _classify("app.bsky.graph.getKnownFollowers") == "auth_preferred"

    def test_auth_required_for_write_endpoints(self):
        assert _classify("com.atproto.repo.createRecord") == "auth_required"
        assert _classify("com.atproto.repo.deleteRecord") == "auth_required"

    def test_auth_required_for_private_read_endpoints(self):
        assert _classify("app.bsky.feed.getTimeline") == "auth_required"
        assert _classify("app.bsky.notification.listNotifications") == "auth_required"

    def test_unknown_endpoint_defaults_to_auth_required(self):
        assert _classify("com.example.unknown.endpoint") == "auth_required"


# ---------------------------------------------------------------------------
# API routing (GET)
# ---------------------------------------------------------------------------


class TestApiGet:
    def _mock_response(self, json_data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        return resp

    @patch("bsky_client.requests.get")
    def test_public_only_uses_public_api(self, mock_get, monkeypatch):
        """Public-only endpoints always use the public API, even with session."""
        monkeypatch.setenv("SESSION_ID", "test-session")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_get.return_value = self._mock_response({"did": "did:plc:abc"})

        result = api.get("com.atproto.identity.resolveHandle", {"handle": "bsky.app"})

        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert call_url.startswith("https://public.api.bsky.app/xrpc/")
        assert result == {"did": "did:plc:abc"}

    @patch("bsky_client.requests.get")
    def test_public_only_works_without_session(self, mock_get, monkeypatch):
        """Public-only endpoints work fine without session env vars."""
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)
        mock_get.return_value = self._mock_response({"handle": "bsky.app"})

        result = api.get("app.bsky.actor.getProfile", {"actor": "bsky.app"})

        assert result == {"handle": "bsky.app"}
        call_url = mock_get.call_args[0][0]
        assert "public.api.bsky.app" in call_url

    @patch("bsky_client.requests.get")
    def test_auth_preferred_uses_proxy_with_session(self, mock_get, monkeypatch):
        """Auth-preferred endpoints use proxy when session is available."""
        monkeypatch.setenv("SESSION_ID", "test-session")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_get.return_value = self._mock_response({"followers": []})

        api.get("app.bsky.graph.getKnownFollowers", {"actor": "bsky.app"})

        call_url = mock_get.call_args[0][0]
        assert call_url.startswith("https://proxy.example.com/proxy/bsky/")
        headers = mock_get.call_args[1].get("headers", {})
        assert headers.get("X-Session-Id") == "test-session"

    def test_auth_preferred_raises_without_session(self, monkeypatch):
        """Auth-preferred endpoints raise AuthRequiredError without session."""
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError) as exc_info:
            api.get("app.bsky.graph.getKnownFollowers", {"actor": "bsky.app"})
        assert "getKnownFollowers" in str(exc_info.value)

    @patch("bsky_client.requests.get")
    def test_auth_required_uses_proxy_with_session(self, mock_get, monkeypatch):
        """Auth-required endpoints use proxy when session is available."""
        monkeypatch.setenv("SESSION_ID", "test-session")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_get.return_value = self._mock_response({"feed": []})

        api.get("app.bsky.feed.getTimeline")

        call_url = mock_get.call_args[0][0]
        assert "proxy.example.com" in call_url
        assert "getTimeline" in call_url

    def test_auth_required_raises_without_session(self, monkeypatch):
        """Auth-required endpoints raise AuthRequiredError without session."""
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.get("app.bsky.feed.getTimeline")

    def test_unknown_endpoint_raises_without_session(self, monkeypatch):
        """Unknown endpoints default to auth_required (fail-safe)."""
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.get("com.example.unknown")


# ---------------------------------------------------------------------------
# API routing (POST)
# ---------------------------------------------------------------------------


class TestApiPost:
    def _mock_response(self, json_data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        return resp

    @patch("bsky_client.requests.post")
    def test_post_uses_proxy(self, mock_post, monkeypatch):
        """POST requests always go through the proxy."""
        monkeypatch.setenv("SESSION_ID", "test-session")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_post.return_value = self._mock_response({"uri": "at://..."})

        result = api.post("com.atproto.repo.createRecord", {"repo": "did:plc:abc"})

        call_url = mock_post.call_args[0][0]
        assert "proxy.example.com" in call_url
        assert result == {"uri": "at://..."}

    def test_post_raises_without_session(self, monkeypatch):
        """POST always requires a session."""
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.post("com.atproto.repo.createRecord", {"repo": "did:plc:abc"})


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestResolveHandleToDid:
    @patch("bsky_client.requests.get")
    def test_resolves_handle(self, mock_get):
        resp = MagicMock()
        resp.json.return_value = {"did": "did:plc:abc123"}
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp

        result = resolve_handle_to_did("bsky.app")

        assert result == "did:plc:abc123"
        call_url = mock_get.call_args[0][0]
        assert "resolveHandle" in call_url


class TestResolveDidToHandle:
    @patch("bsky_client.requests.get")
    def test_resolves_did(self, mock_get):
        resp = MagicMock()
        resp.json.return_value = {"handle": "bsky.app"}
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp

        result = resolve_did_to_handle("did:plc:abc123")

        assert result == "bsky.app"

    @patch("bsky_client.requests.get")
    def test_returns_none_on_failure(self, mock_get):
        import requests as req

        mock_get.side_effect = req.exceptions.ConnectionError("fail")

        result = resolve_did_to_handle("did:plc:nonexistent")

        assert result is None


class TestUrlToAtUri:
    @patch("bsky_client.requests.get")
    def test_converts_handle_url(self, mock_get):
        resp = MagicMock()
        resp.json.return_value = {"did": "did:plc:abc123"}
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp

        result = url_to_at_uri("https://bsky.app/profile/bsky.app/post/3abc123")

        assert result == "at://did:plc:abc123/app.bsky.feed.post/3abc123"

    def test_converts_did_url(self):
        """DID URLs don't need handle resolution."""
        result = url_to_at_uri("https://bsky.app/profile/did:plc:abc123/post/3xyz789")

        assert result == "at://did:plc:abc123/app.bsky.feed.post/3xyz789"

    def test_rejects_invalid_url(self):
        with pytest.raises(ValueError, match="Invalid bsky.app post URL"):
            url_to_at_uri("https://example.com/not-a-bsky-url")

    def test_strips_query_and_fragment(self):
        """URL with query params and fragment should still match."""
        result = url_to_at_uri("https://bsky.app/profile/did:plc:abc/post/3xyz?foo=bar#section")

        assert result == "at://did:plc:abc/app.bsky.feed.post/3xyz"
