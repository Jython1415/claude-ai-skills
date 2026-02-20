"""
Unit tests for service-specific endpoint filtering.

Tests the validation functions in server/service_filters.py that enforce
proxy-level endpoint restrictions (e.g., blocking Gmail send endpoints).
"""

import pytest

from server.service_filters import validate_gmail_endpoint, validate_proxy_request

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
    """Batch endpoint: only POST batch/gmail/v1 is allowed."""

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

    def test_bsky_passes_through(self):
        """Non-Gmail services should pass through unfiltered."""
        allowed, error = validate_proxy_request("bsky", "POST", "any/path/here")
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
