"""
Shared Gmail API client with session-based authentication.

Routes all requests through the credential proxy. Credentials stay on the
proxy server; Claude only gets time-limited session tokens.  One session can
grant access to multiple services (e.g., Gmail + Bluesky), so SESSION_ID and
PROXY_URL are service-agnostic.  GMAIL_SERVICE selects which Gmail account
the proxy should use (default: "gmail").

Usage:
    from gmail_client import api, search, get_message, get_thread, create_draft

    # Low-level: direct API calls
    profile = api.get("profile")
    api.post("messages/msg123/modify", json={"addLabelIds": ["STARRED"]})

    # High-level helpers
    messages = search("from:alice is:unread", max_results=5)
    thread   = get_thread("18d1a2b3c4d5e6f7")
    draft    = create_draft("bob@example.com", "Re: Hello", "Got it, thanks!",
                            thread_id="18d1a2b3c4d5e6f7",
                            reply_to_msg_id="18d1a2b3c4d5e6f7")
"""

import base64
import os
from email.mime.text import MIMEText

import requests

DEFAULT_TIMEOUT = 30


class AuthRequiredError(Exception):
    """Raised when a request requires auth but no session is available."""

    def __init__(self):
        super().__init__(
            "Gmail requires authentication. Set SESSION_ID and PROXY_URL environment variables "
            "(use MCP create_session tool)."
        )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


