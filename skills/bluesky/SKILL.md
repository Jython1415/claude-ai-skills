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

Search supports advanced query syntax:
- Basic terms: `python programming`
- Exact phrases: `"event sourcing"`
- User filter: `from:handle.bsky.social`
- Mentions: `mentions:handle.bsky.social`
- Date range: `since:2025-01-01 until:2025-06-01`
- Language: `lang:en`
- Hashtags: `#python`
- Domain links: `domain:github.com`

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
    params={"actor": "bsky.app", "limit": 10, "filter": "posts_no_replies"},
    timeout=30,
)
for item in response.json().get("feed", []):
    print(item["post"]["record"]["text"][:100])
```

Filter options for `getAuthorFeed`:
- `posts_with_replies` -- All posts including replies
- `posts_no_replies` -- Original posts only (default)
- `posts_with_media` -- Only posts with images/video
- `posts_and_author_threads` -- Posts and self-reply threads

### Get Post Thread

```python
response = requests.get(
    "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread",
    params={"uri": "at://did:plc:xxx/app.bsky.feed.post/yyy", "depth": 6},
    timeout=30,
)
thread = response.json()["thread"]
```

Accepts AT-URIs. To convert a bsky.app URL to an AT-URI, resolve the handle first:
```python
# Resolve handle -> DID
did = requests.get(
    "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle",
    params={"handle": "bsky.app"}, timeout=30,
).json()["did"]

# Build AT-URI: at://{did}/app.bsky.feed.post/{rkey}
```

### Get Trending Topics

```python
# Lightweight topic list (low token cost)
response = requests.get(
    "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrendingTopics",
    params={"limit": 10},
    timeout=30,
)
for topic in response.json().get("topics", []):
    print(topic["displayName"])

# Rich trends with post counts and top actors
response = requests.get(
    "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrends",
    params={"limit": 10},
    timeout=30,
)
for trend in response.json().get("trends", []):
    print(f"{trend['displayName']} -- {trend.get('postCount', 0)} posts")
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

This returns `session_id` and `proxy_url` -- set these as environment variables.

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
- `app.bsky.feed.searchPosts` -- Search posts (supports advanced query syntax)
- `app.bsky.feed.getAuthorFeed` -- Get user's posts (supports filter param)
- `app.bsky.feed.getPostThread` -- Get post with parent chain and replies
- `app.bsky.feed.getPosts` -- Get specific posts by URI
- `app.bsky.feed.getFeed` -- Get posts from a custom feed
- `app.bsky.feed.getListFeed` -- Get posts from a list
- `app.bsky.feed.getLikes` -- Get users who liked a post
- `app.bsky.feed.getRepostedBy` -- Get users who reposted a post
- `app.bsky.feed.getQuotes` -- Get posts that quote a specific post

### Actor Operations
- `app.bsky.actor.getProfile` -- Get user profile
- `app.bsky.actor.getProfiles` -- Get multiple profiles
- `app.bsky.actor.searchActors` -- Search for users

### Graph Operations
- `app.bsky.graph.getFollowers` -- Get followers (paginated, max 100 per page)
- `app.bsky.graph.getFollows` -- Get following (paginated, max 100 per page)

### Trending (Unspecced)
- `app.bsky.unspecced.getTrendingTopics` -- Lightweight trending topic list
- `app.bsky.unspecced.getTrends` -- Rich trends with post counts and actors

### Identity
- `com.atproto.identity.resolveHandle` -- Resolve handle to DID

## Write Endpoints (Require Proxy Auth)

These require a session via the credential proxy:

- `com.atproto.repo.createRecord` -- Create posts, likes, follows
- `com.atproto.repo.deleteRecord` -- Delete records
- `app.bsky.notification.updateSeen` -- Mark notifications read

## Rate Limits

### Bluesky API Rate Limits

Bluesky enforces rate limits at multiple levels. All limits are subject to change.

**Global (per IP):**
- 3,000 requests per 5 minutes (applies to all endpoints)

**Content writes (per account, points-based):**
- 5,000 points per hour / 35,000 points per day
- CREATE = 3 points, UPDATE = 2 points, DELETE = 1 point
- Approximately 1,666 record creations per hour

**AppView read endpoints** (search, feeds, profiles) have generous rate limits.
Contact Bluesky support if you encounter restrictions on read-heavy workloads.

**Specific endpoint limits (per account):**
- `createSession`: 30 per 5 minutes / 300 per day
- `updateHandle`: 10 per 5 minutes / 50 per day

### Credential Proxy Rate Limits

The proxy server applies its own rate limit of **300 requests per minute** per session.
This is well below Bluesky's 3,000/5min global limit and should not restrict
normal usage. If you hit the proxy limit before the Bluesky limit, the proxy
returns HTTP 429.

## Tips

- **Use the public API for reads.** No auth setup needed, better caching via `public.api.bsky.app`.
- **Pagination**: Endpoints returning lists support cursor-based pagination. Pass the `cursor` from the response as a query parameter to get the next page.
- **AT-URIs**: Many endpoints accept AT-URIs (`at://did:plc:xxx/collection/rkey`). Use `resolveHandle` to convert handles to DIDs when constructing URIs from bsky.app URLs.
- **Trending endpoints are "unspecced"**: `getTrendingTopics` and `getTrends` may change without notice. Use `getTrendingTopics` for a quick scan (lower token cost) and `getTrends` for detailed analysis.
- **Feed filters**: `getAuthorFeed` supports `filter` param to narrow results. Use `posts_no_replies` to skip reply noise, `posts_with_media` for visual content.

## Scripts

See the `scripts/` directory for ready-to-use Python scripts:

- `search_posts.py` -- Search Bluesky posts
- `get_profile.py` -- Get user profile information
- `get_author_feed.py` -- Get a user's recent posts with filtering
- `get_post_thread.py` -- Get a post thread with context and replies
- `get_trending.py` -- Get trending topics (lightweight or rich mode)
- `search_users.py` -- Search for users by name, handle, or bio

All scripts use the public API by default and require no authentication for read operations.
