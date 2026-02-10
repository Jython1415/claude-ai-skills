#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Search for Bluesky users by name, handle, or bio.

Uses the public API (no auth needed).

Usage:
    python search_users.py <query> [limit]

Examples:
    python search_users.py "machine learning"
    python search_users.py "python developer" 10
"""

import sys

import requests

PUBLIC_API = "https://public.api.bsky.app/xrpc"


def search_users(query: str, limit: int = 25) -> dict:
    """
    Search for Bluesky users.

    Uses the public API (no auth needed).

    Args:
        query: Search query (matches against handle, display name, and bio)
        limit: Maximum number of results (1-100)

    Returns:
        API response with actors array
    """
    response = requests.get(
        f"{PUBLIC_API}/app.bsky.actor.searchActors",
        params={"q": query, "limit": min(max(limit, 1), 100)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def format_user(actor: dict) -> str:
    """Format a user for display."""
    handle = actor.get("handle", "unknown")
    display_name = actor.get("displayName", handle)
    description = actor.get("description", "")
    followers = actor.get("followersCount", 0)
    following = actor.get("followsCount", 0)
    posts = actor.get("postsCount", 0)

    bio = description.replace("\n", " ")[:120] if description else "No bio"

    return f"@{handle} ({display_name})\n  {bio}\n  [{followers:,} followers, {following:,} following, {posts:,} posts]"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    try:
        result = search_users(query, limit)
        actors = result.get("actors", [])

        if not actors:
            print(f"No users found for: {query}")
            return

        print(f"Found {len(actors)} users for: {query}\n")
        print("-" * 60)

        for actor in actors:
            print(format_user(actor))
            print("-" * 60)

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
