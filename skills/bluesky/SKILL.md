---
name: bluesky
description: Search and interact with Bluesky/ATProtocol. Public API for reads (no auth needed), credential proxy for writes.
---

# Bluesky Skill

Access Bluesky (ATProtocol) APIs. Read operations use the public API directly (no authentication needed). Write operations use the credential proxy.

## Public API (No Auth Required)

The public API at `https://public.api.bsky.app/xrpc` supports all read operations without authentication.

### Search Posts

```python
import requests

response = requests.get(
    "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
    params={"q": "python programming", "limit": 25},
    timeout=30,
)

for post in response.json().get("posts", []):
    author = post["author"]["handle"]
    text = post["record"]["text"][:100]
    print(f"@{author}: {text}")
```

### Get User Profile

```python
response = requests.get(
    "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile",
    params={"actor": "bsky.app"},
    timeout=30,
)
print(response.json())
```

### Get User Feed

```python
response = requests.get(
    "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
    params={"actor": "bsky.app", "limit": 10},
    timeout=30,
)
for item in response.json().get("feed", []):
    print(item["post"]["record"]["text"][:100])
```

## Authenticated Operations (Via Proxy)

Write operations (posting, liking, following, etc.) require authentication via the credential proxy.

### Setup

1. **MCP Custom Connector**: Add the credential proxy MCP server as a custom connector in Claude.ai
2. **Bluesky Credentials**: Configured on the proxy server in `credentials.json`

Create a session:
```
Use create_session with services: ["bsky"]
```

This returns `session_id` and `proxy_url` — set these as environment variables.

### Create a Post

```python
import os
import requests

SESSION_ID = os.environ["SESSION_ID"]
PROXY_URL = os.environ["PROXY_URL"]

response = requests.post(
    f"{PROXY_URL}/proxy/bsky/com.atproto.repo.createRecord",
    json={
        "repo": "your-did-here",
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": "Hello from Claude!",
            "createdAt": "2024-01-01T00:00:00.000Z"
        }
    },
    headers={"X-Session-Id": SESSION_ID},
    timeout=30,
)
```

## Available Read Endpoints (Public API)

All these work without authentication via `https://public.api.bsky.app/xrpc/`:

### Feed Operations
- `app.bsky.feed.searchPosts` — Search posts
- `app.bsky.feed.getAuthorFeed` — Get user's posts
- `app.bsky.feed.getPostThread` — Get post with replies
- `app.bsky.feed.getPosts` — Get specific posts by URI

### Actor Operations
- `app.bsky.actor.getProfile` — Get user profile
- `app.bsky.actor.getProfiles` — Get multiple profiles
- `app.bsky.actor.searchActors` — Search for users

### Graph Operations
- `app.bsky.graph.getFollowers` — Get followers
- `app.bsky.graph.getFollows` — Get following

## Write Endpoints (Require Proxy Auth)

These require a session via the credential proxy:

- `com.atproto.repo.createRecord` — Create posts, likes, follows
- `com.atproto.repo.deleteRecord` — Delete records
- `app.bsky.notification.updateSeen` — Mark notifications read

## Scripts

See the `scripts/` directory for ready-to-use Python scripts:

- `search_posts.py` — Search Bluesky posts (uses public API, falls back to proxy)
- `get_profile.py` — Get user profile information (uses public API, falls back to proxy)
