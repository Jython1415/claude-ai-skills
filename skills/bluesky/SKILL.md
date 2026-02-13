---
name: bluesky
description: Search and interact with Bluesky/ATProtocol. Always use this skill when encountering bsky.app URLs — web_fetch cannot render Bluesky's JavaScript SPA. Use for resolving posts, threads, quote chains, profiles, and search. Public API for reads (no auth needed), credential proxy for writes.
---

# Bluesky Skill

Access Bluesky (ATProtocol) APIs via two Python libraries:

- **`bsky_client`** -- Low-level API client with automatic auth routing
- **`bsky_sets`** -- Set-based operations on actor collections (follows, followers, likes, reposts)

Read operations use the public API directly (no authentication needed). Write operations use the credential proxy.

## Setup

Both modules live alongside this file. Add the skill directory to `sys.path`:

```python
import sys
sys.path.insert(0, "/path/to/skills/bluesky")
```

Public read operations (profiles, search, feeds, trending) work immediately with no further setup.

### Authenticated operations

For writes (posting, liking, following), timeline, notifications, known_followers, and other auth-required endpoints, create a session first using the `create_session` MCP tool:

```
create_session(services=["bsky"], ttl_minutes=30)
```

Then set the returned values as environment variables so the client can route through the credential proxy:

```python
import os
os.environ["SESSION_ID"] = "<session_id from create_session>"
os.environ["PROXY_URL"] = "<proxy_url from create_session>"
```

Once set, `api.get()` and `api.post()` automatically route auth-required endpoints through the proxy. No additional configuration is needed -- the client handles the routing.

Sessions are service-agnostic -- one session can grant access to multiple services (e.g., `["bsky", "gmail"]`). Sessions expire after the specified TTL (default 30 minutes).

## Examples

### Get a user's profile

```python
from bsky_client import api

profile = api.get("app.bsky.actor.getProfile", {"actor": "bsky.app"})
print(f"{profile['displayName']} (@{profile['handle']})")
print(f"Followers: {profile['followersCount']} | Following: {profile['followsCount']}")
if profile.get("description"):
    print(profile["description"])
```

### Search posts

```python
from bsky_client import api

data = api.get("app.bsky.feed.searchPosts", {"q": "python programming", "limit": 10})
for post in data["posts"]:
    author = post["author"]
    print(f"@{author['handle']}: {post['record']['text'][:100]}")
    print(f"  Likes: {post.get('likeCount', 0)} | Reposts: {post.get('repostCount', 0)}")
```

### Get a post thread

```python
from bsky_client import api, url_to_at_uri

uri = url_to_at_uri("https://bsky.app/profile/bsky.app/post/3abc123")
data = api.get("app.bsky.feed.getPostThread", {"uri": uri, "depth": 6})

thread = data["thread"]
post = thread["post"]
print(f"@{post['author']['handle']}: {post['record']['text']}")
for reply in thread.get("replies", []):
    r = reply["post"]
    print(f"  @{r['author']['handle']}: {r['record']['text'][:80]}")
```

### Resolve any Bluesky identifier

```python
from bsky_client import api, resolve_handle_to_did, url_to_at_uri

# Handle -> DID
did = resolve_handle_to_did("bsky.app")

# bsky.app URL -> AT-URI
uri = url_to_at_uri("https://bsky.app/profile/bsky.app/post/3abc123")

# AT-URI -> post data
data = api.get("app.bsky.feed.getPosts", {"uris": [uri]})
```

### Paginate through all results

```python
from bsky_client import paginate

# Fetch all followers (handles pagination automatically)
all_followers = paginate(
    "app.bsky.graph.getFollowers",
    {"actor": "bsky.app"},
    "followers",
)
print(f"Total followers fetched: {len(all_followers)}")

# Cap at 500 to limit API calls
sample = paginate(
    "app.bsky.feed.getLikes",
    {"uri": "at://did:plc:xxx/app.bsky.feed.post/yyy"},
    "likes",
    max_items=500,
)
```

### Cross-reference actor collections (set operations)

