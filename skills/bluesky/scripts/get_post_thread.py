#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Get a Bluesky post thread with parent context and replies.

Uses the public API (no auth needed). Accepts either an AT-URI or a
bsky.app URL and resolves it automatically.

Usage:
    python get_post_thread.py <post_url_or_uri> [depth] [parent_height]

Examples:
    python get_post_thread.py https://bsky.app/profile/bsky.app/post/3abc123
    python get_post_thread.py at://did:plc:xxx/app.bsky.feed.post/3abc123 10 5
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bsky_client import api, url_to_at_uri


def get_post_thread(post_ref: str, depth: int = 6, parent_height: int = 80) -> dict:
    """
    Get a post thread with parent chain and replies.

    Args:
        post_ref: AT-URI or bsky.app URL of the post
        depth: How many levels of replies to fetch (1-1000, default 6)
        parent_height: How many parent posts to fetch (1-1000, default 80)

    Returns:
        API response with thread structure
    """
    if post_ref.startswith("http"):
        uri = url_to_at_uri(post_ref)
    elif post_ref.startswith("at://"):
        uri = post_ref
    else:
        raise ValueError(f"Invalid post reference: {post_ref}")

    return api.get(
        "app.bsky.feed.getPostThread",
        {
            "uri": uri,
            "depth": min(max(depth, 0), 1000),
            "parentHeight": min(max(parent_height, 0), 1000),
        },
    )


def format_post(post_data: dict, indent: int = 0) -> str:
    """Format a single post for display."""
    post = post_data.get("post", post_data)
    author = post.get("author", {})
    handle = author.get("handle", "unknown")
    display_name = author.get("displayName", handle)
    record = post.get("record", {})
    text = record.get("text", "")
    created_at = record.get("createdAt", "")[:16]

    likes = post.get("likeCount", 0)
    reposts = post.get("repostCount", 0)
    replies = post.get("replyCount", 0)

    prefix = "  " * indent
    lines = [
        f"{prefix}@{handle} ({display_name}) - {created_at}",
        f"{prefix}{text}",
        f"{prefix}[{likes} likes, {reposts} reposts, {replies} replies]",
    ]
    return "\n".join(lines)


def format_thread(thread: dict, indent: int = 0) -> str:
    """Recursively format a thread for display."""
    parts = []

    # Show parent chain first (recursively)
    if "parent" in thread:
        parent = thread["parent"]
        if parent.get("$type") == "app.bsky.feed.defs#threadViewPost":
            parts.append(format_thread(parent, indent))
            parts.append("  " * indent + "  |")

    # Show the main post
    if "post" in thread:
        parts.append(format_post(thread, indent))

    # Show replies
    for reply in thread.get("replies", []):
        if reply.get("$type") == "app.bsky.feed.defs#threadViewPost":
            parts.append("")
            parts.append(format_thread(reply, indent + 1))

    return "\n".join(parts)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    post_ref = sys.argv[1]
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    parent_height = int(sys.argv[3]) if len(sys.argv) > 3 else 80

    try:
        result = get_post_thread(post_ref, depth, parent_height)
        thread = result.get("thread", {})

        if not thread:
            print("Thread not found.")
            return

        print(format_thread(thread))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
