#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Get a Bluesky user's recent posts.

Uses the public API (no auth needed). Supports filtering by post type.

Usage:
    python get_author_feed.py <handle_or_did> [limit] [filter]

Arguments:
    handle_or_did  User handle (e.g., bsky.app) or DID
    limit          Max posts to return (1-100, default 20)
    filter         Post filter: posts_with_replies, posts_no_replies,
                   posts_with_media, posts_and_author_threads (default: posts_no_replies)

Examples:
    python get_author_feed.py bsky.app
    python get_author_feed.py bsky.app 10 posts_with_media
"""

import sys

import requests

PUBLIC_API = "https://public.api.bsky.app/xrpc"

VALID_FILTERS = [
    "posts_with_replies",
    "posts_no_replies",
    "posts_with_media",
    "posts_and_author_threads",
]


def get_author_feed(actor: str, limit: int = 20, filter_type: str = "posts_no_replies") -> dict:
    """
    Get a user's recent posts.

    Uses the public API (no auth needed).

    Args:
        actor: Handle (e.g., "bsky.app") or DID
        limit: Maximum number of posts (1-100)
        filter_type: One of posts_with_replies, posts_no_replies,
                     posts_with_media, posts_and_author_threads

    Returns:
        API response with feed array
    """
    if filter_type not in VALID_FILTERS:
        raise ValueError(f"Invalid filter: {filter_type}. Must be one of: {', '.join(VALID_FILTERS)}")

    response = requests.get(
        f"{PUBLIC_API}/app.bsky.feed.getAuthorFeed",
        params={
            "actor": actor,
            "limit": min(max(limit, 1), 100),
            "filter": filter_type,
        },
        timeout=30,
    )

    if response.status_code == 400:
        raise ValueError(f"User not found: {actor}")

    response.raise_for_status()
    return response.json()


def format_post(item: dict) -> str:
    """Format a feed item for display."""
    post = item.get("post", {})
    author = post.get("author", {})
    handle = author.get("handle", "unknown")
    record = post.get("record", {})
    text = record.get("text", "")
    created_at = record.get("createdAt", "")[:16]

    likes = post.get("likeCount", 0)
    reposts = post.get("repostCount", 0)
    replies = post.get("replyCount", 0)

    # Check if this is a repost
    reason = item.get("reason", {})
    repost_note = ""
    if reason.get("$type") == "app.bsky.feed.defs#reasonRepost":
        repost_by = reason.get("by", {}).get("handle", "someone")
        repost_note = f"  (reposted by @{repost_by})\n"

    return f"@{handle} - {created_at}\n{repost_note}{text}\n[{likes} likes, {reposts} reposts, {replies} replies]"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    actor = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    filter_type = sys.argv[3] if len(sys.argv) > 3 else "posts_no_replies"

    try:
        result = get_author_feed(actor, limit, filter_type)
        feed = result.get("feed", [])

        if not feed:
            print(f"No posts found for: {actor}")
            return

        print(f"Recent posts from @{actor} ({len(feed)} posts):\n")
        print("-" * 60)

        for item in feed:
            print(format_post(item))
            print("-" * 60)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
