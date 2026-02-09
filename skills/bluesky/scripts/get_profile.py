#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Get Bluesky user profile.

Uses the public API by default. Set SESSION_ID and PROXY_URL environment
variables to use the credential proxy instead.

Usage:
    python get_profile.py <handle_or_did>

Example:
    python get_profile.py bsky.app
"""

import os
import sys

import requests

PUBLIC_API = "https://public.api.bsky.app/xrpc"


def get_profile(actor: str) -> dict:
    """
    Get Bluesky user profile.

    Uses the public API by default (no auth needed).
    Falls back to credential proxy if SESSION_ID and PROXY_URL are set.

    Args:
        actor: Handle (e.g., "bsky.app") or DID

    Returns:
        Profile data
    """
    session_id = os.environ.get("SESSION_ID")
    proxy_url = os.environ.get("PROXY_URL")

    if session_id and proxy_url:
        # Use proxy (authenticated)
        response = requests.get(
            f"{proxy_url}/proxy/bsky/app.bsky.actor.getProfile",
            params={"actor": actor},
            headers={"X-Session-Id": session_id},
            timeout=30,
        )
    else:
        # Use public API (no auth needed)
        response = requests.get(
            f"{PUBLIC_API}/app.bsky.actor.getProfile",
            params={"actor": actor},
            timeout=30,
        )

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
