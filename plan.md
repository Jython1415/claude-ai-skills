# Implementation Plan: Issue #90 — Shared `bsky_client` Module

## Summary

Create a shared `bsky_client.py` module that abstracts auth routing (public API vs credential proxy) behind a single `api.get()` call, consolidates duplicated helpers, and classifies every Bluesky endpoint by auth requirement. Migrate all 8 existing scripts to use it.

## Decisions (confirmed with user)

- **Import style**: `sys.path` insert in each script (2 lines)
- **Migration scope**: All 8 scripts
- **Utilities**: Consolidate `resolve_handle_to_did` and `url_to_at_uri` into `bsky_client`
- **Env vars**: Keep `SESSION_ID` and `PROXY_URL` (not `BSKY_`-prefixed) because sessions are service-agnostic — one session can grant access to multiple skills (e.g., Gmail + Bluesky)

## Steps

### Step 1: Create `skills/bluesky/bsky_client.py`

New file with these components:

**a) Constants and config**
- `PUBLIC_API = "https://public.api.bsky.app/xrpc"`
- `DEFAULT_TIMEOUT = 30`

**b) Endpoint metadata registry**

A dict classifying endpoints into four categories:
- `public_only` — Never needs auth (resolveHandle, getProfile, searchPosts, searchActors, getAuthorFeed, getPostThread, getPosts, getTrendingTopics, getTrends)
- `public_default` — Works unauthenticated with complete results; use public API even when session exists (getLikes, getFollows, getFollowers, getRepostedBy, listRecords)
- `auth_preferred` — Works unauthenticated but returns incomplete/empty data; route through proxy when session available, warn when not (getKnownFollowers)
- `auth_required` — Always requires proxy (getTimeline, getActorLikes, getBookmarks, notification endpoints, all write operations via `com.atproto.repo.*`)

The registry maps NSID strings (e.g., `"app.bsky.feed.getLikes"`) to their category. Unknown endpoints default to `auth_required` (fail-safe).

**c) Custom exceptions**
- `AuthRequiredError(endpoint)` — Raised when an `auth_required` or `auth_preferred` endpoint is called without session credentials
- `AuthRecommendedWarning` — Warning (via `warnings.warn`) for `auth_preferred` endpoints when session is missing

**d) `api.get(endpoint, params=None)` function**

Core routing logic:
1. Look up endpoint in the metadata registry
2. Read `SESSION_ID` and `PROXY_URL` from `os.environ`
3. Route based on category:
   - `public_only` / `public_default` → always use public API
   - `auth_preferred` → use proxy if session available, otherwise raise `AuthRequiredError`
   - `auth_required` → use proxy, raise `AuthRequiredError` if no session
4. Make `requests.get()` with appropriate URL and headers
5. Call `response.raise_for_status()` and return `response.json()`

Proxy requests go to `{PROXY_URL}/proxy/bsky/{endpoint}` with header `X-Session-Id: {SESSION_ID}`.

**e) `api.post(endpoint, json=None)` function**

Same routing logic as `api.get()` but uses `requests.post()`. All write endpoints are `auth_required`.

**f) Shared utility functions**
- `resolve_handle_to_did(handle)` — Resolve a handle to a DID via `com.atproto.identity.resolveHandle` (uses `api.get` internally)
- `url_to_at_uri(url)` — Parse a `bsky.app` post URL into an `at://` URI (calls `resolve_handle_to_did` for the DID lookup)

### Step 2: Migrate all 8 scripts

Each script gets these changes:

**a) Add `sys.path` insert (2 lines at top, after PEP 723 block)**
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

**b) Replace direct API calls with `bsky_client`**
- Remove `PUBLIC_API` constant
- Remove inline `requests.get(f"{PUBLIC_API}/...")` calls
- Replace with `from bsky_client import api` and `api.get("endpoint.name", params)`
- Remove `os` import if it was only used for env vars (auth routing is now in the client)

**c) Remove duplicated helpers**
- `get_post_thread.py`: Remove `resolve_handle_to_did`, `url_to_at_uri` → import from `bsky_client`
- `trace_quote_chain.py`: Remove `resolve_handle_to_did`, `url_to_at_uri` → import from `bsky_client`
- `resolve_url.py`: Remove `resolve_handle_to_did` → import from `bsky_client`

