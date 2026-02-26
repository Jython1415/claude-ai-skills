# Claude Code Technical Reference

@DEVELOPMENT.md

## Workflow: Skill Versioning & CI

Each skill has `VERSION` and `CHANGELOG.md` files in its directory. **Any PR that modifies
files under `skills/<name>/` must bump the VERSION and add a CHANGELOG entry.** This is
enforced by the `check-version-bump` CI workflow — PRs will fail without it.

- Bump the patch version for fixes, minor version for new features
- Follow the existing CHANGELOG format (`## [x.y.z] - YYYY-MM-DD` with `### Added/Changed/Fixed` subsections)

PRs run two CI workflows:
- **test** — `ruff check`, `ruff format --check`, `pytest` with coverage
- **check-version-bump** — Verifies VERSION is bumped when skill files change

Both must pass before merge. Run locally before pushing:
```bash
uv run ruff check && uv run ruff format --check && uv run pytest
```

## Environment Setup

Claude Code runs in two environments: **locally** (CLI) or **remotely** (Claude Code Web).
The SessionStart hook (`.claude/hooks/session-start.sh`) outputs the appropriate setup file
at session start:
- `LOCAL-SETUP.md` — local behavioral instructions, server management, LaunchAgent/Cloudflare reference
- `REMOTE-SETUP.md` — remote behavioral instructions, available/unavailable tools, network constraints

## Architectural Constraints

### Local Server Requirement
The MCP server must run locally on the user's machine, not on cloud infrastructure like Cloudflare Workers. This is a non-negotiable requirement for the credential proxy architecture - credentials must stay on the local machine.

### Local vs Remote MCP Tool Placement
Tools that manage local infrastructure (launchctl, log reading, setup scripts) belong on
the **local stdio MCP server** (`local_server.py` via `.mcp.json`), NOT on the remote MCP
server. The remote server requires itself to be running — putting management tools there
creates a chicken-and-egg problem. The local server is launched by Claude Code as a
subprocess, runs outside the sandbox, and has no dependency on remote infrastructure.

## Sandbox Limitations

### Temp Files
The Write tool triggers interactive permission prompts for paths outside the project (including `$TMPDIR`). Use `printf ... > "$TMPDIR/file"` via Bash instead — the Bash sandbox has write access to `$TMPDIR` without prompts.

### Git Commits
Sandbox blocks heredoc temp file creation → empty commit message → abort. Use `git commit -m "Title" -m "Body" -m "Footer"` with multiple `-m` flags instead of heredocs.

### gh CLI TLS Issue
The gh CLI in the sandbox hits macOS TLS verification (`SecTrustEvaluateWithError`) failures:
- `gh-nosec` at `~/.local/bin/gh-nosec` built with `CGO_ENABLED=0` + `golang.org/x/crypto/x509roots/fallback` (embeds Mozilla CA roots)
- Requires `GODEBUG=x509usefallbackroots=1` at runtime to force pure-Go verifier
- Wrapper at `~/bin/gh` dispatches to `gh-nosec` with GODEBUG when `CLAUDECODE=1`, falls through to `/opt/homebrew/bin/gh` otherwise
- To update `gh-nosec`:
  ```
  git clone --depth 1 --branch <version> https://github.com/cli/cli.git /tmp/gh-build
  cd /tmp/gh-build && go get golang.org/x/crypto/x509roots/fallback
  # Add `_ "golang.org/x/crypto/x509roots/fallback"` to cmd/gh/main.go imports
  go mod tidy
  CGO_ENABLED=0 go build -C /tmp/gh-build -o ~/.local/bin/gh-nosec ./cmd/gh
  ```
- Tailscale Funnel does NOT work — Anthropic's backend (160.79.104.0/21) times out reaching Funnel relay servers

## Agent Guidelines

### Refactoring Parameter Preservation
When refactoring function internals, always preserve all parameter defaults from the original implementation. Changed defaults cause silent behavioral regressions (e.g., `search_threads()` called `threads.get` with no `format` param — API default: `full`. A refactor silently changed this to `format="metadata"`, causing data loss).
