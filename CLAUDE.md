# Claude AI Skills - Technical Reference

## Project Purpose

A collection of skills for Claude.ai, powered by a credential proxy that lets Claude access APIs and clone repositories without exposing credentials. Credentials stay on your Mac; Claude only gets time-limited session tokens.

## Architecture

```
Claude.ai
    │
    ├── MCP Custom Connector (port 10000, Streamable HTTP)
    │       └── FastMCP server calling Flask API
    │
    └── Flask Proxy Server (port 8443)
            ├── /sessions     → Session management
            ├── /services     → List available services
            ├── /issues       → GitHub issue creation
            ├── /proxy/<svc>  → Transparent credential proxy
            └── /git/*        → Git bundle operations
```

## Key Files

### Server (`server/`)
- `proxy_server.py` - Main Flask app with all endpoints
- `sessions.py` - In-memory session store with TTL
- `credentials.py` - Loads service configs from JSON
- `proxy.py` - Transparent HTTP forwarding with credential injection
- `audit_log.py` - JSON Lines audit logger for session lifecycle, proxy requests, and git operations
- `credentials.json` - Your API credentials (gitignored)

### MCP Server (`mcp/`)
- `mcp_server.py` - Remote FastMCP server with `create_session`, `revoke_session`, `list_services`, `report_skill_issue`
  - Runs on port 10000 with Streamable HTTP transport via Cloudflare Tunnel
  - Uses GitHub OAuth with username allowlist
- `local_server.py` - Local stdio MCP server with `service_status`, `service_control`, `service_logs`, `service_setup`, `test_proxy`
  - Launched by Claude Code via `.mcp.json` — no remote infrastructure needed
  - Runs outside sandbox, can call `launchctl` and `localhost` directly
  - `test_proxy` reads `PROXY_SECRET_KEY` from `.env` for transparent admin auth
- `services.py` - LaunchAgent service management (discover, start/stop/restart, logs, setup script)

### Skills (`skills/`)
- `git-proxy/` - Git bundle proxy skill (Python library + packaging)
  - `git_client.py` - Python client supporting both session and key auth
- `bluesky/` - Bluesky API skill (Python libraries)
  - `bsky_client.py` - API client with automatic auth routing and pagination
  - `bsky_sets.py` - Set-based operations on actor collections

## Authentication

**Admin key (`X-Auth-Key: PROXY_SECRET_KEY`):**

Session management endpoints (`/sessions`, `/services`) require the `X-Auth-Key` header
with the value of `PROXY_SECRET_KEY`. The MCP server passes this key automatically when
calling the Flask API on behalf of authenticated users.

**Session-based (`X-Session-Id`):**
```python
# MCP creates session (passes X-Auth-Key internally)
session = create_session(["bsky", "git"], ttl_minutes=30)

# Scripts use session_id for proxy and git endpoints
headers = {"X-Session-Id": session["session_id"]}
requests.get(f"{session['proxy_url']}/proxy/bsky/...", headers=headers)
```

## Endpoints

### Health
- `GET /health` - Health check (unauthenticated, no sensitive data exposed)

### Session Management (require `X-Auth-Key` header)
- `POST /sessions` - Create session with services list
- `DELETE /sessions/<id>` - Revoke session
- `GET /services` - List available services

### Transparent Proxy (require `X-Session-Id` header)
- `ANY /proxy/<service>/<path>` - Forward to upstream with credentials

### Git Operations (require `X-Session-Id`)
- `POST /git/fetch-bundle` - Clone repo, return bundle
- `POST /git/push-bundle` - Apply bundle, push, create PR

### Issue Reporting (require `X-Auth-Key` header)
- `POST /issues` - Create GitHub issue in configured repo

## Configuration

**Server `.env`:**
```
PROXY_SECRET_KEY=<shared-secret-key>   # Required by both Flask and MCP server
PORT=8443
DEBUG=false
PUBLIC_PROXY_URL=https://proxy.joshuashew.com

# GitHub OAuth for MCP Server
GITHUB_CLIENT_ID=<github-oauth-app-client-id>
GITHUB_CLIENT_SECRET=<github-oauth-app-secret>
GITHUB_ALLOWED_USERS=Jython1415,other-username
BASE_URL=https://mcp.joshuashew.com
ISSUE_REPO=Jython1415/claude-ai-skills    # GitHub repo for issue reporting (owner/repo)
```

`PROXY_SECRET_KEY` is required for both servers. The Flask server uses it to
authenticate admin requests. The MCP server uses it to authorize its calls to
the Flask API. The setup script validates this key is set before starting services.