**d) Remove auth branching from get_profile.py and search_posts.py**
- Delete the `if session_id and proxy_url:` / `else:` pattern
- Replace with a single `api.get(...)` call (the client handles routing)

**e) Keep formatting functions and main() in each script**
- These are script-specific (different signatures, different output formats)
- No change needed

### Step 3: Add tests for `bsky_client`

Create `tests/test_bsky_client.py` with unit tests:

- **Endpoint classification tests**: Verify known endpoints are in the right category
- **Routing tests** (mock `requests.get`):
  - `public_only` endpoint → calls public API URL regardless of env vars
  - `public_default` endpoint → calls public API URL even when session exists
  - `auth_preferred` endpoint with session → calls proxy URL
  - `auth_preferred` endpoint without session → raises `AuthRequiredError`
  - `auth_required` endpoint with session → calls proxy URL
  - `auth_required` endpoint without session → raises `AuthRequiredError`
  - Unknown endpoint without session → raises `AuthRequiredError` (fail-safe)
- **Utility tests** (mock API responses):
  - `resolve_handle_to_did` returns DID from API response
  - `url_to_at_uri` parses various URL formats correctly

### Step 4: Update `skills/bluesky/SKILL.md`

- **Quick Start section**: Update to mention that scripts auto-route through the proxy when `SESSION_ID` and `PROXY_URL` env vars are set
- **Authenticated Operations section**: Expand with clear env var setup instructions:
  ```
  export SESSION_ID=<from create_session>
  export PROXY_URL=<from create_session>
  ```
- **Add "Auth Routing" section**: Brief explanation of the four endpoint categories and how the client auto-routes
- **Remove any per-script auth documentation** that is now handled by the client

### Step 5: Update CHANGELOG.md and VERSION

- Bump VERSION from `1.2.0` to `1.3.0` (new feature: shared client module)
- Add CHANGELOG entry for 1.3.0 describing the new `bsky_client` module, auth routing abstraction, and utility consolidation

## Files changed

| File | Action |
|------|--------|
| `skills/bluesky/bsky_client.py` | **Create** — shared client module |
| `skills/bluesky/scripts/get_profile.py` | Edit — use bsky_client, remove auth branching |
| `skills/bluesky/scripts/search_posts.py` | Edit — use bsky_client, remove auth branching |
| `skills/bluesky/scripts/get_post_thread.py` | Edit — use bsky_client, remove duplicated helpers |
| `skills/bluesky/scripts/trace_quote_chain.py` | Edit — use bsky_client, remove duplicated helpers |
| `skills/bluesky/scripts/resolve_url.py` | Edit — use bsky_client, remove duplicated helper |
| `skills/bluesky/scripts/get_author_feed.py` | Edit — use bsky_client |
| `skills/bluesky/scripts/search_users.py` | Edit — use bsky_client |
| `skills/bluesky/scripts/get_trending.py` | Edit — use bsky_client |
| `tests/test_bsky_client.py` | **Create** — unit tests for the client |
| `skills/bluesky/SKILL.md` | Edit — document auth routing |
| `skills/bluesky/CHANGELOG.md` | Edit — add 1.3.0 entry |
| `skills/bluesky/VERSION` | Edit — bump to 1.3.0 |

## Risks and mitigations

1. **`sys.path` insert fragility**: If scripts are moved to a different directory, the relative path breaks. Mitigated by using `Path(__file__).resolve().parent.parent` which is robust to symlinks and always resolves to `skills/bluesky/`.

2. **Endpoint misclassification**: If an endpoint is wrongly categorized (e.g., `auth_preferred` listed as `public_default`), results could be silently wrong. Mitigated by defaulting unknown endpoints to `auth_required` (fail-safe) and adding comments noting the source/rationale for each classification.

3. **CI coverage gap**: The CI workflow only covers `--cov=server --cov=mcp`. The new `tests/test_bsky_client.py` will run (it's in `tests/`) but coverage won't be reported for `skills/`. This is acceptable — the tests validate behavior via mocked requests, not coverage metrics.
