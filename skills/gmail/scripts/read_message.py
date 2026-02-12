#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Read a full Gmail message body via credential proxy.

Usage:
    python read_message.py <message_id>

Environment variables (from MCP create_session):
    SESSION_ID    - Session ID
    PROXY_URL     - Proxy base URL
    GMAIL_SERVICE - Service name in credential proxy (default: "gmail")

Example:
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python read_message.py 18d1a2b3c4d5e6f7
"""

import base64
import os
import sys

import requests


def get_message(message_id: str) -> dict:
    """
    Fetch a full Gmail message by ID.

    Args:
        message_id: Gmail message ID

    Returns:
        Full message API response
    """
    service = os.environ.get("GMAIL_SERVICE", "gmail")
    session_id = os.environ.get("SESSION_ID")
    proxy_url = os.environ.get("PROXY_URL")

    if not session_id or not proxy_url:
        raise ValueError("SESSION_ID and PROXY_URL environment variables required.\nUse MCP create_session tool first.")

    response = requests.get(
        f"{proxy_url}/proxy/{service}/gmail/v1/users/me/messages/{message_id}",
        params={"format": "full"},
        headers={"X-Session-Id": session_id},
        timeout=30,
    )

    if response.status_code == 401:
        raise ValueError("Session invalid or expired. Create a new session.")
    if response.status_code == 403:
        raise ValueError(f"Session does not have access to {service} service.")
    if response.status_code == 404:
        raise ValueError(f"Message not found: {message_id}")

    response.raise_for_status()
    return response.json()


def decode_body(data: str) -> str:
    """Decode a base64url-encoded body part."""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def extract_body(payload: dict) -> str:
    """
    Extract the text body from a Gmail message payload.

    Walks the MIME tree looking for text/plain first, then text/html.

    Args:
        payload: The message payload object from the API

    Returns:
        Decoded message body text
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
            # Recurse into nested multipart
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


def format_message(message: dict) -> str:
    """Format a full message for display."""
    payload = message.get("payload", {})
    headers = extract_headers(payload)
    body = extract_body(payload)

    lines = []
    for name in ("From", "To", "Cc", "Subject", "Date"):
        if name in headers:
            lines.append(f"{name}: {headers[name]}")

    lines.append("")
    lines.append(body)

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    message_id = sys.argv[1]

    try:
        message = get_message(message_id)
        print(format_message(message))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
