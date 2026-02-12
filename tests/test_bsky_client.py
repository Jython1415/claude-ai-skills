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
    paginate,
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


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPaginate:
    def _mock_response(self, json_data, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        return resp

    @patch("bsky_client.requests.get")
    def test_single_page(self, mock_get):
        """Single page with no cursor returns all items."""
        mock_get.return_value = self._mock_response({"follows": [{"did": "did:plc:a"}, {"did": "did:plc:b"}]})
        result = paginate("app.bsky.graph.getFollows", {"actor": "did:plc:x"}, "follows")
        assert len(result) == 2
        mock_get.assert_called_once()

    @patch("bsky_client.requests.get")
    def test_multiple_pages(self, mock_get):
        """Follows cursor across pages until exhausted."""
        mock_get.side_effect = [
            self._mock_response({"follows": [{"did": "did:plc:a"}], "cursor": "page2"}),
            self._mock_response({"follows": [{"did": "did:plc:b"}], "cursor": "page3"}),
            self._mock_response({"follows": [{"did": "did:plc:c"}]}),
        ]
        result = paginate("app.bsky.graph.getFollows", {"actor": "did:plc:x"}, "follows")
        assert len(result) == 3
        assert mock_get.call_count == 3

    @patch("bsky_client.requests.get")
    def test_max_items_caps_results(self, mock_get):
        """max_items stops pagination early and truncates."""
        mock_get.side_effect = [
            self._mock_response({"follows": [{"did": f"did:plc:{i}"} for i in range(100)], "cursor": "page2"}),
            self._mock_response({"follows": [{"did": f"did:plc:{i + 100}"} for i in range(100)]}),
        ]
        result = paginate("app.bsky.graph.getFollows", {"actor": "did:plc:x"}, "follows", max_items=150)
        assert len(result) == 150
        assert mock_get.call_count == 2

    @patch("bsky_client.requests.get")
    def test_empty_page_stops(self, mock_get):
        """Empty result list stops pagination even with a cursor."""
        mock_get.side_effect = [
            self._mock_response({"follows": [{"did": "did:plc:a"}], "cursor": "page2"}),
            self._mock_response({"follows": [], "cursor": "page3"}),
        ]
        result = paginate("app.bsky.graph.getFollows", {"actor": "did:plc:x"}, "follows")
        assert len(result) == 1
        assert mock_get.call_count == 2

    @patch("bsky_client.requests.get")
    def test_cursor_passed_to_subsequent_requests(self, mock_get):
        """Cursor from response is passed as param to next request."""
        mock_get.side_effect = [
            self._mock_response({"follows": [{"did": "did:plc:a"}], "cursor": "abc123"}),
            self._mock_response({"follows": [{"did": "did:plc:b"}]}),
        ]
        paginate("app.bsky.graph.getFollows", {"actor": "did:plc:x"}, "follows")

        second_call_params = mock_get.call_args_list[1][1]["params"]
        assert second_call_params["cursor"] == "abc123"

    @patch("bsky_client.requests.get")
    def test_page_size_param(self, mock_get):
        """page_size is passed as the limit parameter."""
        mock_get.return_value = self._mock_response({"follows": []})
        paginate("app.bsky.graph.getFollows", {"actor": "did:plc:x"}, "follows", page_size=50)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["limit"] == 50