class _API:
    """Namespace for Gmail API request methods.

    All requests go through the credential proxy with session-based auth.
    The proxy injects Gmail OAuth2 credentials automatically.
    """

    @staticmethod
    def _get_session() -> tuple[str, str, str]:
        """Return (session_id, proxy_url, service) or raise.

        Raises:
            AuthRequiredError: If SESSION_ID or PROXY_URL is missing.
        """
        session_id = os.environ.get("SESSION_ID")
        proxy_url = os.environ.get("PROXY_URL")
        if not session_id or not proxy_url:
            raise AuthRequiredError()
        service = os.environ.get("GMAIL_SERVICE", "gmail")
        return session_id, proxy_url, service

    @staticmethod
    def _url(proxy_url: str, service: str, path: str) -> str:
        """Build the full proxy URL for a Gmail API path."""
        return f"{proxy_url}/proxy/{service}/gmail/v1/users/me/{path}"

    @staticmethod
    def get(path: str, params: dict | None = None) -> dict:
        """GET request to a Gmail API path.

        Args:
            path: Path relative to ``gmail/v1/users/me/``
                  (e.g., ``"messages"``, ``"threads/abc123"``).
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            AuthRequiredError: If no session is available.
            requests.exceptions.HTTPError: On non-2xx responses.
        """
        session_id, proxy_url, service = _API._get_session()
        url = _API._url(proxy_url, service, path)
        response = requests.get(
            url,
            params=params,
            headers={"X-Session-Id": session_id},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def post(path: str, json: dict | None = None) -> dict:
        """POST request to a Gmail API path.

        Args:
            path: Path relative to ``gmail/v1/users/me/``.
            json: JSON body.

        Returns:
            Parsed JSON response.

        Raises:
            AuthRequiredError: If no session is available.
            requests.exceptions.HTTPError: On non-2xx responses.
        """
        session_id, proxy_url, service = _API._get_session()
        url = _API._url(proxy_url, service, path)
        response = requests.post(
            url,
            json=json,
            headers={"X-Session-Id": session_id},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def delete(path: str) -> dict:
        """DELETE request to a Gmail API path.

        Args:
            path: Path relative to ``gmail/v1/users/me/``.

        Returns:
            Parsed JSON response (often empty ``{}``).

        Raises:
            AuthRequiredError: If no session is available.
            requests.exceptions.HTTPError: On non-2xx responses.
        """
        session_id, proxy_url, service = _API._get_session()
        url = _API._url(proxy_url, service, path)
        response = requests.delete(
            url,
            headers={"X-Session-Id": session_id},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        # DELETE may return empty body (204)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    @staticmethod
    def patch(path: str, json: dict | None = None) -> dict:
        """PATCH request to a Gmail API path.

        Args:
            path: Path relative to ``gmail/v1/users/me/``.
            json: JSON body.

        Returns:
            Parsed JSON response.

        Raises:
            AuthRequiredError: If no session is available.
            requests.exceptions.HTTPError: On non-2xx responses.
        """
        session_id, proxy_url, service = _API._get_session()
        url = _API._url(proxy_url, service, path)
        response = requests.patch(
            url,
            json=json,
            headers={"X-Session-Id": session_id},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def put(path: str, json: dict | None = None) -> dict:
        """PUT request to a Gmail API path.

        Args:
            path: Path relative to ``gmail/v1/users/me/``.
            json: JSON body.

        Returns:
            Parsed JSON response.

        Raises:
            AuthRequiredError: If no session is available.
            requests.exceptions.HTTPError: On non-2xx responses.
        """
        session_id, proxy_url, service = _API._get_session()
        url = _API._url(proxy_url, service, path)
        response = requests.put(
            url,
            json=json,
            headers={"X-Session-Id": session_id},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()


api = _API()


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------


def decode_body(data: str) -> str:
    """Decode a base64url-encoded Gmail body part.

    Args:
        data: Base64url-encoded string from the Gmail API.

    Returns:
        Decoded UTF-8 text.
    """
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def extract_body(payload: dict) -> str:
    """Extract the text body from a Gmail message payload.

    Walks the MIME tree looking for text/plain first, then text/html.

    Args:
        payload: The ``payload`` object from a Gmail message response.

    Returns:
        Decoded message body, or ``"(no text body)"`` if none found.
    """
    mime_type = payload.get("mimeType", "")

    # Simple single-part message
    body_data = payload.get("body", {}).get("data")
    if body_data and mime_type.startswith("text/"):
        return decode_body(body_data)

    # Multipart — search parts recursively
    parts = payload.get("parts", [])
    text_plain = None
    text_html = None

    for part in parts:
        part_mime = part.get("mimeType", "")
        part_body = part.get("body", {}).get("data")

        if part_mime == "text/plain" and part_body:
            text_plain = decode_body(part_body)
        elif part_mime == "text/html" and part_body:
            text_html = decode_body(part_body)
        elif part_mime.startswith("multipart/"):
            nested = extract_body(part)
            if nested and nested != "(no text body)":
                return nested

    return text_plain or text_html or "(no text body)"


def extract_headers(payload: dict, names: list[str] | None = None) -> dict[str, str]:
    """Extract headers from a Gmail message payload.

    Matching is case-insensitive per RFC 2822.  The returned dict uses the
    *requested* casing, not the casing from the API response.  For example,
    requesting ``["Message-ID"]`` will match a response header named
    ``Message-Id`` and return the key as ``"Message-ID"``.

    Args:
        payload: The ``payload`` object from a Gmail message response.
        names: Header names to extract (case-insensitive).
               Defaults to ``["From", "To", "Cc", "Subject", "Date"]``.

    Returns:
        Dict mapping header name to value for each header found.
    """
    if names is None:
        names = ["From", "To", "Cc", "Subject", "Date"]
    # Map lowercased name -> requested name for case-insensitive lookup
    target = {n.lower(): n for n in names}
    result: dict[str, str] = {}
    for header in payload.get("headers", []):
        name = header.get("name", "")
        requested = target.get(name.lower())
        if requested is not None:
            result[requested] = header.get("value", "")
    return result


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def paginate(
    path: str,
    params: dict,
    result_key: str,
    *,
    max_items: int | None = None,
    page_size: int = 100,
) -> list[dict]:
    """Fetch all pages from a paginated Gmail endpoint.

    Gmail uses ``pageToken`` / ``nextPageToken`` (not ``cursor``).

    Args:
        path: API path (e.g., ``"messages"``).
        params: Base query parameters (pageToken is managed automatically).
        result_key: JSON key containing the result list (e.g., ``"messages"``).
        max_items: Stop after collecting this many items.  ``None`` = no limit.
        page_size: Items per page (``maxResults``).

    Returns:
        List of all collected items across pages.
    """
    items: list[dict] = []
    page_token = None

    while True:
        page_params = {**params, "maxResults": page_size}
        if page_token:
            page_params["pageToken"] = page_token

        data = api.get(path, page_params)
        page_items = data.get(result_key, [])
        items.extend(page_items)

        if max_items is not None and len(items) >= max_items:
            return items[:max_items]

        page_token = data.get("nextPageToken")
        if not page_token or not page_items:
            break

    return items


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------


def search(query: str = "", max_results: int = 10) -> list[dict]:
    """Search Gmail messages and return enriched results.

    Each returned message dict includes ``id``, ``threadId``, ``headers``
    (decoded), and ``snippet``.

    Args:
        query: Gmail search query (e.g., ``"from:alice is:unread"``).
        max_results: Maximum number of messages to return (1-500).

    Returns:
        List of message dicts with decoded headers and snippet.
    """
    params: dict = {"maxResults": min(max_results, 500)}
    if query:
        params["q"] = query

    data = api.get("messages", params)
    stubs = data.get("messages", [])
    if not stubs:
        return []

    results = []
    for stub in stubs:
        msg = api.get(
            f"messages/{stub['id']}",
            {"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
        )
        headers = extract_headers(msg.get("payload", {}), ["From", "To", "Subject", "Date"])
        results.append(
            {
                "id": msg["id"],
                "threadId": msg.get("threadId"),
                "headers": headers,
                "snippet": msg.get("snippet", ""),
            }
        )

    return results


def get_message(message_id: str) -> dict:
    """Fetch a full Gmail message with decoded body and headers.

    Args:
        message_id: Gmail message ID.

    Returns:
        Dict with ``id``, ``threadId``, ``headers``, ``body``, and
        ``labelIds``.
    """
    msg = api.get(f"messages/{message_id}", {"format": "full"})
    payload = msg.get("payload", {})
    return {
        "id": msg["id"],
        "threadId": msg.get("threadId"),
        "labelIds": msg.get("labelIds", []),
        "headers": extract_headers(payload),
        "body": extract_body(payload),
    }


def get_thread(thread_id: str) -> dict:
    """Fetch a full Gmail thread with all messages decoded.

    Args:
        thread_id: Gmail thread ID.

    Returns:
        Dict with ``id`` and ``messages`` list.  Each message has ``id``,
        ``threadId``, ``headers``, ``body``, and ``labelIds``.
    """
    data = api.get(f"threads/{thread_id}", {"format": "full"})
    messages = []
    for msg in data.get("messages", []):
        payload = msg.get("payload", {})
        messages.append(
            {
                "id": msg["id"],
                "threadId": msg.get("threadId"),
                "labelIds": msg.get("labelIds", []),
                "headers": extract_headers(payload),
                "body": extract_body(payload),
            }
        )
    return {"id": data["id"], "messages": messages}


def create_draft(
    to: str,
    subject: str,
    body: str,
    *,
    thread_id: str | None = None,
    reply_to_msg_id: str | None = None,
) -> dict:
    """Create a Gmail draft, optionally threaded as a reply.

    For a threaded reply, provide both ``thread_id`` and
    ``reply_to_msg_id``.  The function fetches the original message's
    ``Message-ID`` and ``References`` headers to set ``In-Reply-To`` and
    ``References`` correctly.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text message body.
        thread_id: Gmail thread ID to attach the draft to.
        reply_to_msg_id: Gmail message ID of the message being replied to.
            Used to fetch ``Message-ID`` for correct threading headers.

    Returns:
        Draft resource from the Gmail API.
    """
    mime_msg = MIMEText(body)
    mime_msg["To"] = to
    mime_msg["Subject"] = subject

    # Add threading headers if replying
    if reply_to_msg_id:
        orig = api.get(
            f"messages/{reply_to_msg_id}",
            {"format": "metadata", "metadataHeaders": ["Message-ID", "References"]},
        )
        orig_headers = extract_headers(orig.get("payload", {}), ["Message-ID", "References"])
        message_id_header = orig_headers.get("Message-ID", "")
        references = orig_headers.get("References", "")

        if message_id_header:
            mime_msg["In-Reply-To"] = message_id_header
            if references:
                mime_msg["References"] = f"{references} {message_id_header}"
            else:
                mime_msg["References"] = message_id_header

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()

    draft_body: dict = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    return api.post("drafts", draft_body)
