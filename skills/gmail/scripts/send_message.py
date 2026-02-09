#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Send email via Gmail API through credential proxy.

Usage:
    python send_message.py <to> <subject> <body>

Environment variables (from MCP create_session):
    SESSION_ID    - Session ID
    PROXY_URL     - Proxy base URL
    GMAIL_SERVICE - Service name in credential proxy (default: "gmail")

Example:
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python send_message.py "recipient@example.com" "Test Subject" "Hello, this is a test email!"
"""

import base64
import os
import sys
from email.mime.text import MIMEText

import requests


def send_message(to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail API.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body text

    Returns:
        API response with message ID and thread ID
    """
    service = os.environ.get("GMAIL_SERVICE", "gmail")
    session_id = os.environ.get("SESSION_ID")
    proxy_url = os.environ.get("PROXY_URL")

    if not session_id or not proxy_url:
        raise ValueError("SESSION_ID and PROXY_URL environment variables required.\nUse MCP create_session tool first.")

    # Create MIME message
    message = MIMEText(body)
    message["To"] = to
    message["Subject"] = subject

    # Base64url encode the message
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send via Gmail API
    response = requests.post(
        f"{proxy_url}/proxy/{service}/gmail/v1/users/me/messages/send",
        json={"raw": raw},
        headers={"X-Session-Id": session_id},
        timeout=30,
    )

    if response.status_code == 401:
        raise ValueError("Session invalid or expired. Create a new session.")
    if response.status_code == 403:
        raise ValueError(f"Session does not have access to {service} service.")

    response.raise_for_status()
    return response.json()


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    to = sys.argv[1]
    subject = sys.argv[2]
    body = sys.argv[3]

    try:
        result = send_message(to, subject, body)

        msg_id = result.get("id", "unknown")
        thread_id = result.get("threadId", "unknown")
        labels = result.get("labelIds", [])

        print("Email sent successfully!")
        print(f"Message ID: {msg_id}")
        print(f"Thread ID: {thread_id}")
        print(f"Labels: {', '.join(labels)}")

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
