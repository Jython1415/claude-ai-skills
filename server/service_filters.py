"""
Service-specific endpoint filtering for the credential proxy.

Validates proxy requests against per-service allowlists/blocklists before
forwarding to upstream APIs. This provides defense-in-depth beyond OAuth
scopes — for example, blocking Gmail send endpoints even though the
gmail.modify scope technically permits sending.

All validation functions return (is_allowed: bool, error_message: str) tuples.
When is_allowed is True, error_message is an empty string.
"""

import re

# Gmail API path prefix: gmail/v1/users/{userId}/
# After stripping this prefix, we get the resource segments.
_GMAIL_PATH_PREFIX = re.compile(r"^gmail/v1/users/[^/]+/")

# Known Gmail resource types (first segment after userId)
_GMAIL_KNOWN_RESOURCES = frozenset({"messages", "threads", "drafts", "labels", "profile", "history", "settings"})


def _parse_gmail_segments(path: str) -> list[str] | None:
    """
    Strip the Gmail API prefix and return resource segments.

    Example: "gmail/v1/users/me/messages/abc123/modify" -> ["messages", "abc123", "modify"]
    Returns None if the path doesn't match the Gmail API pattern.
    """
    match = _GMAIL_PATH_PREFIX.match(path)
    if not match:
        return None
    rest = path[match.end() :]
    if not rest:
        return None
    return [s for s in rest.split("/") if s]


def validate_gmail_endpoint(method: str, path: str) -> tuple[bool, str]:
    """
    Validate a Gmail API request against the proxy's endpoint policy.

    Policy: block send, permanent delete, insert, import, and settings.
    Allow read, drafts CRUD, labels CRUD, modify, and trash operations.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        path: The path after /proxy/<service>/ (e.g. "gmail/v1/users/me/messages")

    Returns:
        Tuple of (is_allowed, error_message). error_message is empty when allowed.
    """
    method = method.upper()
    segments = _parse_gmail_segments(path)

    if segments is None:
        return False, "Invalid Gmail API path format (expected gmail/v1/users/{userId}/...)"

    if not segments:
        return False, "No resource specified in Gmail API path"

    resource = segments[0]  # e.g. "messages", "threads", "drafts", "labels"
    last_segment = segments[-1]

    # === BLOCK RULES (checked first) ===

    # Block send (covers messages/send and drafts/send)
    if last_segment == "send":
        return False, "Sending email is blocked by proxy policy (use drafts instead)"

    # Block all settings endpoints
    if resource == "settings":
        return False, "Gmail settings endpoints are blocked by proxy policy (forwarding, delegates, filters)"

    # Block permanent deletion: DELETE on messages or threads
    if method == "DELETE" and resource in ("messages", "threads"):
        return False, "Permanent deletion of messages/threads is blocked (use trash instead)"

    # Block batchDelete
    if last_segment == "batchDelete":
        return False, "Batch deletion is blocked by proxy policy (use trash instead)"

    # Block POST to bare messages (insert)
    if method == "POST" and resource == "messages" and len(segments) == 1:
        return False, "Message insert is blocked by proxy policy"

    # Block messages/import
    if resource == "messages" and len(segments) >= 2 and segments[1] == "import":
        return False, "Message import is blocked by proxy policy"

    # === ALLOW RULES ===

    # GET on known resources is always allowed
    if method == "GET" and resource in _GMAIL_KNOWN_RESOURCES:
        return True, ""

    # Draft CRUD (but not send — already blocked above)
    if resource == "drafts":
        if method in ("GET", "POST", "PUT", "DELETE"):
            return True, ""

    # Label CRUD
    if resource == "labels":
        if method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            return True, ""

    # Modify: POST to */modify or messages/batchModify
    if method == "POST" and last_segment == "modify":
        return True, ""
    if method == "POST" and resource == "messages" and last_segment == "batchModify":
        return True, ""

    # Trash / untrash
    if method == "POST" and last_segment in ("trash", "untrash"):
        return True, ""

    # Profile (non-GET already covered by known resources check, but be explicit)
    if resource == "profile" and method == "GET":
        return True, ""

    # History
    if resource == "history" and method == "GET":
        return True, ""

    # === DEFAULT DENY ===
    return False, f"Endpoint not in allowlist: {method} {path}"


def validate_proxy_request(service: str, method: str, path: str) -> tuple[bool, str]:
    """
    Dispatcher: check if a service has endpoint filtering, and apply it.

    Services without a registered validator pass through (allowed by default).

    Args:
        service: Service name (e.g. "gmail", "bsky", "gmail_work")
        method: HTTP method
        path: The path after /proxy/<service>/

    Returns:
        Tuple of (is_allowed, error_message). error_message is empty when allowed.
    """
    if service == "gmail" or service.startswith("gmail_"):
        return validate_gmail_endpoint(method, path)

    # No filter for this service — allow through
    return True, ""
