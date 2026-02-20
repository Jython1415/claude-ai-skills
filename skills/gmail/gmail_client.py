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
import json
import os
import urllib.parse
import uuid
from email.mime.text import MIMEText
from html.parser import HTMLParser

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
    def _batch_url(proxy_url: str, service: str) -> str:
        """Build the full proxy URL for the Gmail batch endpoint."""
        return f"{proxy_url}/proxy/{service}/batch/gmail/v1"

    @staticmethod
    def batch_post(body: str, boundary: str) -> requests.Response:
        """POST a multipart/mixed batch request to the Gmail batch endpoint.

        Args:
            body: Multipart request body string.
            boundary: Boundary string used in the body.

        Returns:
            Raw requests.Response (not parsed).

        Raises:
            AuthRequiredError: If no session is available.
            requests.exceptions.HTTPError: On non-2xx responses.
        """
        session_id, proxy_url, service = _API._get_session()
        url = _API._batch_url(proxy_url, service)
        response = requests.post(
            url,
            data=body.encode("utf-8"),
            headers={
                "X-Session-Id": session_id,
                "Content-Type": f"multipart/mixed; boundary={boundary}",
            },
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response

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

    return text_plain or (strip_html(text_html) if text_html else None) or "(no text body)"


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


class _HTMLStripper(HTMLParser):
    """HTMLParser subclass that extracts text content from HTML."""

    _SKIP_TAGS = frozenset(("script", "style"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities, returning plain text.

    Uses stdlib html.parser for correct handling of malformed HTML
    and character references. Suppresses content inside <script> and
    <style> elements.

    Args:
        text: HTML string to strip.

    Returns:
        Plain text with tags removed and entities decoded.
    """
    stripper = _HTMLStripper()
    stripper.feed(text)
    return "".join(stripper._parts)


def extract_attachments(payload: dict) -> list[dict]:
    """Extract attachment metadata from a message payload.

    Walks the MIME tree and returns metadata for parts that have an
    attachmentId (i.e., non-inline content that must be fetched separately).

    Args:
        payload: The message payload dict from the Gmail API.

    Returns:
        List of dicts with keys: filename, mime_type, attachment_id, size.
    """
    attachments = []

    def _walk(part: dict) -> None:
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        if attachment_id:
            attachments.append(
                {
                    "filename": part.get("filename", ""),
                    "mime_type": part.get("mimeType", ""),
                    "attachment_id": attachment_id,
                    "size": body.get("size", 0),
                }
            )
        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)
    return attachments


def get_attachment(message_id: str, attachment_id: str) -> bytes:
    """Download an attachment and return its raw bytes.

    Args:
        message_id: The message ID containing the attachment.
        attachment_id: The attachment ID from extract_attachments().

    Returns:
        The decoded attachment bytes.
    """
    data = api.get(f"messages/{message_id}/attachments/{attachment_id}")
    return base64.urlsafe_b64decode(data["data"])


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
# Batch helpers
# ---------------------------------------------------------------------------

_BATCH_LIMIT = 100


def _build_batch_body(paths: list[str], boundary: str) -> str:
    parts = []
    for i, path in enumerate(paths):
        parts.append(
            f"--{boundary}\r\n"
            f"Content-Type: application/http\r\n"
            f"Content-ID: <item{i}>\r\n"
            f"\r\n"
            f"GET /{path} HTTP/1.1\r\n"
            f"\r\n"
        )
    parts.append(f"--{boundary}--")
    return "".join(parts)


def _parse_batch_response(response: requests.Response) -> list[dict]:
    content_type = response.headers.get("Content-Type", "")
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[len("boundary=") :].strip('"')
            break
    if not boundary:
        return []

    text = response.text
    delimiter = f"--{boundary}"
    raw_parts = text.split(delimiter)
    # First element is preamble before first boundary, last is epilogue after --boundary--
    raw_parts = raw_parts[1:]

    results = []
    for raw_part in raw_parts:
        if raw_part.strip() == "--" or raw_part.strip() == "":
            continue
        # Strip leading \r\n
        if raw_part.startswith("\r\n"):
            raw_part = raw_part[2:]
        # Split outer headers from body (blank line separator)
        if "\r\n\r\n" not in raw_part:
            continue
        _, inner = raw_part.split("\r\n\r\n", 1)
        # inner is the embedded HTTP response: status line, headers, blank line, body
        if "\r\n" not in inner:
            continue
        status_line, rest = inner.split("\r\n", 1)
        # Check for 200 status
        status_parts = status_line.split(" ", 2)
        if len(status_parts) < 2:
            continue
        try:
            status_code = int(status_parts[1])
        except ValueError:
            continue
        if status_code != 200:
            continue
        # Find the blank line separating inner headers from inner body
        if "\r\n\r\n" not in rest:
            continue
        _, body = rest.split("\r\n\r\n", 1)
        body = body.rstrip("\r\n")
        if not body:
            continue
        try:
            results.append(json.loads(body))
        except (ValueError, KeyError):
            continue

    return results


def batch_get_messages(
    message_ids: list[str],
    *,
    format: str = "metadata",
    metadata_headers: list[str] | None = None,
) -> list[dict]:
    params: dict = {"format": format}
    if metadata_headers:
        params["metadataHeaders"] = metadata_headers
    paths = [f"gmail/v1/users/me/messages/{mid}?{urllib.parse.urlencode(params, doseq=True)}" for mid in message_ids]
    results = []
    for i in range(0, len(paths), _BATCH_LIMIT):
        chunk = paths[i : i + _BATCH_LIMIT]
        boundary = uuid.uuid4().hex
        body = _build_batch_body(chunk, boundary)
        response = api.batch_post(body, boundary)
        results.extend(_parse_batch_response(response))
    return results


def batch_get_threads(
    thread_ids: list[str],
    *,
    format: str = "metadata",
    metadata_headers: list[str] | None = None,
) -> list[dict]:
    params: dict = {"format": format}
    if metadata_headers:
        params["metadataHeaders"] = metadata_headers
    paths = [f"gmail/v1/users/me/threads/{tid}?{urllib.parse.urlencode(params, doseq=True)}" for tid in thread_ids]
    results = []
    for i in range(0, len(paths), _BATCH_LIMIT):
        chunk = paths[i : i + _BATCH_LIMIT]
        boundary = uuid.uuid4().hex
        body = _build_batch_body(chunk, boundary)
        response = api.batch_post(body, boundary)
        results.extend(_parse_batch_response(response))
    return results


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

    message_ids = [stub["id"] for stub in stubs]
    messages = batch_get_messages(
        message_ids,
        format="metadata",
        metadata_headers=["From", "To", "Subject", "Date"],
    )

    results = []
    for msg in messages:
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


def get_profile() -> dict:
    """Get the authenticated user's Gmail profile.

    Returns a dict with emailAddress, messagesTotal, threadsTotal, historyId.
    Useful as a cheap preflight check before broad searches.
    """
    return api.get("profile")


def search_threads(query: str = "", max_results: int = 10) -> list[dict]:
    """Search for threads and return full thread objects.

    Combines the threads.list and threads.get calls into one convenience
    function. Each returned thread includes its full message list.

    Args:
        query: Gmail search query (same syntax as the Gmail search box).
        max_results: Maximum number of threads to return (default 10).

    Returns:
        List of thread objects, each with id, messages, and other fields.
    """
    params = {"maxResults": max_results}
    if query:
        params["q"] = query

    data = api.get("threads", params)
    thread_stubs = data.get("threads", [])

    thread_ids = [stub["id"] for stub in thread_stubs]
    return batch_get_threads(thread_ids)