```python
from bsky_sets import actors, estimate_likes

# Who do I follow that liked this post?
my_follows = actors.follows("joshuashew.bsky.social")
post_likers = actors.likes("at://did:plc:xxx/app.bsky.feed.post/yyy")

mutual = my_follows & post_likers
print(f"{len(mutual)} of your follows liked this post:")
for a in mutual.sorted("display_name"):
    print(f"  {a.display_name} (@{a.handle})")
```

### Check feasibility before large fetches

```python
from bsky_sets import actors, estimate_likes, estimate_followers

# Check how many likes before committing to pagination
count = estimate_likes("at://did:plc:xxx/app.bsky.feed.post/yyy")
print(f"This post has {count} likes")

if count > 5000:
    # Fetch only first 1000 (default cap for likes/reposts)
    likers = actors.likes(uri)
else:
    # Fetch all
    likers = actors.likes(uri, max=None)
```

### Find mutual followers between two accounts

```python
from bsky_sets import actors

a_followers = actors.followers("alice.bsky.social")
b_followers = actors.followers("bob.bsky.social")

# People who follow both
shared = a_followers & b_followers
print(f"{len(shared)} accounts follow both:")
for a in shared.sorted("handle"):
    print(f"  @{a.handle}")

# People who follow Alice but not Bob
alice_only = a_followers - b_followers
print(f"{len(alice_only)} follow only Alice")
```

### Followers who engage: find followers that liked a post

```python
from bsky_sets import actors

followers = actors.followers("creator.bsky.social", max=5000)
likers = actors.likes("at://did:plc:xxx/app.bsky.feed.post/yyy")

engaged = followers & likers
print(f"{len(engaged)}/{len(followers)} followers liked the post ({len(engaged)/len(followers):.0%})")
```

### Create a post (authenticated)

```python
from bsky_client import api
from datetime import datetime, timezone

# Requires SESSION_ID and PROXY_URL (see "Authenticated operations" above)
result = api.post("com.atproto.repo.createRecord", {
    "repo": "your-did-here",
    "collection": "app.bsky.feed.post",
    "record": {
        "$type": "app.bsky.feed.post",
        "text": "Hello from Claude!",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
})
print(f"Posted: {result['uri']}")
```

### Get trending topics

```python
from bsky_client import api

# Lightweight topic list
topics = api.get("app.bsky.unspecced.getTrendingTopics", {"limit": 10})
for t in topics.get("topics", []):
    print(f"#{t['topic']} - {t.get('displayName', t['topic'])}")

# Rich trends with post counts
trends = api.get("app.bsky.unspecced.getTrends", {"limit": 5})
for t in trends.get("trends", []):
    print(f"{t.get('displayName', t['topic'])}: {t.get('postCount', '?')} posts")
```

## API Reference

### `bsky_client` -- Low-level API client

**Auth Routing:**
- **Public endpoints** (profiles, search, feeds, trending) always use `https://public.api.bsky.app/xrpc/` -- no auth needed.
- **Auth-required endpoints** (timeline, notifications, writes) route through the credential proxy when `SESSION_ID` and `PROXY_URL` are set.
- **Unknown endpoints** default to auth-required (fail-safe).

**Functions:**

| Function | Description |
|----------|-------------|
| `api.get(endpoint, params)` | GET request, auto-routed by endpoint classification |
| `api.post(endpoint, json)` | POST request, always through proxy (requires auth) |
| `paginate(endpoint, params, result_key, *, max_items, page_size)` | Fetch all pages from a paginated endpoint |
| `resolve_handle_to_did(handle)` | Resolve a handle to a DID |
| `resolve_did_to_handle(did)` | Resolve a DID to a handle (returns None on failure) |
| `url_to_at_uri(url)` | Convert a bsky.app post URL to an AT-URI |

### `bsky_sets` -- Actor collections with set operations

**Actor producers** (all return `ActorSet`):

| Function | Endpoint | Auth? | Default `max` |
|----------|----------|-------|---------------|
| `actors.follows(actor, *, max)` | getFollows | No | None (all) |
| `actors.followers(actor, *, max)` | getFollowers | No | None (all) |
| `actors.likes(uri, *, max)` | getLikes | No | 1000 |
| `actors.reposts(uri, *, max)` | getRepostedBy | No | 1000 |
| `actors.known_followers(actor, *, max)` | getKnownFollowers | **Yes** | None (all) |

