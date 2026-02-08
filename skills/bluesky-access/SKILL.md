---
name: bluesky-access
description: Search and interact with Bluesky/ATProtocol via credential proxy
---

# Bluesky Access Skill

Access Bluesky (ATProtocol) APIs through the credential proxy. Credentials are managed server-side - no tokens appear in Claude's context.

## Prerequisites

1. **MCP Custom Connector**: Add the credential proxy MCP server as a custom connector in Claude.ai
2. **Bluesky Credentials**: Configured on the proxy server in `credentials.json`

## Setup

Before using this skill, create a session using the MCP tools:

```
Use create_session with services: ["bsky"]
```

This returns `session_id` and `proxy_url` (a public HTTPS URL via Cloudflare Tunnel, e.g., `https://proxy.joshuashew.com`) - set these as environment variables for scripts.

## Environment Variables

Scripts expect these environment variables (provided by MCP session):

| Variable | Description |
|----------|-------------|
| `SESSION_ID` | Session ID from create_session |
| `PROXY_URL` | Public proxy URL from create_session (Cloudflare Tunnel URL) |

## Usage Examples

### Search Posts

```python
import os
import requests

SESSION_ID = os.environ['SESSION_ID']
PROXY_URL = os.environ['PROXY_URL']

response = requests.get(
    f"{PROXY_URL}/proxy/bsky/app.bsky.feed.searchPosts",
    params={"q": "python programming", "limit": 25},
    headers={"X-Session-Id": SESSION_ID}
)

for post in response.json().get("posts", []):
    author = post["author"]["handle"]
    text = post["record"]["text"][:100]
    print(f"@{author}: {text}")
```

### Get User Profile

```python
response = requests.get(
    f"{PROXY_URL}/proxy/bsky/app.bsky.actor.getProfile",
    params={"actor": "bsky.app"},
    headers={"X-Session-Id": SESSION_ID}
)
print(response.json())
```

### Get User Feed

```python
response = requests.get(
    f"{PROXY_URL}/proxy/bsky/app.bsky.feed.getAuthorFeed",
    params={"actor": "bsky.app", "limit": 10},
    headers={"X-Session-Id": SESSION_ID}
)
for item in response.json().get("feed", []):
    print(item["post"]["record"]["text"][:100])
```

## Available Endpoints

All ATProtocol endpoints are available via `/proxy/bsky/<endpoint>`. Common ones:

### Feed Operations
- `app.bsky.feed.searchPosts` - Search posts
- `app.bsky.feed.getAuthorFeed` - Get user's posts
- `app.bsky.feed.getTimeline` - Get home timeline
- `app.bsky.feed.getPostThread` - Get post with replies
- `app.bsky.feed.getPosts` - Get specific posts by URI

### Actor Operations
- `app.bsky.actor.getProfile` - Get user profile
- `app.bsky.actor.getProfiles` - Get multiple profiles
- `app.bsky.actor.searchActors` - Search for users

### Graph Operations
- `app.bsky.graph.getFollowers` - Get followers
- `app.bsky.graph.getFollows` - Get following
- `app.bsky.graph.getBlocks` - Get blocked accounts
- `app.bsky.graph.getMutes` - Get muted accounts

### Notification Operations
- `app.bsky.notification.listNotifications` - List notifications

## Security

- Bluesky credentials (app password) stay on the proxy server
- Sessions expire automatically (default 30 minutes)
- Sessions can be revoked early via `revoke_session` MCP tool
- Only ATProtocol endpoints are accessible (not arbitrary URLs)

## Scripts

See the `scripts/` directory for ready-to-use Python scripts:

- `search_posts.py` - Search Bluesky posts
- `get_profile.py` - Get user profile information
