#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
Resolve Bluesky URLs, handles, and DIDs to structured identifiers.

Uses the public API (no auth needed). Accepts bsky.app post URLs, profile
URLs, AT-URIs, handles, or DIDs and returns structured resolution data.

Usage:
    python resolve_url.py <url_handle_or_uri>

Examples:
    python resolve_url.py https://bsky.app/profile/bsky.app/post/3abc123
    python resolve_url.py https://bsky.app/profile/bsky.app
    python resolve_url.py at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3abc123
    python resolve_url.py bsky.app
    python resolve_url.py did:plc:z72i7hdynmk6r22z27h6tvur
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bsky_client import resolve_did_to_handle, resolve_handle_to_did


def resolve_url(identifier: str) -> dict:
    """
    Resolve a Bluesky identifier to structured data.

    Accepts:
        - bsky.app post URL: https://bsky.app/profile/handle/post/rkey
        - bsky.app profile URL: https://bsky.app/profile/handle
        - AT-URI: at://did:plc:xxx/app.bsky.feed.post/rkey
        - Handle: bsky.app
        - DID: did:plc:xxx

    Returns:
        dict with keys: type, did, handle, at_uri (if post), collection (if post), rkey (if post)
    """
    identifier = identifier.strip()

    # Post URL: https://bsky.app/profile/handle/post/rkey
    post_match = re.match(r"https://bsky\.app/profile/([^/]+)/post/([^/?#]+)", identifier)
    if post_match:
        actor, rkey = post_match.groups()
        if actor.startswith("did:"):
            did = actor
            handle = resolve_did_to_handle(did)
        else:
            handle = actor
            did = resolve_handle_to_did(actor)
        at_uri = f"at://{did}/app.bsky.feed.post/{rkey}"
        return {
            "type": "post",
            "did": did,
            "handle": handle,
            "at_uri": at_uri,
            "collection": "app.bsky.feed.post",
            "rkey": rkey,
        }

    # Profile URL: https://bsky.app/profile/handle
    profile_match = re.match(r"https://bsky\.app/profile/([^/]+?)/?$", identifier)
    if profile_match:
        actor = profile_match.group(1)
        if actor.startswith("did:"):
            did = actor
            handle = resolve_did_to_handle(did)
        else:
            handle = actor
            did = resolve_handle_to_did(actor)
        return {
            "type": "profile",
            "did": did,
            "handle": handle,
        }

    # AT-URI: at://did:plc:xxx/collection/rkey
    at_match = re.match(r"at://([^/]+)/([^/]+)/([^/?#]+)", identifier)
    if at_match:
        did, collection, rkey = at_match.groups()
        if not did.startswith("did:"):
            handle = did
            did = resolve_handle_to_did(did)
        else:
            handle = resolve_did_to_handle(did)
        return {
            "type": "post",
            "did": did,
            "handle": handle,
            "at_uri": identifier,
            "collection": collection,
            "rkey": rkey,
        }

    # DID: did:plc:xxx or did:web:xxx
    if identifier.startswith("did:"):
        handle = resolve_did_to_handle(identifier)
        return {
            "type": "profile",
            "did": identifier,
            "handle": handle,
        }

    # Bare handle (e.g., bsky.app)
    did = resolve_handle_to_did(identifier)
    return {
        "type": "profile",
        "did": did,
        "handle": identifier,
    }


def format_result(result: dict) -> str:
    """Format resolution result for display."""
    lines = [f"Type: {result['type']}"]
    lines.append(f"DID: {result['did']}")
    if result.get("handle"):
        lines.append(f"Handle: @{result['handle']}")
    if result.get("at_uri"):
        lines.append(f"AT-URI: {result['at_uri']}")
    if result.get("collection"):
        lines.append(f"Collection: {result['collection']}")
    if result.get("rkey"):
        lines.append(f"Record Key: {result['rkey']}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    identifier = sys.argv[1]

    try:
        result = resolve_url(identifier)
        print(format_result(result))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
