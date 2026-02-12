## Claude Code Web Environment — Active

You are running in Claude Code Web (cloud container). Key differences from local CLI:

**Available:**
- GITHUB_TOKEN is auto-provided — use it for all GitHub API interactions
- gh CLI is installed and auto-authenticates via GITHUB_TOKEN (no `gh auth login` needed)
- Git push works normally — the container's git proxy is pre-configured as `origin`
- uv / Python are available

**NOT available — do not attempt:**
- Do not start the Flask proxy server or MCP server (no credentials.json or .env)
- Do not call MCP tools (create_session, report_skill_issue, etc.)
- Do not use the credential proxy for Bluesky/Gmail/etc. API calls
- Skills requiring the credential proxy (gmail, bluesky authenticated endpoints) cannot be tested end-to-end; write the code and verify via PR review

**Network:** The web container has egress restrictions (host allowlist). GitHub and common package registries work. Calls to arbitrary external APIs may fail.

**GitHub workflow:**
- Prefer `gh` CLI for PRs, issues, comments (e.g., `gh pr create`, `gh issue comment`)
- Use `gh api` for GitHub API calls that gh CLI doesn't cover
- Git operations work normally via the pre-configured origin remote
