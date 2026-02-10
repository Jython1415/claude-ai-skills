# Changelog

All notable changes to the Bluesky Access skill will be documented in this file.

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

## [1.0.0] - 2025-12-30

### Added
- Initial release of Bluesky Access skill
- `get_profile.py` - Fetch user profiles from Bluesky
- `search_posts.py` - Search posts on Bluesky
- Session-based credential management via proxy server
