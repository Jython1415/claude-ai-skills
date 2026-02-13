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

**Orchestration: delegate by default.**

Main-context capacity is limited and non-renewable. Subagent context is fresh and cheap. Push all granular work — reads, searches, analysis, code, review — to subagents. Reserve the main context for task decomposition, subagent coordination, and final synthesis.

3 consecutive non-spawn tool calls = you're probably doing work that should be delegated. Use the most capable model each subtask needs.

When in doubt, delegate.
