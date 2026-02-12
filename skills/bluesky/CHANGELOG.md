# Changelog

All notable changes to the Bluesky Access skill will be documented in this file.

## [2.0.1] - 2026-02-12

### Changed
- Updated skill description to trigger on bsky.app URLs, preventing a wasted web_fetch round trip on Bluesky's JavaScript SPA

## [2.0.0] - 2026-02-12

### Added
- `bsky_sets.py` - Set-based operations on actor collections (follows, followers, likes, reposts) with Python set operators (`&`, `|`, `-`)
- `ActorSet` class with intersection, union, difference, membership test, sorting, and DID extraction
- `Actor` dataclass with `did`, `handle`, `display_name` fields
- `actors.follows()`, `actors.followers()`, `actors.likes()`, `actors.reposts()`, `actors.known_followers()` - paginated endpoint wrappers returning `ActorSet`
- `estimate_likes()`, `estimate_reposts()`, `estimate_followers()`, `estimate_follows()` - single-call count checks for cost-aware querying
- `paginate()` utility in `bsky_client` for automatic cursor-based pagination with configurable `max_items` and `page_size`
- Comprehensive tests for `bsky_sets` (set operations, normalization, producers, estimates) and `paginate()`

### Changed
- **BREAKING**: Removed all standalone scripts (`scripts/` directory). The skill is now library-first.
- Rewrote SKILL.md with graduated code examples (simple → complex) as the primary interface, replacing the script-based quick start table
- Endpoint reference condensed into compact grouped lists

### Migration
- Instead of `python get_profile.py bsky.app`, use `api.get("app.bsky.actor.getProfile", {"actor": "bsky.app"})`
- Instead of `python search_posts.py "query"`, use `api.get("app.bsky.feed.searchPosts", {"q": "query", "limit": 25})`
- See SKILL.md examples for all common patterns

## [1.3.0] - 2026-02-12

### Added
- `bsky_client.py` - Shared client module with automatic auth routing (public API vs credential proxy) based on endpoint classification
- `resolve_did_to_handle()` utility in `bsky_client` for DID-to-handle resolution
- Unit tests for `bsky_client` covering endpoint classification, routing logic, and utility functions
- Auth Routing section in SKILL.md documenting how the client auto-routes requests

### Changed
- Migrated all 8 scripts to use the shared `bsky_client` module instead of inline `requests` calls
- Consolidated duplicated `resolve_handle_to_did()` and `url_to_at_uri()` helpers (previously copied across 3 scripts) into `bsky_client`
- Removed auth branching boilerplate from `get_profile.py` and `search_posts.py` (now handled by the client)
- Updated Authenticated Operations section in SKILL.md to use `bsky_client` API
- Environment variables `SESSION_ID` and `PROXY_URL` are service-agnostic (one session can grant access to multiple services like bsky + gmail)

## [1.2.0] - 2026-02-11

### Added
- `resolve_url.py` - Resolve bsky.app URLs, handles, DIDs, and AT-URIs to structured identifiers (type, DID, handle, AT-URI, collection, rkey)
- `trace_quote_chain.py` - Trace quote-post chains backward to the original post, with cycle detection and deleted/blocked post handling
- Quick Start table in SKILL.md mapping tasks to scripts with example invocations
- Patterns & Recipes section in SKILL.md documenting URL resolution, quote-post traversal, and `getQuotes` endpoint
- Expanded Scripts section in SKILL.md with function signatures and CLI arguments for all 8 scripts

### Changed
- Restructured SKILL.md to put scripts and quick start first (before raw API reference) for better LLM agent discoverability
- Moved search query syntax and feed filter options into Patterns & Recipes section
- Condensed Public API section by removing inline Python code examples (scripts handle this)

## [1.1.0] - 2026-02-09

### Added
- `get_post_thread.py` - Fetch post threads with parent chain and replies, supports both AT-URIs and bsky.app URLs
- `get_trending.py` - Get trending topics in lightweight or rich mode (with post counts and top actors)
- `search_users.py` - Search for users by name, handle, or bio
- `get_author_feed.py` - Get a user's recent posts with filter support (media-only, no replies, etc.)
- Rate limit documentation in SKILL.md covering both Bluesky API limits and proxy limits
- Advanced search query syntax documentation (from:, mentions:, since:, domain:, etc.)
- Tips section in SKILL.md with pagination, AT-URI, and trending endpoint guidance

### Changed
- Expanded endpoint reference with feed engagement endpoints (getLikes, getRepostedBy, getQuotes), custom feed/list endpoints (getFeed, getListFeed), trending endpoints (getTrendingTopics, getTrends), and identity resolution (resolveHandle)
- Updated proxy rate limit from 60/min to 300/min to align with Bluesky's 3,000/5min global limit
- Added acknowledgment in CHANGELOG crediting this skill as being inspired by oaustegard's [browsing-bluesky](https://github.com/oaustegard/claude-skills/tree/main/browsing-bluesky) skill

## [1.0.0] - 2025-12-30

### Added
- Initial release of Bluesky Access skill
- `get_profile.py` - Fetch user profiles from Bluesky
- `search_posts.py` - Search posts on Bluesky
- Session-based credential management via proxy server