Likes and reposts default to `max=1000` because popular posts can have tens of thousands. Use `estimate_likes(uri)` or `estimate_reposts(uri)` to check the count first, then pass `max=None` for a full fetch.

**Estimation helpers** (single API call each):

| Function | Description |
|----------|-------------|
| `estimate_likes(uri)` | Like count for a post |
| `estimate_reposts(uri)` | Repost count for a post |
| `estimate_followers(actor)` | Follower count for an actor |
| `estimate_follows(actor)` | Follows count for an actor |

**ActorSet operations:**

| Operation | Description |
|-----------|-------------|
| `a & b` | Intersection -- actors in both sets |
| `a \| b` | Union -- actors in either set |
| `a - b` | Difference -- actors in a but not b |
| `actor in s` | Membership test (accepts Actor or DID string) |
| `len(s)` | Count of actors |
| `for a in s` | Iterate over Actor objects |
| `s.sorted("handle")` | Sorted list by handle or display_name |
| `s.dids` | Set of DID strings |

**Actor fields:** `did`, `handle`, `display_name`

## Search Query Syntax

For `app.bsky.feed.searchPosts`:

- Basic terms: `python programming`
- Exact phrases: `"event sourcing"`
- User filter: `from:handle.bsky.social`
- Mentions: `mentions:handle.bsky.social`
- Date range: `since:2025-01-01 until:2025-06-01`
- Language: `lang:en`
- Hashtags: `#python`
- Domain links: `domain:github.com`

## Feed Filter Options

For `app.bsky.feed.getAuthorFeed` (pass as `filter` param):

- `posts_with_replies` -- All posts including replies
- `posts_no_replies` -- Original posts only (default)
- `posts_with_media` -- Only posts with images/video
- `posts_and_author_threads` -- Posts and self-reply threads

## Available Endpoints

