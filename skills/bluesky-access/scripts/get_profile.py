#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Get Bluesky user profile via credential proxy.

Usage:
    python get_profile.py <handle_or_did>

Environment variables (from MCP create_session):
    SESSION_ID - Session ID
    PROXY_URL  - Proxy base URL

Example:
    SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python get_profile.py bsky.app
"""

import os
import sys

import requests


def get_profile(actor: str) -> dict:
    """
    Get Bluesky user profile.

    Args:
        actor: Handle (e.g., "bsky.app") or DID

    Returns:
        Profile data
    """
    session_id = os.environ.get("SESSION_ID")
    proxy_url = os.environ.get("PROXY_URL")

    if not session_id or not proxy_url:
        raise ValueError("SESSION_ID and PROXY_URL environment variables required.\nUse MCP create_session tool first.")

    response = requests.get(
        f"{proxy_url}/proxy/bsky/app.bsky.actor.getProfile",
        params={"actor": actor},
        headers={"X-Session-Id": session_id},
        timeout=30,
    )

    if response.status_code == 401:
        raise ValueError("Session invalid or expired. Create a new session.")
    if response.status_code == 403:
        raise ValueError("Session does not have access to bsky service.")
    if response.status_code == 400:
        raise ValueError(f"User not found: {actor}")

    response.raise_for_status()
    return response.json()


def format_profile(profile: dict) -> str:
    """Format profile for display."""
    handle = profile.get("handle", "unknown")
    display_name = profile.get("displayName", handle)
    description = profile.get("description", "No bio")
    followers = profile.get("followersCount", 0)
    following = profile.get("followsCount", 0)
    posts = profile.get("postsCount", 0)
    created = profile.get("createdAt", "")[:10]

    return (
        f"@{handle}\n"
        f"Name: {display_name}\n"
        f"Bio: {description}\n"
        f"\n"
        f"Followers: {followers:,}\n"
        f"Following: {following:,}\n"
        f"Posts: {posts:,}\n"
        f"Joined: {created}\n"
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    actor = sys.argv[1]

    try:
        profile = get_profile(actor)
        print(format_profile(profile))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
