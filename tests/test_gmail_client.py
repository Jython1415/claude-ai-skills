"""Tests for the shared Gmail API client module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add skills/gmail to path so we can import gmail_client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "gmail"))

from gmail_client import (
    AuthRequiredError,
    api,
    create_draft,
    decode_body,
    extract_body,
    extract_headers,
    get_message,
    get_thread,
    paginate,
    search,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(json_data, status_code=200, content=b"{}"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    resp.content = content
    return resp


def _make_payload(*, mime_type="text/plain", body_data=None, headers=None, parts=None):
    """Build a minimal Gmail payload dict for testing."""
    payload = {"mimeType": mime_type, "headers": headers or []}
    if body_data is not None:
        payload["body"] = {"data": body_data}
    else:
        payload["body"] = {}
    if parts is not None:
        payload["parts"] = parts
    return payload


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    def test_raises_without_session_id(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.get("messages")

    def test_raises_without_proxy_url(self, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "test-session")
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.get("messages")

    def test_error_message_mentions_env_vars(self):
        err = AuthRequiredError()
        assert "SESSION_ID" in str(err)
        assert "PROXY_URL" in str(err)


# ---------------------------------------------------------------------------
# API GET
# ---------------------------------------------------------------------------


class TestApiGet:
    @patch("gmail_client.requests.get")
    def test_builds_correct_url(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "test-session")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_get.return_value = _mock_response({"messages": []})

        api.get("messages", {"maxResults": 10})

        call_url = mock_get.call_args[0][0]
        assert call_url == "https://proxy.example.com/proxy/gmail/gmail/v1/users/me/messages"

    @patch("gmail_client.requests.get")
    def test_sends_session_header(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "my-session-id")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_get.return_value = _mock_response({})

        api.get("profile")

        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["X-Session-Id"] == "my-session-id"

    @patch("gmail_client.requests.get")
    def test_passes_params(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.return_value = _mock_response({})

        api.get("messages", {"q": "is:unread", "maxResults": 5})

        call_params = mock_get.call_args[1]["params"]
        assert call_params == {"q": "is:unread", "maxResults": 5}

    @patch("gmail_client.requests.get")
    def test_custom_service_name(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        monkeypatch.setenv("GMAIL_SERVICE", "gmail_work")
        mock_get.return_value = _mock_response({})

        api.get("profile")

        call_url = mock_get.call_args[0][0]
        assert "/proxy/gmail_work/" in call_url

    @patch("gmail_client.requests.get")
    def test_returns_parsed_json(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.return_value = _mock_response({"emailAddress": "user@gmail.com"})

        result = api.get("profile")

        assert result == {"emailAddress": "user@gmail.com"}

    def test_raises_without_session(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.get("messages")


# ---------------------------------------------------------------------------
# API POST
# ---------------------------------------------------------------------------


class TestApiPost:
    @patch("gmail_client.requests.post")
    def test_builds_correct_url(self, mock_post, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_post.return_value = _mock_response({"id": "draft-1"})

        api.post("drafts", {"message": {"raw": "abc"}})

        call_url = mock_post.call_args[0][0]
        assert call_url == "https://proxy.example.com/proxy/gmail/gmail/v1/users/me/drafts"

    @patch("gmail_client.requests.post")
    def test_sends_json_body(self, mock_post, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_post.return_value = _mock_response({})

        body = {"addLabelIds": ["STARRED"]}
        api.post("messages/msg123/modify", body)

        call_json = mock_post.call_args[1]["json"]
        assert call_json == body

    def test_raises_without_session(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.post("drafts", {})


# ---------------------------------------------------------------------------
# API DELETE
# ---------------------------------------------------------------------------


class TestApiDelete:
    @patch("gmail_client.requests.delete")
    def test_builds_correct_url(self, mock_delete, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_delete.return_value = _mock_response({}, status_code=204, content=b"")

        api.delete("drafts/draft-1")

        call_url = mock_delete.call_args[0][0]
        assert call_url == "https://proxy.example.com/proxy/gmail/gmail/v1/users/me/drafts/draft-1"

    @patch("gmail_client.requests.delete")
    def test_handles_204_no_content(self, mock_delete, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_delete.return_value = _mock_response({}, status_code=204, content=b"")

        result = api.delete("drafts/draft-1")

        assert result == {}

    def test_raises_without_session(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.delete("drafts/draft-1")


# ---------------------------------------------------------------------------
# API PATCH
# ---------------------------------------------------------------------------


class TestApiPatch:
    @patch("gmail_client.requests.patch")
    def test_builds_correct_url(self, mock_patch, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_patch.return_value = _mock_response({"id": "label-1"})

        api.patch("labels/label-1", {"name": "Updated"})

        call_url = mock_patch.call_args[0][0]
        assert call_url == "https://proxy.example.com/proxy/gmail/gmail/v1/users/me/labels/label-1"

    def test_raises_without_session(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.patch("labels/label-1", {})


# ---------------------------------------------------------------------------
# API PUT
# ---------------------------------------------------------------------------


class TestApiPut:
    @patch("gmail_client.requests.put")
    def test_builds_correct_url(self, mock_put, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://proxy.example.com")
        mock_put.return_value = _mock_response({"id": "draft-1"})

        api.put("drafts/draft-1", {"message": {"raw": "abc"}})

        call_url = mock_put.call_args[0][0]
        assert call_url == "https://proxy.example.com/proxy/gmail/gmail/v1/users/me/drafts/draft-1"

    def test_raises_without_session(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.delenv("PROXY_URL", raising=False)

        with pytest.raises(AuthRequiredError):
            api.put("drafts/draft-1", {})


# ---------------------------------------------------------------------------
# decode_body
# ---------------------------------------------------------------------------


class TestDecodeBody:
    def test_decodes_base64url(self):
        import base64

        encoded = base64.urlsafe_b64encode(b"Hello, world!").decode()
        assert decode_body(encoded) == "Hello, world!"

    def test_handles_unicode(self):
        import base64

        text = "Caf\u00e9 \u2603"
        encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode()
        assert decode_body(encoded) == text

    def test_replaces_invalid_bytes(self):
        import base64

        raw = b"hello \xff\xfe world"
        encoded = base64.urlsafe_b64encode(raw).decode()
        result = decode_body(encoded)
        assert "hello" in result
        assert "world" in result


# ---------------------------------------------------------------------------
# extract_body
# ---------------------------------------------------------------------------


class TestExtractBody:
    def test_single_part_text_plain(self):
        import base64

        data = base64.urlsafe_b64encode(b"Plain text body").decode()
        payload = _make_payload(mime_type="text/plain", body_data=data)
        assert extract_body(payload) == "Plain text body"

    def test_single_part_text_html(self):
        import base64

        data = base64.urlsafe_b64encode(b"<p>HTML body</p>").decode()
        payload = _make_payload(mime_type="text/html", body_data=data)
        assert extract_body(payload) == "<p>HTML body</p>"

    def test_multipart_prefers_plain(self):
        import base64

        plain = base64.urlsafe_b64encode(b"Plain text").decode()
        html = base64.urlsafe_b64encode(b"<p>HTML</p>").decode()
        payload = _make_payload(
            mime_type="multipart/alternative",
            parts=[
                {"mimeType": "text/plain", "body": {"data": plain}},
                {"mimeType": "text/html", "body": {"data": html}},
            ],
        )
        assert extract_body(payload) == "Plain text"

    def test_multipart_falls_back_to_html(self):
        import base64

        html = base64.urlsafe_b64encode(b"<p>HTML only</p>").decode()
        payload = _make_payload(
            mime_type="multipart/alternative",
            parts=[
                {"mimeType": "text/html", "body": {"data": html}},
            ],
        )
        assert extract_body(payload) == "<p>HTML only</p>"

    def test_no_text_body(self):
        payload = _make_payload(
            mime_type="multipart/mixed",
            parts=[
                {"mimeType": "image/png", "body": {"data": "abc"}},
            ],
        )
        assert extract_body(payload) == "(no text body)"

    def test_nested_multipart(self):
        import base64

        plain = base64.urlsafe_b64encode(b"Nested plain").decode()
        payload = _make_payload(
            mime_type="multipart/mixed",
            parts=[
                {
                    "mimeType": "multipart/alternative",
                    "body": {},
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": plain}},
                    ],
                },
            ],
        )
        assert extract_body(payload) == "Nested plain"


# ---------------------------------------------------------------------------
# extract_headers
# ---------------------------------------------------------------------------


class TestExtractHeaders:
    def test_extracts_default_headers(self):
        payload = _make_payload(
            headers=[
                {"name": "From", "value": "alice@example.com"},
                {"name": "To", "value": "bob@example.com"},
                {"name": "Subject", "value": "Test"},
                {"name": "Date", "value": "Mon, 10 Feb 2026 10:00:00 +0000"},
                {"name": "X-Custom", "value": "should be ignored"},
            ]
        )
        headers = extract_headers(payload)
        assert headers == {
            "From": "alice@example.com",
            "To": "bob@example.com",
            "Subject": "Test",
            "Date": "Mon, 10 Feb 2026 10:00:00 +0000",
        }

    def test_custom_header_names(self):
        payload = _make_payload(
            headers=[
                {"name": "Message-ID", "value": "<abc@mail.gmail.com>"},
                {"name": "References", "value": "<ref1@mail.gmail.com>"},
                {"name": "From", "value": "alice@example.com"},
            ]
        )
        headers = extract_headers(payload, ["Message-ID", "References"])
        assert headers == {
            "Message-ID": "<abc@mail.gmail.com>",
            "References": "<ref1@mail.gmail.com>",
        }

    def test_case_insensitive_matching(self):
        """Gmail API returns Message-Id (lowercase d); callers request Message-ID."""
        payload = _make_payload(
            headers=[
                {"name": "Message-Id", "value": "<abc@mail.gmail.com>"},
                {"name": "references", "value": "<ref1@mail.gmail.com>"},
            ]
        )
        headers = extract_headers(payload, ["Message-ID", "References"])
        assert headers == {
            "Message-ID": "<abc@mail.gmail.com>",
            "References": "<ref1@mail.gmail.com>",
        }

    def test_missing_headers_omitted(self):
        payload = _make_payload(headers=[{"name": "From", "value": "alice@example.com"}])
        headers = extract_headers(payload)
        assert headers == {"From": "alice@example.com"}
        assert "To" not in headers

    def test_empty_headers(self):
        payload = _make_payload(headers=[])
        assert extract_headers(payload) == {}


# ---------------------------------------------------------------------------
# paginate
# ---------------------------------------------------------------------------


class TestPaginate:
    @patch("gmail_client.requests.get")
    def test_single_page(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.return_value = _mock_response({"messages": [{"id": "a"}, {"id": "b"}]})

        result = paginate("messages", {"q": "test"}, "messages")

        assert len(result) == 2
        mock_get.assert_called_once()

    @patch("gmail_client.requests.get")
    def test_multiple_pages(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.side_effect = [
            _mock_response({"messages": [{"id": "a"}], "nextPageToken": "page2"}),
            _mock_response({"messages": [{"id": "b"}], "nextPageToken": "page3"}),
            _mock_response({"messages": [{"id": "c"}]}),
        ]

        result = paginate("messages", {}, "messages")

        assert len(result) == 3
        assert mock_get.call_count == 3

    @patch("gmail_client.requests.get")
    def test_max_items_caps_results(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.side_effect = [
            _mock_response({"messages": [{"id": f"m{i}"} for i in range(100)], "nextPageToken": "p2"}),
            _mock_response({"messages": [{"id": f"m{i + 100}"} for i in range(100)]}),
        ]

        result = paginate("messages", {}, "messages", max_items=150)

        assert len(result) == 150

    @patch("gmail_client.requests.get")
    def test_page_token_passed(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.side_effect = [
            _mock_response({"messages": [{"id": "a"}], "nextPageToken": "tok123"}),
            _mock_response({"messages": [{"id": "b"}]}),
        ]

        paginate("messages", {}, "messages")

        second_call_params = mock_get.call_args_list[1][1]["params"]
        assert second_call_params["pageToken"] == "tok123"

    @patch("gmail_client.requests.get")
    def test_page_size_param(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.return_value = _mock_response({"messages": []})

        paginate("messages", {}, "messages", page_size=50)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["maxResults"] == 50

    @patch("gmail_client.requests.get")
    def test_empty_page_stops(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.side_effect = [
            _mock_response({"messages": [{"id": "a"}], "nextPageToken": "p2"}),
            _mock_response({"messages": [], "nextPageToken": "p3"}),
        ]

        result = paginate("messages", {}, "messages")

        assert len(result) == 1
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    @patch("gmail_client.requests.get")
    def test_search_returns_enriched_messages(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")

        # First call: list messages; second call: get metadata
        mock_get.side_effect = [
            _mock_response({"messages": [{"id": "msg1", "threadId": "t1"}]}),
            _mock_response(
                {
                    "id": "msg1",
                    "threadId": "t1",
                    "snippet": "Preview text",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "alice@example.com"},
                            {"name": "Subject", "value": "Hello"},
                        ]
                    },
                }
            ),
        ]

        results = search("from:alice", max_results=1)

        assert len(results) == 1
        assert results[0]["id"] == "msg1"
        assert results[0]["headers"]["From"] == "alice@example.com"
        assert results[0]["snippet"] == "Preview text"

    @patch("gmail_client.requests.get")
    def test_search_empty_results(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.return_value = _mock_response({"resultSizeEstimate": 0})

        results = search("nonexistent query")

        assert results == []

    @patch("gmail_client.requests.get")
    def test_search_caps_max_results(self, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_get.return_value = _mock_response({})

        search("test", max_results=1000)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["maxResults"] == 500


# ---------------------------------------------------------------------------
# get_message
# ---------------------------------------------------------------------------


class TestGetMessage:
    @patch("gmail_client.requests.get")
    def test_returns_decoded_message(self, mock_get, monkeypatch):
        import base64

        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        body_data = base64.urlsafe_b64encode(b"Hello!").decode()

        mock_get.return_value = _mock_response(
            {
                "id": "msg1",
                "threadId": "t1",
                "labelIds": ["INBOX"],
                "payload": {
                    "mimeType": "text/plain",
                    "body": {"data": body_data},
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "Subject", "value": "Test"},
                    ],
                },
            }
        )

        result = get_message("msg1")

        assert result["id"] == "msg1"
        assert result["body"] == "Hello!"
        assert result["headers"]["From"] == "alice@example.com"
        assert result["labelIds"] == ["INBOX"]


# ---------------------------------------------------------------------------
# get_thread
# ---------------------------------------------------------------------------


class TestGetThread:
    @patch("gmail_client.requests.get")
    def test_returns_decoded_thread(self, mock_get, monkeypatch):
        import base64

        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        body1 = base64.urlsafe_b64encode(b"First message").decode()
        body2 = base64.urlsafe_b64encode(b"Reply").decode()

        mock_get.return_value = _mock_response(
            {
                "id": "t1",
                "messages": [
                    {
                        "id": "msg1",
                        "threadId": "t1",
                        "labelIds": ["INBOX"],
                        "payload": {
                            "mimeType": "text/plain",
                            "body": {"data": body1},
                            "headers": [{"name": "From", "value": "alice@example.com"}],
                        },
                    },
                    {
                        "id": "msg2",
                        "threadId": "t1",
                        "labelIds": ["INBOX"],
                        "payload": {
                            "mimeType": "text/plain",
                            "body": {"data": body2},
                            "headers": [{"name": "From", "value": "bob@example.com"}],
                        },
                    },
                ],
            }
        )

        result = get_thread("t1")

        assert result["id"] == "t1"
        assert len(result["messages"]) == 2
        assert result["messages"][0]["body"] == "First message"
        assert result["messages"][1]["body"] == "Reply"


# ---------------------------------------------------------------------------
# create_draft
# ---------------------------------------------------------------------------


class TestCreateDraft:
    @patch("gmail_client.requests.post")
    def test_creates_standalone_draft(self, mock_post, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_post.return_value = _mock_response({"id": "draft-1"})

        result = create_draft("bob@example.com", "Hello", "Hi Bob!")

        assert result["id"] == "draft-1"
        call_json = mock_post.call_args[1]["json"]
        assert "raw" in call_json["message"]
        assert "threadId" not in call_json["message"]

    @patch("gmail_client.requests.get")
    @patch("gmail_client.requests.post")
    def test_creates_threaded_reply_draft(self, mock_post, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")

        # Mock the GET for fetching original message headers.
        # Gmail API returns "Message-Id" (lowercase 'd'), not "Message-ID".
        mock_get.return_value = _mock_response(
            {
                "id": "orig-msg",
                "payload": {
                    "headers": [
                        {"name": "Message-Id", "value": "<orig@mail.gmail.com>"},
                        {"name": "References", "value": "<earlier@mail.gmail.com>"},
                    ]
                },
            }
        )
        mock_post.return_value = _mock_response({"id": "draft-2"})

        result = create_draft(
            "bob@example.com",
            "Re: Hello",
            "Got it!",
            thread_id="t1",
            reply_to_msg_id="orig-msg",
        )

        assert result["id"] == "draft-2"
        call_json = mock_post.call_args[1]["json"]
        assert call_json["message"]["threadId"] == "t1"

        # Verify the raw MIME message contains threading headers
        import base64

        raw = call_json["message"]["raw"]
        decoded = base64.urlsafe_b64decode(raw).decode()
        assert "In-Reply-To: <orig@mail.gmail.com>" in decoded
        assert "References: <earlier@mail.gmail.com> <orig@mail.gmail.com>" in decoded

    @patch("gmail_client.requests.get")
    @patch("gmail_client.requests.post")
    def test_reply_without_existing_references(self, mock_post, mock_get, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")

        # Original message has no References header.
        # Gmail API returns "Message-Id" (lowercase 'd'), not "Message-ID".
        mock_get.return_value = _mock_response(
            {
                "id": "orig-msg",
                "payload": {
                    "headers": [
                        {"name": "Message-Id", "value": "<orig@mail.gmail.com>"},
                    ]
                },
            }
        )
        mock_post.return_value = _mock_response({"id": "draft-3"})

        create_draft(
            "bob@example.com",
            "Re: Hello",
            "Reply!",
            thread_id="t1",
            reply_to_msg_id="orig-msg",
        )

        import base64

        raw = mock_post.call_args[1]["json"]["message"]["raw"]
        decoded = base64.urlsafe_b64decode(raw).decode()
        assert "In-Reply-To: <orig@mail.gmail.com>" in decoded
        assert "References: <orig@mail.gmail.com>" in decoded

    @patch("gmail_client.requests.post")
    def test_thread_id_without_reply(self, mock_post, monkeypatch):
        """thread_id alone attaches to thread but doesn't add threading headers."""
        monkeypatch.setenv("SESSION_ID", "s")
        monkeypatch.setenv("PROXY_URL", "https://p")
        mock_post.return_value = _mock_response({"id": "draft-4"})

        create_draft("bob@example.com", "FYI", "Info", thread_id="t1")

        call_json = mock_post.call_args[1]["json"]
        assert call_json["message"]["threadId"] == "t1"
