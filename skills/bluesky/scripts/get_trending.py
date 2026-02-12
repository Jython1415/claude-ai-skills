#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Get trending topics on Bluesky.

Uses the public API (no auth needed). Supports two modes:
- "topics" (default): Lightweight list of trending topic names
- "rich": Detailed trends with post counts, categories, and top actors

Usage:
    python get_trending.py [mode] [limit]

Examples:
    python get_trending.py
    python get_trending.py topics 10
    python get_trending.py rich 5
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bsky_client import api


def get_trending_topics(limit: int = 10) -> dict:
    """
    Get a lightweight list of trending topics.

    Args:
        limit: Maximum number of topics (1-25, default 10)

    Returns:
        Dict with 'topics' and 'suggested' lists
    """
    return api.get("app.bsky.unspecced.getTrendingTopics", {"limit": min(max(limit, 1), 25)})


def get_trends(limit: int = 10) -> dict:
    """
    Get rich trending data with post counts and top actors.

    Args:
        limit: Maximum number of trends (1-25, default 10)

    Returns:
        Dict with 'trends' list containing detailed trend objects
    """
    return api.get("app.bsky.unspecced.getTrends", {"limit": min(max(limit, 1), 25)})


def format_topic(topic: dict) -> str:
    """Format a trending topic for display."""
    name = topic.get("displayName") or topic.get("topic", "unknown")
    description = topic.get("description", "")
    link = topic.get("link", "")
    parts = [f"  {name}"]
    if description:
        parts.append(f"    {description}")
    if link:
        parts.append(f"    {link}")
    return "\n".join(parts)


def format_trend(trend: dict) -> str:
    """Format a rich trend for display."""
    name = trend.get("displayName") or trend.get("topic", "unknown")
    post_count = trend.get("postCount", 0)
    status = trend.get("status", "")
    category = trend.get("category", "")
    started_at = trend.get("startedAt", "")[:16]

    header = f"  {name} -- {post_count} posts"
    if status:
        header += f" ({status})"
    parts = [header]

    meta = []
    if category:
        meta.append(f"category: {category}")
    if started_at:
        meta.append(f"started: {started_at}")
    if meta:
        parts.append(f"    {', '.join(meta)}")

    actors = trend.get("actors", [])
    if actors:
        handles = [a.get("handle", "?") for a in actors[:3]]
        parts.append(f"    top accounts: {', '.join('@' + h for h in handles)}")

    return "\n".join(parts)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "topics"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    if mode not in ("topics", "rich"):
        print(f'Invalid mode: {mode}. Use "topics" or "rich".', file=sys.stderr)
        print(__doc__)
        sys.exit(1)

    try:
        if mode == "topics":
            result = get_trending_topics(limit)
            topics = result.get("topics", [])
            suggested = result.get("suggested", [])

            if topics:
                print(f"Trending Topics ({len(topics)}):\n")
                for topic in topics:
                    print(format_topic(topic))
                    print()

            if suggested:
                print(f"Suggested Topics ({len(suggested)}):\n")
                for topic in suggested:
                    print(format_topic(topic))
                    print()

            if not topics and not suggested:
                print("No trending topics found.")

        else:
            result = get_trends(limit)
            trends = result.get("trends", [])

            if not trends:
                print("No trends found.")
                return

            print(f"Trending on Bluesky ({len(trends)} trends):\n")
            for trend in trends:
                print(format_trend(trend))
                print()

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
