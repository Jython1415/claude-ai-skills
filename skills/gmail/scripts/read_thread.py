#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Read a full Gmail thread (conversation) via credential proxy.

Usage:
    python read_thread.py <thread_id>
    python read_thread.py --search "subject:meeting from:alice"

Arguments:
    thread_id   - Gmail thread ID (from list_messages.py or Gmail URL)
    --search Q  - Search for a thread matching query Q, then read it

Environment variables (from MCP create_session):
    SESSION_ID    - Session ID
    PROXY_URL     - Proxy base URL
    GMAIL_SERVICE - Service name in credential proxy (default: "gmail")

Example:
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python read_thread.py 18d1a2b3c4d5e6f7
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python read_thread.py --search "subject:weekly sync"
"""

import base64
import os
import sys

import requests


def _get_env() -> tuple[str, str, str]:
    """Return (session_id, proxy_url, service) from environment."""
    service = os.environ.get("GMAIL_SERVICE", "gmail")
    session_id = os.environ.get("SESSION_ID")
    proxy_url = os.environ.get("PROXY_URL")

    if not session_id or not proxy_url:
        raise ValueError("SESSION_ID and PROXY_URL environment variables required.\nUse MCP create_session tool first.")

    return session_id, proxy_url, service


def search_threads(query: str, max_results: int = 1) -> list[dict]:
    """
    Search for threads matching a Gmail query.

    Args:
        query: Gmail search query (e.g., "subject:meeting from:alice")
        max_results: Maximum number of thread stubs to return

    Returns:
        List of thread stubs with "id" and "historyId" fields
    """
    session_id, proxy_url, service = _get_env()

    response = requests.get(
        f"{proxy_url}/proxy/{service}/gmail/v1/users/me/threads",
        params={"q": query, "maxResults": max_results},
        headers={"X-Session-Id": session_id},
        timeout=30,
    )

    if response.status_code == 401:
        raise ValueError("Session invalid or expired. Create a new session.")
    if response.status_code == 403:
        raise ValueError(f"Session does not have access to {service} service.")

    response.raise_for_status()
    return response.json().get("threads", [])


def get_thread(thread_id: str) -> dict:
    """
    Fetch a full Gmail thread by ID with all messages.

    Args:
        thread_id: Gmail thread ID

    Returns:
        Full thread API response including all messages with decoded bodies
    """
    session_id, proxy_url, service = _get_env()

    response = requests.get(
        f"{proxy_url}/proxy/{service}/gmail/v1/users/me/threads/{thread_id}",
        params={"format": "full"},
        headers={"X-Session-Id": session_id},
        timeout=30,
    )

    if response.status_code == 401:
        raise ValueError("Session invalid or expired. Create a new session.")
    if response.status_code == 403:
        raise ValueError(f"Session does not have access to {service} service.")
    if response.status_code == 404:
        raise ValueError(f"Thread not found: {thread_id}")

    response.raise_for_status()
    return response.json()


def decode_body(data: str) -> str:
    """Decode a base64url-encoded body part."""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def extract_body(payload: dict) -> str:
    """
    Extract the text body from a Gmail message payload.

    Walks the MIME tree looking for text/plain first, then text/html.
    """
    mime_type = payload.get("mimeType", "")

    # Simple single-part message
    body_data = payload.get("body", {}).get("data")
    if body_data and mime_type.startswith("text/"):
        return decode_body(body_data)

    # Multipart message — search parts recursively
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
            if nested:
                return nested

    return text_plain or text_html or "(no text body)"


def extract_headers(payload: dict) -> dict:
    """Extract common headers from a message payload."""
    headers = {}
    for header in payload.get("headers", []):
        name = header.get("name", "")
        if name in ("From", "To", "Cc", "Subject", "Date"):
            headers[name] = header.get("value", "")
    return headers


def format_message(message: dict, index: int, total: int) -> str:
    """Format a single message within a thread for display."""
    payload = message.get("payload", {})
    headers = extract_headers(payload)
    body = extract_body(payload)

    lines = [f"--- Message {index}/{total} ---"]
    for name in ("From", "To", "Cc", "Subject", "Date"):
        if name in headers:
            lines.append(f"{name}: {headers[name]}")

    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def format_thread(thread: dict) -> str:
    """Format an entire thread for display with all messages in order."""
    messages = thread.get("messages", [])
    total = len(messages)

    if total == 0:
        return "(empty thread)"

    # Extract subject from first message for the header
    first_payload = messages[0].get("payload", {})
    first_headers = extract_headers(first_payload)
    subject = first_headers.get("Subject", "(no subject)")

    parts = [
        f"Thread: {subject}",
        f"Messages: {total}",
        f"Thread ID: {thread.get('id', 'unknown')}",
        "=" * 72,
    ]

    for i, message in enumerate(messages, 1):
        parts.append(format_message(message, i, total))
        if i < total:
            parts.append("")

    return "\n".join(parts)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    try:
        if sys.argv[1] == "--search":
            if len(sys.argv) < 3:
                print("Error: --search requires a query argument", file=sys.stderr)
                sys.exit(1)
            query = sys.argv[2]
            threads = search_threads(query)
            if not threads:
                print(f"No threads found for query: {query}", file=sys.stderr)
                sys.exit(1)
            thread_id = threads[0]["id"]
            print(f"Found thread: {thread_id}\n")
        else:
            thread_id = sys.argv[1]

        thread = get_thread(thread_id)
        print(format_thread(thread))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
