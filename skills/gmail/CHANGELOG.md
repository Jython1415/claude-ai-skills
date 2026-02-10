# Changelog

All notable changes to the Gmail Access skill will be documented in this file.

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
