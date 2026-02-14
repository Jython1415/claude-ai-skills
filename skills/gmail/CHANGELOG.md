# Changelog

All notable changes to the Gmail Access skill will be documented in this file.

## [0.4.1] - 2026-02-14

### Fixed
- Fix `extract_headers` to use case-insensitive header name matching per RFC 2822 — Gmail API returns `Message-Id` (lowercase 'd') but `create_draft` looked for `Message-ID`, silently skipping threading headers

### Changed
- Add header casing note to SKILL.md for users making direct API calls

## [0.4.0] - 2026-02-14

### Added
- `gmail_client.py` — Shared API client library with session-based auth, replacing standalone scripts
  - Core `api` object with `get()`, `post()`, `delete()`, `patch()`, `put()` methods
  - `decode_body()`, `extract_body()`, `extract_headers()` for MIME message handling
  - `search()` — Search messages with decoded headers and snippets
  - `get_message()` — Fetch full message with decoded body
  - `get_thread()` — Fetch full thread with all messages decoded
  - `create_draft()` — Create drafts with correct reply threading (`In-Reply-To`, `References`, `threadId`)
  - `paginate()` — Cursor-based pagination for any Gmail list endpoint

### Changed
- Rewrite SKILL.md with library-first approach and inline code examples
  - Add examples: search, read message, read thread, reply to thread, manage labels, paginate
  - Add API reference table for all exported functions

### Removed
- **BREAKING:** Remove all 3 scripts from `scripts/` directory (`list_messages.py`, `read_message.py`, `read_thread.py`), replaced by `gmail_client` library

## [0.3.0] - 2026-02-12

### Added
- `read_thread.py` - Read full email thread with decoded bodies and chronological message display
  - Supports direct thread ID lookup and `--search` mode to find threads by Gmail query

### Fixed
- Include `threadId` in `list_messages.py` output for easy pipeline to `read_thread.py`

### Changed
- Restructure SKILL.md to prioritize scripts over raw API examples
  - Add "Common Tasks" quick-reference table mapping tasks to scripts
  - Move scripts section with full usage docs above API examples
  - Rename "Usage Examples" to "Direct API Usage" and position as fallback for custom operations

## [0.2.0] - 2026-02-11

### Added
- `read_message.py` - Read full message body with MIME multipart decoding

### Fixed
- Fix `metadataHeaders` parameter in `list_messages.py` — pass as list instead of comma-separated string

### Removed
- Remove `send_message.py` — sending is blocked by the proxy; use drafts instead

## [0.1.1] - 2026-02-10

### Fixed
- Fix auto-release for skills merged via pull requests

## [0.1.0] - 2026-02-09

### Added
- Initial release of Gmail Access skill
- `list_messages.py` - Search and list emails via credential proxy
- `send_message.py` - Send emails via credential proxy
- Multi-account support via `GMAIL_SERVICE` environment variable
- Account management: `--rename` and `--remove` subcommands in setup script
- Session-based credential management via proxy server