**Service Credentials (`server/credentials.json`):**
```json
{
  "bsky": {
    "identifier": "handle.bsky.social",
    "app_password": "xxxx-xxxx-xxxx-xxxx"
  },
  "github_api": {
    "token": "ghp_..."
  },
  "gmail": {
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "..."
  }
}
```

Known services (`bsky`, `github_api`, `gmail`, `gcal`, `gdrive`) have hardcoded base URLs and auth types
in `credentials.py`. Custom services need explicit `base_url` and `type` fields.

## Testing MCP Tools

`@mcp.tool()` wraps functions into `FunctionTool` objects that aren't directly callable.
To unit-test tool logic, split implementation from the decorator:

```python
def _my_tool_impl(arg: str) -> str:
    """Testable implementation."""
    ...

@mcp.tool()
def my_tool(arg: str) -> str:
    """MCP tool wrapper."""
    return _my_tool_impl(arg)
```

Tests import and call `_my_tool_impl` directly. See `tests/test_local_server.py` for examples.

## Skill Versioning

Each skill has `VERSION` and `CHANGELOG.md` files in its directory. **Any PR that modifies
files under `skills/<name>/` must bump the VERSION and add a CHANGELOG entry.** This is
enforced by the `check-version-bump` CI workflow — PRs will fail without it.

- Bump the patch version for fixes, minor version for new features
- Follow the existing CHANGELOG format (`## [x.y.z] - YYYY-MM-DD` with `### Added/Changed/Fixed` subsections)

## CI Checks

PRs run two CI workflows:
- **test** — `ruff check`, `ruff format --check`, `pytest` with coverage
- **check-version-bump** — Verifies VERSION is bumped when skill files change

Both must pass before merge. Run locally before pushing:
```bash
uv run ruff check && uv run ruff format --check && uv run pytest
```

## Dependencies

Managed via `pyproject.toml` and uv:
- Flask, requests, python-dotenv (Flask server)
- mcp[cli], httpx (MCP server)
- Python 3.10+

## Security Model

- **MCP Authentication**: GitHub OAuth with username allowlist
- **Access Control**: Only specified GitHub usernames can access MCP tools
- **Admin Endpoints**: Session management and service listing require `X-Auth-Key` header
- **Credentials Protection**: API credentials never leave the proxy server
- **Session Management**: Sessions expire automatically (default 30 min)
- **Service Isolation**: Sessions grant access to specific services only
- **Transport Security**: Cloudflare Tunnel provides encrypted HTTPS tunnel
- **Audit Logging**: All session lifecycle events, proxy requests, and git operations logged to `~/Library/Logs/claude-ai-skills-audit.jsonl`

## Environment Setup

Claude Code runs in two environments: **locally** (CLI) or **remotely** (Claude Code Web).
The SessionStart hook (`.claude/hooks/session-start.sh`) outputs the appropriate setup file
at session start:
- `LOCAL-SETUP.md` — local behavioral instructions, server management, LaunchAgent/Cloudflare reference
- `REMOTE-SETUP.md` — remote behavioral instructions, available/unavailable tools, network constraints

## Core Requirements

### Local Server Requirement
The MCP server must run locally on the user's machine, not on cloud infrastructure like Cloudflare Workers. This is a non-negotiable requirement for the credential proxy architecture - credentials must stay on the local machine.

### Local vs Remote MCP Tool Placement
Tools that manage local infrastructure (launchctl, log reading, setup scripts) belong on
the **local stdio MCP server** (`local_server.py` via `.mcp.json`), NOT on the remote MCP
server. The remote server requires itself to be running — putting management tools there
creates a chicken-and-egg problem. The local server is launched by Claude Code as a
subprocess, runs outside the sandbox, and has no dependency on remote infrastructure.

## Service Configuration

Each service in `credentials.json` specifies:
- `base_url`: API base URL
- `auth_type`: `bearer`, `header`, or `query`
- `credential`: The secret token
- `auth_header`: Custom header name (for `auth_type: header`)
- `query_param`: Query param name (for `auth_type: query`)

### OAuth2 Services (Google APIs)

Google API services use OAuth2 with automatic token refresh. Configure with:
- `client_id`: Google Cloud OAuth2 client ID
- `client_secret`: Google Cloud OAuth2 client secret
- `refresh_token`: Offline refresh token (use `scripts/google_oauth_setup.py` to obtain)
- `token_url`: (optional) Token endpoint, defaults to `https://oauth2.googleapis.com/token`

Known OAuth2 services: `gmail` (Gmail API), `gcal` (Google Calendar), `gdrive` (Google Drive).
Multi-account is supported via distinct service names (e.g., `gmail_work`) with explicit `base_url` and `type: "oauth2"`.