The lists below cover common endpoints. For the full API reference with parameters, response schemas, and examples, see the [Bluesky HTTP API Reference](https://docs.bsky.app/docs/category/http-reference).

Individual endpoint docs are at `https://docs.bsky.app/docs/api/{slug}` where the slug is formed by replacing dots with hyphens and converting camelCase to kebab-case. Examples:

| Endpoint NSID | Documentation URL |
|---|---|
| `app.bsky.feed.getTimeline` | [app-bsky-feed-get-timeline](https://docs.bsky.app/docs/api/app-bsky-feed-get-timeline) |
| `com.atproto.repo.createRecord` | [com-atproto-repo-create-record](https://docs.bsky.app/docs/api/com-atproto-repo-create-record) |
| `app.bsky.graph.muteActor` | [app-bsky-graph-mute-actor](https://docs.bsky.app/docs/api/app-bsky-graph-mute-actor) |

Any XRPC endpoint can be called via `api.get()` or `api.post()` — the libraries are not limited to the endpoints listed here.

### Public Read Endpoints (No Auth)

All these work without authentication via `https://public.api.bsky.app/xrpc/`:

**Feed:** searchPosts, getAuthorFeed, getPostThread, getPosts, getQuotes, getFeed, getListFeed, getLikes, getRepostedBy, getActorFeeds, getFeedGenerator, getFeedGenerators, getSuggestedFeeds, describeFeedGenerator

**Actors:** getProfile, getProfiles, searchActors, searchActorsTypeahead, getSuggestions

**Graph:** getFollowers, getFollows, getRelationships, getSuggestedFollowsByActor, getList, getLists, getStarterPack, getStarterPacks, getActorStarterPacks, searchStarterPacks

**Trending:** getTrendingTopics, getTrends, getPopularFeedGenerators, getTaggedSuggestions

**Identity:** resolveHandle | **Repository:** describeRepo, getRecord, listRecords | **Labels:** queryLabels | **Labeler:** getServices

### Authenticated Read Endpoints (Require Proxy)

Feed: getTimeline, getActorLikes | Notifications: listNotifications, getUnreadCount | Graph: getBlocks, getMutes, getListBlocks, getListMutes, getKnownFollowers, getListsWithMembership, getStarterPacksWithMembership | Account: getPreferences, getBookmarks

### Write Endpoints (Require Proxy)

Records: createRecord, deleteRecord, putRecord, applyWrites, uploadBlob | Account: putPreferences, createBookmark, deleteBookmark | Notifications: updateSeen, registerPush, putPreferences | Graph mutations: muteActor, unmuteActor, muteActorList, unmuteActorList, muteThread, unmuteThread | Moderation: createReport

### Write Operations Quick Reference

Most write operations go through [`com.atproto.repo.createRecord`](https://docs.bsky.app/docs/api/com-atproto-repo-create-record) or [`com.atproto.repo.deleteRecord`](https://docs.bsky.app/docs/api/com-atproto-repo-delete-record). The table below shows the record schemas for common actions.

**createRecord** — `api.post("com.atproto.repo.createRecord", body)`

| Action | `collection` | `record` fields | Notes |
|--------|-------------|-----------------|-------|
| **Post** | `app.bsky.feed.post` | `text`, `createdAt`, optional `embed`, `facets`, `reply` | See [creating a post](https://docs.bsky.app/docs/tutorials/creating-a-post) for embeds and rich text |
| **Like** | `app.bsky.feed.like` | `subject: {uri, cid}`, `createdAt` | `subject` is a strong ref — get `uri` and `cid` from the post object |
| **Repost** | `app.bsky.feed.repost` | `subject: {uri, cid}`, `createdAt` | Same strong ref as like |
| **Follow** | `app.bsky.graph.follow` | `subject: "<did>"`, `createdAt` | `subject` is a DID string, not a strong ref |
| **Block** | `app.bsky.graph.block` | `subject: "<did>"`, `createdAt` | Same shape as follow |
| **List item** | `app.bsky.graph.listitem` | `subject: "<did>"`, `list: "<at-uri>"`, `createdAt` | Adds an actor to a list |

All `createRecord` calls require `repo` (your DID) and `collection` at the top level. Response: `{uri, cid}`.

**deleteRecord** — `api.post("com.atproto.repo.deleteRecord", body)` ([docs](https://docs.bsky.app/docs/api/com-atproto-repo-delete-record))

Body: `{repo, collection, rkey}` — extract `rkey` from the record's AT-URI (the last path segment).

**uploadBlob** — `api.post("com.atproto.repo.uploadBlob", image_bytes)` ([docs](https://docs.bsky.app/docs/api/com-atproto-repo-upload-blob))

Send raw bytes with `Content-Type` set to the MIME type (e.g., `image/png`). Returns a `blob` object to embed in a post record. Max image size: 1 MB.

**Graph mutations** (simple POST, no createRecord needed):

| Endpoint | Body | Docs |
|----------|------|------|
| `app.bsky.graph.muteActor` | `{actor}` | [docs](https://docs.bsky.app/docs/api/app-bsky-graph-mute-actor) |
| `app.bsky.graph.unmuteActor` | `{actor}` | [docs](https://docs.bsky.app/docs/api/app-bsky-graph-unmute-actor) |
| `app.bsky.graph.muteThread` | `{root}` | [docs](https://docs.bsky.app/docs/api/app-bsky-graph-mute-thread) |
| `app.bsky.graph.unmuteThread` | `{root}` | [docs](https://docs.bsky.app/docs/api/app-bsky-graph-unmute-thread) |

`actor` accepts a DID or handle. `root` is an AT-URI of the thread root post.

## Rate Limits

**Bluesky API (per IP):** 3,000 requests per 5 minutes. Read endpoints have generous limits; contact Bluesky support for heavy read workloads.

**Content writes (per account):** 5,000 points/hour, 35,000 points/day. CREATE = 3 pts, UPDATE = 2 pts, DELETE = 1 pt.

**Credential proxy:** 300 requests/minute per session.

**Pagination cost guide:** 100 items/page. 2,000 follows = 20 API calls. 50,000 likes = 500 calls (~2 min wall time). Use `estimate_*` functions and `max` parameter to control costs.

## Reporting Issues

Encountered a problem or have a suggestion? Use the `report_skill_issue` MCP tool to submit a bug report or enhancement request.
