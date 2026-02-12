#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Search and list Gmail messages via credential proxy.

Usage:
    python list_messages.py [query] [max_results]

Environment variables (from MCP create_session):
    SESSION_ID    - Session ID
    PROXY_URL     - Proxy base URL
    GMAIL_SERVICE - Service name in credential proxy (default: "gmail")

Example:
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python list_messages.py "from:example@gmail.com" 10
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python list_messages.py "is:unread" 25
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python list_messages.py "" 10
"""

import os
import sys

import requests


def list_messages(query: str = "", max_results: int = 10) -> list:
    """
    List Gmail messages matching query.

    Args:
        query: Gmail search query (e.g., "from:user@example.com is:unread")
        max_results: Maximum number of messages to return (1-500)

    Returns:
        List of message objects with headers and snippet
    """
    service = os.environ.get("GMAIL_SERVICE", "gmail")
    session_id = os.environ.get("SESSION_ID")
    proxy_url = os.environ.get("PROXY_URL")

    if not session_id or not proxy_url:
        raise ValueError("SESSION_ID and PROXY_URL environment variables required.\nUse MCP create_session tool first.")

    # List messages (returns message IDs only)
    params = {"maxResults": min(max_results, 500)}
    if query:
        params["q"] = query

    response = requests.get(
        f"{proxy_url}/proxy/{service}/gmail/v1/users/me/messages",
        params=params,
        headers={"X-Session-Id": session_id},
        timeout=30,
    )

    if response.status_code == 401:
        raise ValueError("Session invalid or expired. Create a new session.")
    if response.status_code == 403:
        raise ValueError(f"Session does not have access to {service} service.")

    response.raise_for_status()
    result = response.json()

    messages = result.get("messages", [])
    if not messages:
        return []

    # Fetch full metadata for each message
    detailed_messages = []
    for msg in messages:
        msg_id = msg["id"]
        msg_response = requests.get(
            f"{proxy_url}/proxy/{service}/gmail/v1/users/me/messages/{msg_id}",
            params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
            headers={"X-Session-Id": session_id},
            timeout=30,
        )

        if msg_response.status_code == 200:
            detailed_messages.append(msg_response.json())

    return detailed_messages


def format_message(message: dict) -> str:
    """Format a message for display."""
    msg_id = message.get("id", "unknown")
    thread_id = message.get("threadId", "unknown")
    snippet = message.get("snippet", "")

    # Extract headers
    headers = {}
    for header in message.get("payload", {}).get("headers", []):
        name = header.get("name", "")
        value = header.get("value", "")
        if name in ["From", "To", "Subject", "Date"]:
            headers[name] = value

    from_addr = headers.get("From", "Unknown")
    to_addr = headers.get("To", "Unknown")
    subject = headers.get("Subject", "(No subject)")
    date = headers.get("Date", "Unknown date")

    # Format date to be more readable (just take the date part)
    if "," in date:
        date = date.split(",", 1)[1].strip()[:16]  # e.g., "9 Feb 2026 10:30"

    return (
        f"ID: {msg_id}\n"
        f"Thread ID: {thread_id}\n"
        f"From: {from_addr}\n"
        f"To: {to_addr}\n"
        f"Subject: {subject}\n"
        f"Date: {date}\n"
        f"Preview: {snippet[:100]}{'...' if len(snippet) > 100 else ''}\n"
    )


def main():
    query = ""
    max_results = 10

    if len(sys.argv) > 1:
        query = sys.argv[1]
    if len(sys.argv) > 2:
        max_results = int(sys.argv[2])

    try:
        messages = list_messages(query, max_results)

        if not messages:
            print("No messages found" + (f" for query: {query}" if query else ""))
            return

        print(f"Found {len(messages)} message(s)" + (f" for query: {query}" if query else ""))
        print("=" * 80)
        print()

        for message in messages:
            print(format_message(message))
            print("-" * 80)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
