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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bsky_client import api


def get_profile(actor: str) -> dict:
    """
    Get Bluesky user profile.

    Args:
        actor: Handle (e.g., "bsky.app") or DID

    Returns:
        Profile data
    """
    try:
        return api.get("app.bsky.actor.getProfile", {"actor": actor})
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            raise ValueError(f"User not found: {actor}") from e
        raise


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
