#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Search Bluesky posts.

Uses the public API by default. Set SESSION_ID and PROXY_URL environment
variables to use the credential proxy instead.

Usage:
    python search_posts.py <query> [limit]

Example:
    python search_posts.py "python" 10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bsky_client import api


def search_posts(query: str, limit: int = 25) -> dict:
    """
    Search Bluesky posts.

    Args:
        query: Search query string
        limit: Maximum number of results (1-100)

    Returns:
        API response with posts array
    """
    return api.get("app.bsky.feed.searchPosts", {"q": query, "limit": min(limit, 100)})


def format_post(post: dict) -> str:
    """Format a post for display."""
    author = post.get("author", {})
    handle = author.get("handle", "unknown")
    display_name = author.get("displayName", handle)
    record = post.get("record", {})
    text = record.get("text", "")
    created_at = record.get("createdAt", "")[:10]  # Just the date

    likes = post.get("likeCount", 0)
    reposts = post.get("repostCount", 0)
    replies = post.get("replyCount", 0)

    return f"@{handle} ({display_name}) - {created_at}\n{text}\n[{likes} likes, {reposts} reposts, {replies} replies]\n"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    try:
        result = search_posts(query, limit)
        posts = result.get("posts", [])

        if not posts:
            print(f"No posts found for: {query}")
            return

        print(f"Found {len(posts)} posts for: {query}\n")
        print("-" * 60)

        for post in posts:
            print(format_post(post))
            print("-" * 60)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
