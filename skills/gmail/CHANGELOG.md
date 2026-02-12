# Changelog

All notable changes to the Gmail Access skill will be documented in this file.

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
