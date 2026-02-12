#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Trace a Bluesky quote-post chain back to the original post.

Uses the public API (no auth needed). Starts from a quote post and walks
backward through each quoted post until it reaches the origin (a post
that doesn't quote anything).

Usage:
    python trace_quote_chain.py <post_url_or_uri> [max_depth]

Examples:
    python trace_quote_chain.py https://bsky.app/profile/user.bsky.social/post/3abc123
    python trace_quote_chain.py at://did:plc:xxx/app.bsky.feed.post/3abc123 20
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bsky_client import api, url_to_at_uri


def fetch_post(uri: str) -> dict | None:
    """Fetch a single post by AT-URI. Returns None if not found."""
    posts = api.get("app.bsky.feed.getPosts", {"uris": [uri]}).get("posts", [])
    return posts[0] if posts else None


def extract_quoted_uri(post_view: dict) -> str | None:
    """Extract the AT-URI of the quoted post from a post's embed, if any.

    Handles both:
        - app.bsky.embed.record#view (plain quote)
        - app.bsky.embed.recordWithMedia#view (quote + media)

    Returns None if the post doesn't quote anything, or if the quoted
    post is deleted/blocked (#viewNotFound, #viewBlocked).
    """
    embed = post_view.get("embed")
    if not embed:
        return None

    embed_type = embed.get("$type", "")

    if embed_type == "app.bsky.embed.record#view":
        record = embed.get("record", {})
    elif embed_type == "app.bsky.embed.recordWithMedia#view":
        record = embed.get("record", {}).get("record", {})
    else:
        return None

    # Only follow actual post views, not deleted/blocked refs
    record_type = record.get("$type", "")
    if record_type in (
        "app.bsky.embed.record#viewNotFound",
        "app.bsky.embed.record#viewBlocked",
    ):
        return None

    return record.get("uri")


def trace_quote_chain(post_ref: str, max_depth: int = 50) -> list[dict]:
    """
    Trace a quote-post chain back to the origin.

    Starts from the given post and follows quoted posts backward until
    reaching a post that doesn't quote anything, hitting a deleted/blocked
    post, or reaching max_depth.

    Args:
        post_ref: AT-URI or bsky.app URL of the starting post
        max_depth: Maximum number of hops to follow (default 50)

    Returns:
        List of post views from start to origin (oldest last)
    """
    if post_ref.startswith("http"):
        uri = url_to_at_uri(post_ref)
    elif post_ref.startswith("at://"):
        uri = post_ref
    else:
        raise ValueError(f"Invalid post reference: {post_ref}")

    chain = []
    seen = set()

    for _ in range(max_depth):
        if uri in seen:
            break
        seen.add(uri)

        post = fetch_post(uri)
        if not post:
            break

        chain.append(post)

        quoted_uri = extract_quoted_uri(post)
        if not quoted_uri:
            break

        uri = quoted_uri

    return chain


def format_chain(chain: list[dict]) -> str:
    """Format a quote chain for display."""
    if not chain:
        return "No posts found."

    if len(chain) == 1:
        lines = ["This post does not quote another post.\n"]
        lines.append(format_post(chain[0], "SINGLE POST"))
        return "\n".join(lines)

    lines = [f"Quote chain: {len(chain)} posts (start -> origin)\n"]

    for i, post in enumerate(chain):
        if i == 0:
            label = "START"
        elif i == len(chain) - 1:
            label = "ORIGIN"
        else:
            label = f"QUOTED (depth {i})"

        lines.append(format_post(post, label))

        if i < len(chain) - 1:
            lines.append("  | quotes")
            lines.append("  v")
            lines.append("")

    return "\n".join(lines)


def format_post(post: dict, label: str) -> str:
    """Format a single post with a label."""
    author = post.get("author", {})
    handle = author.get("handle", "unknown")
    display_name = author.get("displayName", handle)
    record = post.get("record", {})
    text = record.get("text", "")
    created_at = record.get("createdAt", "")[:16]
    uri = post.get("uri", "")

    likes = post.get("likeCount", 0)
    reposts = post.get("repostCount", 0)
    replies = post.get("replyCount", 0)
    quotes = post.get("quoteCount", 0)

    lines = [
        f"[{label}]",
        f"  @{handle} ({display_name}) - {created_at}",
        f"  {text}",
        f"  [{likes} likes, {reposts} reposts, {replies} replies, {quotes} quotes]",
        f"  URI: {uri}",
    ]
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    post_ref = sys.argv[1]
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    try:
        chain = trace_quote_chain(post_ref, max_depth)
        print(format_chain(chain))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
