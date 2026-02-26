# Changelog

All notable changes to the git-proxy skill will be documented in this file.

## [1.3.0] - 2026-02-26

### Changed
- Decouple session setup instructions from SKILL.md: Setup section now uses requirements-only language (Requires SESSION_ID and PROXY_URL; service name: "git") instead of imperative create_session procedure
- sys.path instruction now uses self-referential path derivation instead of a hardcoded placeholder
- report_skill_issue reference replaced with consumer-agnostic link to the claude-ai-skills repository

## [1.2.1] - 2024-12-25

### Fixed
- **Prominent import fix**: Added explicit copy command at top of setup instructions to avoid import errors
- Made import workaround the first step in Quick Start example

### Improved
- **51.6% token reduction**: Reduced SKILL.md from 1089 to 527 words (265 to 161 lines)
- Consolidated redundant sections (removed duplicate workflow examples)
- Streamlined troubleshooting with concise Q&A format
- Removed verbose explanations while keeping all essential information
- Reorganized for faster scanning

## [1.2.0] - 2024-12-25

### Added
- `setup_git_user()` function - Auto-configure git identity for commits
- `clone_repo()` now auto-configures git user by default (disable with `setup_user=False`)
- Server auto-detects GitHub CLI (`gh`) at startup for automatic PR creation

### Fixed
- **Critical**: Corrected all bundle creation examples to use explicit branch refs (`origin/main..branch-name` instead of `origin/main..HEAD`)
- Server now finds `gh` CLI even when not in PATH (checks `/opt/homebrew/bin/gh`)
- PR creation now works automatically - no manual URL needed!

### Documentation
- Added troubleshooting sections for bundle refs, git config, and import errors
- Added EXPLANATIONS.md with technical details on bundle refs and gh CLI detection
- Updated all code examples with correct bundle syntax

## [1.1.0] - 2024-12-24

### Added
- `load_env_from_file()` convenience function - Auto-load environment variables from `/mnt/project/_env`
- `clone_repo()` convenience function - One-step clone combining fetch_bundle + git clone + set remote

### Documentation
- Added "IMPORTANT: Available Methods" section explicitly listing what exists
- Added "Methods that DO NOT exist" warnings to prevent hallucination
- Added "Quick Start (Easy Mode)" using new convenience functions
- Added "Common Mistakes to Avoid" section with wrong/correct examples
- Enhanced troubleshooting with specific error scenarios (404, 401, connection issues)

## [1.0.0] - 2024-12-23

### Added
- Initial release with git bundle proxy functionality
- `GitProxyClient` with `health_check()`, `fetch_bundle()`, and `push_bundle()` methods
- Bundle-based clone and push workflow for Claude.ai Projects
- Authentication via secret key
- Automatic temporary directory cleanup on server
