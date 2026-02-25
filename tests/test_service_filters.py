"""
Unit tests for service-specific endpoint filtering.

Tests the validation functions in server/service_filters.py that enforce
proxy-level endpoint restrictions (e.g., blocking Gmail send endpoints).
"""

import json

import pytest

from server.service_filters import validate_bluesky_endpoint, validate_gmail_endpoint, validate_proxy_request

# =============================================================================
# Gmail: Send endpoints blocked
# =============================================================================


class TestGmailSendBlocked:
    """Both send endpoints should be blocked regardless of method."""

    def test_messages_send_post_blocked(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/send")
        assert allowed is False
        assert "send" in error.lower()

    def test_drafts_send_post_blocked(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/drafts/send")
        assert allowed is False
        assert "send" in error.lower()

    def test_messages_send_get_blocked(self):
        """GET on send endpoint should also be blocked."""
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/messages/send")
        assert allowed is False
        assert "send" in error.lower()

    def test_drafts_send_get_blocked(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/drafts/send")
        assert allowed is False
        assert "send" in error.lower()


# =============================================================================
# Gmail: Drafts allowed (except send)
# =============================================================================


class TestGmailDraftsAllowed:
    """Draft CRUD operations should be allowed."""

    def test_list_drafts(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/drafts")
        assert allowed is True
        assert error == ""

    def test_get_draft(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/drafts/abc123")
        assert allowed is True
        assert error == ""

    def test_create_draft(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/drafts")
        assert allowed is True
        assert error == ""

    def test_update_draft(self):
        allowed, error = validate_gmail_endpoint("PUT", "gmail/v1/users/me/drafts/abc123")
        assert allowed is True
        assert error == ""

    def test_delete_draft(self):
        allowed, error = validate_gmail_endpoint("DELETE", "gmail/v1/users/me/drafts/abc123")
        assert allowed is True
        assert error == ""


# =============================================================================
# Gmail: Labels allowed
# =============================================================================


class TestGmailLabelsAllowed:
    """Full label CRUD should be allowed."""

    def test_list_labels(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/labels")
        assert allowed is True
        assert error == ""

    def test_get_label(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/labels/Label_1")
        assert allowed is True
        assert error == ""

    def test_create_label(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/labels")
        assert allowed is True
        assert error == ""

    def test_update_label_put(self):
        allowed, error = validate_gmail_endpoint("PUT", "gmail/v1/users/me/labels/Label_1")
        assert allowed is True
        assert error == ""

    def test_update_label_patch(self):
        allowed, error = validate_gmail_endpoint("PATCH", "gmail/v1/users/me/labels/Label_1")
        assert allowed is True
        assert error == ""

    def test_delete_label(self):
        allowed, error = validate_gmail_endpoint("DELETE", "gmail/v1/users/me/labels/Label_1")
        assert allowed is True
        assert error == ""


# =============================================================================
# Gmail: Modify allowed
# =============================================================================


class TestGmailModifyAllowed:
    """Message and thread modify operations should be allowed."""

    def test_message_modify(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/abc123/modify")
        assert allowed is True
        assert error == ""

    def test_thread_modify(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/threads/abc123/modify")
        assert allowed is True
        assert error == ""

    def test_batch_modify(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/batchModify")
        assert allowed is True
        assert error == ""


# =============================================================================
# Gmail: Trash allowed
# =============================================================================


class TestGmailTrashAllowed:
    """Trash and untrash operations should be allowed."""

    def test_message_trash(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/abc123/trash")
        assert allowed is True
        assert error == ""

    def test_message_untrash(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/abc123/untrash")
        assert allowed is True
        assert error == ""

    def test_thread_trash(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/threads/abc123/trash")
        assert allowed is True
        assert error == ""

    def test_thread_untrash(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/threads/abc123/untrash")
        assert allowed is True
        assert error == ""


# =============================================================================
# Gmail: Read operations allowed
# =============================================================================


class TestGmailReadAllowed:
    """GET on standard resources should be allowed."""

    def test_list_messages(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/messages")
        assert allowed is True
        assert error == ""

    def test_get_message(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/messages/abc123")
        assert allowed is True
        assert error == ""

    def test_get_attachment(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/messages/abc123/attachments/att456")
        assert allowed is True
        assert error == ""

    def test_list_threads(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/threads")
        assert allowed is True
        assert error == ""

    def test_get_thread(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/threads/abc123")
        assert allowed is True
        assert error == ""

    def test_get_profile(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/profile")
        assert allowed is True
        assert error == ""

    def test_list_history(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/history")
        assert allowed is True
        assert error == ""


# =============================================================================
# Gmail: Permanent delete blocked
# =============================================================================


class TestGmailDeleteBlocked:
    """Permanent deletion of messages/threads should be blocked."""

    def test_delete_message(self):
        allowed, error = validate_gmail_endpoint("DELETE", "gmail/v1/users/me/messages/abc123")
        assert allowed is False
        assert "permanent deletion" in error.lower()

    def test_delete_thread(self):
        allowed, error = validate_gmail_endpoint("DELETE", "gmail/v1/users/me/threads/abc123")
        assert allowed is False
        assert "permanent deletion" in error.lower()

    def test_batch_delete(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/batchDelete")
        assert allowed is False
        assert "batch deletion" in error.lower()


# =============================================================================
# Gmail: Insert and import blocked
# =============================================================================


class TestGmailInsertImportBlocked:
    """POST to bare messages (insert) and messages/import should be blocked."""

    def test_message_insert(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages")
        assert allowed is False
        assert "insert" in error.lower()

    def test_message_import(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/messages/import")
        assert allowed is False
        assert "import" in error.lower()

    def test_message_import_get(self):
        """GET on import path should also be blocked."""
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/messages/import")
        assert allowed is False
        assert "import" in error.lower()


# =============================================================================
# Gmail: Settings blocked
# =============================================================================


class TestGmailSettingsBlocked:
    """All settings sub-endpoints should be blocked."""

    def test_settings_filters(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/settings/filters")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_forwarding(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/settings/forwardingAddresses")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_delegates(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/settings/delegates")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_auto_forwarding(self):
        allowed, error = validate_gmail_endpoint("PUT", "gmail/v1/users/me/settings/autoForwarding")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_imap(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/settings/imap")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_pop(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/settings/pop")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_vacation(self):
        allowed, error = validate_gmail_endpoint("PUT", "gmail/v1/users/me/settings/vacation")
        assert allowed is False
        assert "settings" in error.lower()

    def test_create_settings_filter(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/settings/filters")
        assert allowed is False
        assert "settings" in error.lower()

    def test_settings_sendAs(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/settings/sendAs")
        assert allowed is False
        assert "settings" in error.lower()


# =============================================================================
# Gmail: Edge cases
# =============================================================================


class TestGmailEdgeCases:
    """Edge cases: malformed paths, normalization, method casing."""

    def test_invalid_path_no_prefix(self):
        allowed, error = validate_gmail_endpoint("GET", "v1/users/me/messages")
        assert allowed is False
        assert "invalid" in error.lower()

    def test_invalid_path_no_resource(self):
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/")
        assert allowed is False

    def test_invalid_path_empty(self):
        allowed, error = validate_gmail_endpoint("GET", "")
        assert allowed is False

    def test_method_case_insensitive(self):
        """Method should be normalized to uppercase."""
        allowed, error = validate_gmail_endpoint("get", "gmail/v1/users/me/messages")
        assert allowed is True
        assert error == ""

    def test_method_mixed_case(self):
        allowed, error = validate_gmail_endpoint("Post", "gmail/v1/users/me/messages/send")
        assert allowed is False
        assert "send" in error.lower()

    def test_different_user_id(self):
        """Should work with any userId, not just 'me'."""
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/user@example.com/messages")
        assert allowed is True
        assert error == ""

    def test_unknown_resource_blocked(self):
        """Unknown resources should be default-denied."""
        allowed, error = validate_gmail_endpoint("GET", "gmail/v1/users/me/unknownResource")
        assert allowed is False
        assert "allowlist" in error.lower()

    def test_post_to_unknown_resource_blocked(self):
        allowed, error = validate_gmail_endpoint("POST", "gmail/v1/users/me/unknownResource")
        assert allowed is False
        assert "allowlist" in error.lower()


# =============================================================================
# Gmail: Batch endpoint filtering
# =============================================================================


class TestServiceFilterBatch:
    """Batch endpoint: only POST batch/gmail/v1 is allowed, with GET-only sub-requests."""

    # -- Method checks --

    def test_post_batch_endpoint_allowed(self):
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1")
        assert allowed is True
        assert error == ""

    def test_get_batch_endpoint_blocked(self):
        """GET on the batch endpoint is not allowed — only POST."""
        allowed, error = validate_gmail_endpoint("GET", "batch/gmail/v1")
        assert allowed is False

    def test_post_batch_wrong_version_blocked(self):
        """batch/gmail/v2 is not the correct path — should be blocked."""
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v2")
        assert allowed is False

    def test_put_batch_endpoint_blocked(self):
        """Only POST is permitted; PUT should be blocked."""
        allowed, error = validate_gmail_endpoint("PUT", "batch/gmail/v1")
        assert allowed is False

    def test_delete_batch_endpoint_blocked(self):
        """DELETE on the batch endpoint should be blocked."""
        allowed, error = validate_gmail_endpoint("DELETE", "batch/gmail/v1")
        assert allowed is False

    # -- Body validation --

    def test_batch_get_subrequests_allowed(self):
        """Batch body containing only GET sub-requests should be allowed."""
        body = (
            "--batch_abc\r\n"
            "Content-Type: application/http\r\n"
            "Content-ID: <item0>\r\n"
            "\r\n"
            "GET /gmail/v1/users/me/messages/abc123?format=metadata HTTP/1.1\r\n"
            "\r\n"
            "--batch_abc\r\n"
            "Content-Type: application/http\r\n"
            "Content-ID: <item1>\r\n"
            "\r\n"
            "GET /gmail/v1/users/me/messages/def456?format=metadata HTTP/1.1\r\n"
            "\r\n"
            "--batch_abc--"
        )
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1", body)
        assert allowed is True
        assert error == ""

    def test_batch_post_subrequest_blocked(self):
        """Batch body with POST sub-request (e.g., send) should be blocked."""
        body = (
            "--batch_abc\r\n"
            "Content-Type: application/http\r\n"
            "Content-ID: <item0>\r\n"
            "\r\n"
            "POST /gmail/v1/users/me/messages/send HTTP/1.1\r\n"
            "\r\n"
            "--batch_abc--"
        )
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1", body)
        assert allowed is False
        assert "POST" in error

    def test_batch_delete_subrequest_blocked(self):
        """Batch body with DELETE sub-request should be blocked."""
        body = (
            "--batch_abc\r\n"
            "Content-Type: application/http\r\n"
            "Content-ID: <item0>\r\n"
            "\r\n"
            "DELETE /gmail/v1/users/me/messages/abc123 HTTP/1.1\r\n"
            "\r\n"
            "--batch_abc--"
        )
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1", body)
        assert allowed is False
        assert "DELETE" in error

    def test_batch_mixed_methods_blocked(self):
        """If any sub-request is not GET, the whole batch is blocked."""
        body = (
            "--batch_abc\r\n"
            "Content-Type: application/http\r\n"
            "Content-ID: <item0>\r\n"
            "\r\n"
            "GET /gmail/v1/users/me/messages/abc123 HTTP/1.1\r\n"
            "\r\n"
            "--batch_abc\r\n"
            "Content-Type: application/http\r\n"
            "Content-ID: <item1>\r\n"
            "\r\n"
            "POST /gmail/v1/users/me/messages/send HTTP/1.1\r\n"
            "\r\n"
            "--batch_abc--"
        )
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1", body)
        assert allowed is False
        assert "POST" in error

    def test_batch_empty_body_allowed(self):
        """Empty body is allowed (no sub-requests to validate)."""
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1", b"")
        assert allowed is True
        assert error == ""

    def test_batch_bytes_body_validated(self):
        """Body can be bytes (as received from Flask request.get_data())."""
        body = (
            b"--batch_abc\r\n"
            b"Content-Type: application/http\r\n"
            b"Content-ID: <item0>\r\n"
            b"\r\n"
            b"PUT /gmail/v1/users/me/settings/vacation HTTP/1.1\r\n"
            b"\r\n"
            b"--batch_abc--"
        )
        allowed, error = validate_gmail_endpoint("POST", "batch/gmail/v1", body)
        assert allowed is False
        assert "PUT" in error

    # -- Dispatcher integration --

    def test_batch_endpoint_via_gmail_service_dispatcher(self):
        """validate_proxy_request should allow POST batch/gmail/v1 for gmail service."""
        allowed, error = validate_proxy_request("gmail", "POST", "batch/gmail/v1")
        assert allowed is True
        assert error == ""

    def test_batch_endpoint_via_gmail_work_service_dispatcher(self):
        """Gmail variant services should also allow the batch endpoint."""
        allowed, error = validate_proxy_request("gmail_work", "POST", "batch/gmail/v1")
        assert allowed is True
        assert error == ""

    def test_batch_body_validated_via_dispatcher(self):
        """Body validation works through the dispatcher."""
        body = (
            "--b\r\nContent-Type: application/http\r\n\r\nPOST /gmail/v1/users/me/messages/send HTTP/1.1\r\n\r\n--b--"
        )
        allowed, error = validate_proxy_request("gmail", "POST", "batch/gmail/v1", body)
        assert allowed is False
        assert "POST" in error


# =============================================================================
# Dispatcher: validate_proxy_request
# =============================================================================


class TestValidateProxyRequest:
    """Tests for the service dispatcher."""

    def test_gmail_filtered(self):
        """Gmail service should go through the filter."""
        allowed, error = validate_proxy_request("gmail", "POST", "gmail/v1/users/me/messages/send")
        assert allowed is False
        assert "send" in error.lower()

    def test_gmail_allowed(self):
        allowed, error = validate_proxy_request("gmail", "GET", "gmail/v1/users/me/messages")
        assert allowed is True
        assert error == ""

    def test_gmail_work_filtered(self):
        """gmail_work variant should also be filtered."""
        allowed, error = validate_proxy_request("gmail_work", "POST", "gmail/v1/users/me/messages/send")
        assert allowed is False
        assert "send" in error.lower()

    def test_gmail_personal_filtered(self):
        allowed, error = validate_proxy_request("gmail_personal", "GET", "gmail/v1/users/me/settings/filters")
        assert allowed is False
        assert "settings" in error.lower()

    def test_bsky_read_passes_through(self):
        """Bsky read endpoints pass through the filter."""
        allowed, error = validate_proxy_request("bsky", "GET", "app.bsky.feed.getTimeline")
        assert allowed is True
        assert error == ""

    def test_github_api_passes_through(self):
        allowed, error = validate_proxy_request("github_api", "DELETE", "repos/user/repo")
        assert allowed is True
        assert error == ""

    def test_unknown_service_passes_through(self):
        allowed, error = validate_proxy_request("custom_svc", "POST", "some/endpoint")
        assert allowed is True
        assert error == ""


# =============================================================================
# Bluesky: Blocked collections (post, repost, threadgate, generator)
# =============================================================================


def _make_create_body(collection: str) -> bytes:
    """Build a minimal createRecord body for a given collection."""
    return json.dumps({"repo": "did:plc:test123", "collection": collection, "record": {}}).encode()


class TestBskyBlockedCollections:
    """createRecord / putRecord with blocked collections should be denied."""

    def test_create_post_blocked(self):
        body = _make_create_body("app.bsky.feed.post")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "app.bsky.feed.post" in error

    def test_create_repost_blocked(self):
        body = _make_create_body("app.bsky.feed.repost")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "app.bsky.feed.repost" in error

    def test_create_threadgate_blocked(self):
        body = _make_create_body("app.bsky.feed.threadgate")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "app.bsky.feed.threadgate" in error

    def test_create_generator_blocked(self):
        body = _make_create_body("app.bsky.feed.generator")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "app.bsky.feed.generator" in error

    def test_put_post_blocked(self):
        """putRecord with blocked collection is also denied."""
        body = _make_create_body("app.bsky.feed.post")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.putRecord", body)
        assert allowed is False
        assert "app.bsky.feed.post" in error

    def test_put_repost_blocked(self):
        body = _make_create_body("app.bsky.feed.repost")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.putRecord", body)
        assert allowed is False
        assert "app.bsky.feed.repost" in error


# =============================================================================
# Bluesky: Allowed write collections (like, follow, block, mute, listitem)
# =============================================================================


class TestBskyAllowedWriteCollections:
    """createRecord / putRecord with allowed collections should pass."""

    def test_create_like_allowed(self):
        body = _make_create_body("app.bsky.feed.like")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is True
        assert error == ""

    def test_create_follow_allowed(self):
        body = _make_create_body("app.bsky.graph.follow")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is True
        assert error == ""

    def test_create_block_allowed(self):
        body = _make_create_body("app.bsky.graph.block")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is True
        assert error == ""

    def test_create_listitem_allowed(self):
        body = _make_create_body("app.bsky.graph.listitem")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is True
        assert error == ""

    def test_put_like_allowed(self):
        body = _make_create_body("app.bsky.feed.like")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.putRecord", body)
        assert allowed is True
        assert error == ""


# =============================================================================
# Bluesky: deleteRecord always allowed
# =============================================================================


class TestBskyDeleteAllowed:
    """deleteRecord is allowed for any collection (content removal is safe)."""

    def test_delete_post_record_allowed(self):
        """Deleting a post record (e.g., undoing a post) is allowed."""
        body = json.dumps({"repo": "did:plc:test123", "collection": "app.bsky.feed.post", "rkey": "3abc123"}).encode()
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.deleteRecord", body)
        assert allowed is True
        assert error == ""

    def test_delete_like_allowed(self):
        body = json.dumps({"repo": "did:plc:test123", "collection": "app.bsky.feed.like", "rkey": "3abc123"}).encode()
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.deleteRecord", body)
        assert allowed is True
        assert error == ""


# =============================================================================
# Bluesky: applyWrites blocked entirely
# =============================================================================


class TestBskyApplyWritesBlocked:
    """applyWrites is blocked regardless of body contents."""

    def test_apply_writes_no_body_blocked(self):
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.applyWrites")
        assert allowed is False
        assert "applyWrites" in error

    def test_apply_writes_with_body_blocked(self):
        body = json.dumps({"repo": "did:plc:test123", "writes": []}).encode()
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.applyWrites", body)
        assert allowed is False
        assert "applyWrites" in error


# =============================================================================
# Bluesky: Read and other write endpoints allowed
# =============================================================================


class TestBskyOtherEndpointsAllowed:
    """Reads and non-record-creation write endpoints should pass through."""

    def test_get_timeline_allowed(self):
        allowed, error = validate_bluesky_endpoint("GET", "app.bsky.feed.getTimeline")
        assert allowed is True
        assert error == ""

    def test_get_notifications_allowed(self):
        allowed, error = validate_bluesky_endpoint("GET", "app.bsky.notification.listNotifications")
        assert allowed is True
        assert error == ""

    def test_mute_actor_allowed(self):
        allowed, error = validate_bluesky_endpoint("POST", "app.bsky.graph.muteActor")
        assert allowed is True
        assert error == ""

    def test_unmute_actor_allowed(self):
        allowed, error = validate_bluesky_endpoint("POST", "app.bsky.graph.unmuteActor")
        assert allowed is True
        assert error == ""

    def test_update_seen_allowed(self):
        allowed, error = validate_bluesky_endpoint("POST", "app.bsky.notification.updateSeen")
        assert allowed is True
        assert error == ""

    def test_put_preferences_allowed(self):
        allowed, error = validate_bluesky_endpoint("POST", "app.bsky.actor.putPreferences")
        assert allowed is True
        assert error == ""

    def test_upload_blob_allowed(self):
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.uploadBlob")
        assert allowed is True
        assert error == ""


# =============================================================================
# Bluesky: Edge cases (malformed body, missing collection)
# =============================================================================


class TestBskyEdgeCases:
    """Edge cases for createRecord / putRecord body inspection."""

    def test_create_record_no_body_denied(self):
        """Missing body cannot be inspected — fail safe."""
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord")
        assert allowed is False
        assert "could not determine collection" in error

    def test_create_record_empty_body_denied(self):
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", b"")
        assert allowed is False
        assert "could not determine collection" in error

    def test_create_record_invalid_json_denied(self):
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", b"not json")
        assert allowed is False
        assert "could not determine collection" in error

    def test_create_record_no_collection_field_denied(self):
        body = json.dumps({"repo": "did:plc:test123", "record": {}}).encode()
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "could not determine collection" in error

    def test_create_record_unknown_collection_denied(self):
        """Unknown collections are denied by default (conservative)."""
        body = _make_create_body("app.bsky.some.unknownType")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "Unknown collection" in error

    def test_create_record_bytes_body_parsed(self):
        """Body as bytes (from Flask request.get_data()) is parsed correctly."""
        body = json.dumps({"repo": "did:plc:test123", "collection": "app.bsky.feed.like", "record": {}}).encode("utf-8")
        allowed, error = validate_bluesky_endpoint("POST", "com.atproto.repo.createRecord", body)
        assert allowed is True
        assert error == ""


# =============================================================================
# Bluesky: Dispatcher integration
# =============================================================================


class TestBskyDispatcherIntegration:
    """validate_proxy_request routes bsky to the Bluesky filter."""

    def test_bsky_create_post_blocked_via_dispatcher(self):
        body = _make_create_body("app.bsky.feed.post")
        allowed, error = validate_proxy_request("bsky", "POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "app.bsky.feed.post" in error

    def test_bsky_create_like_allowed_via_dispatcher(self):
        body = _make_create_body("app.bsky.feed.like")
        allowed, error = validate_proxy_request("bsky", "POST", "com.atproto.repo.createRecord", body)
        assert allowed is True
        assert error == ""

    def test_bsky_apply_writes_blocked_via_dispatcher(self):
        allowed, error = validate_proxy_request("bsky", "POST", "com.atproto.repo.applyWrites")
        assert allowed is False

    def test_bsky_read_allowed_via_dispatcher(self):
        allowed, error = validate_proxy_request("bsky", "GET", "app.bsky.feed.getTimeline")
        assert allowed is True
        assert error == ""

    def test_bsky_variant_service_also_filtered(self):
        """bsky_personal / bsky_work variants should also be filtered."""
        body = _make_create_body("app.bsky.feed.post")
        allowed, error = validate_proxy_request("bsky_personal", "POST", "com.atproto.repo.createRecord", body)
        assert allowed is False
        assert "app.bsky.feed.post" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
