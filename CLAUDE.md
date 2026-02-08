# Claude Credential Proxy - Technical Reference

## Project Purpose

Credential proxy enabling Claude.ai to access APIs and clone repositories without exposing credentials. Credentials stay on your Mac; Claude only gets time-limited session tokens.

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
            ├── /proxy/<svc>  → Transparent credential proxy
            └── /git/*        → Git bundle operations
```

## Key Files

### Server (`server/`)
- `proxy_server.py` - Main Flask app with all endpoints
- `sessions.py` - In-memory session store with TTL
- `credentials.py` - Loads service configs from JSON
- `proxy.py` - Transparent HTTP forwarding with credential injection
- `credentials.json` - Your API credentials (gitignored)

### MCP Server (`mcp/`)
- `server.py` - FastMCP server with `create_session`, `revoke_session`, `list_services`
- Runs on port 10000 with Streamable HTTP transport via Cloudflare Tunnel
- Uses GitHub OAuth with username allowlist (set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_ALLOWED_USERS` env vars)
- No custom middleware needed -- uses default FastMCP directly

### Skills (`skills/`)
- `git-proxy/` - Git bundle proxy skill (Python library + packaging)
  - `git_client.py` - Python client supporting both session and key auth
- `bluesky-access/` - Bluesky API skill (standalone scripts)

## Authentication

**Session-based (new):**
```python
# MCP creates session
session = create_session(["bsky", "git"], ttl_minutes=30)

# Scripts use session_id
headers = {"X-Session-Id": session["session_id"]}
requests.get(f"{session['proxy_url']}/proxy/bsky/...", headers=headers)
```

**Legacy key-based (still supported):**
```python
headers = {"X-Auth-Key": os.environ["GIT_PROXY_KEY"]}
```

Git endpoints accept either auth method.

## Endpoints

### Session Management
- `POST /sessions` - Create session with services list
- `DELETE /sessions/<id>` - Revoke session
- `GET /services` - List available services

### Transparent Proxy
- `ANY /proxy/<service>/<path>` - Forward to upstream with credentials

### Git Operations
- `POST /git/fetch-bundle` - Clone repo, return bundle
- `POST /git/push-bundle` - Apply bundle, push, create PR

## Configuration

**Server `.env`:**
```
PROXY_SECRET_KEY=<legacy-auth-key>
PORT=8443
DEBUG=false

# GitHub OAuth for MCP Server
GITHUB_CLIENT_ID=<github-oauth-app-client-id>
GITHUB_CLIENT_SECRET=<github-oauth-app-secret>
GITHUB_ALLOWED_USERS=Jython1415,other-username
BASE_URL=https://mcp.joshuashew.com
```

**Service Credentials (`server/credentials.json`):**
```json
{
  "bsky": {
    "base_url": "https://bsky.social/xrpc",
    "auth_type": "bearer",
    "credential": "your-app-password"
  }
}
```

## Running Locally

```bash
# Sync dependencies
uv sync

# Start Flask server
uv run python server/proxy_server.py

# Start MCP server (separate terminal)
FLASK_URL=http://localhost:8443 uv run python mcp/server.py
```

## LaunchAgent Setup

All three services (Flask proxy, MCP server, Cloudflare Tunnel) auto-start on login via LaunchAgents:

```bash
# Install (one-time) or restart servers
./scripts/setup-launchagents.sh

# Check status
launchctl list | grep joshuashew

# Logs
tail -f ~/Library/Logs/com.joshuashew.credential-proxy.log
tail -f ~/Library/Logs/com.joshuashew.mcp-server.log
tail -f ~/Library/Logs/com.joshuashew.cloudflare-tunnel.log
```

**Important for Claude Code:**
- The setup script (`setup-launchagents.sh`) must be run by the USER, not by Claude
- Claude cannot execute this script due to launchctl permissions
- If servers need restarting, ask the user to run: `./scripts/setup-launchagents.sh`
- The script is idempotent - safe to run multiple times (detects and restarts existing servers)

## Cloudflare Tunnel

The MCP server is exposed via Cloudflare Tunnel (dashboard-managed).
The tunnel connector runs as a system LaunchDaemon (`com.cloudflare.cloudflared`),
installed via `sudo cloudflared service install <token>`.
Wildcard DNS `*.joshuashew.com` routes through the tunnel.

**Important:** Cloudflare's "Block AI Bots" setting (Security -> Bots) must be
disabled for the zone. It silently blocks Claude.ai's backend requests
(`python-httpx` User-Agent) through the tunnel.

## Dependencies

Managed via `pyproject.toml` and uv:
- Flask, requests, python-dotenv (Flask server)
- mcp[cli], httpx (MCP server)
- Python 3.10+

## Security Model

- **MCP Authentication**: GitHub OAuth with username allowlist
- **Access Control**: Only specified GitHub usernames can access MCP tools
- **Credentials Protection**: API credentials never leave the proxy server
- **Session Management**: Sessions expire automatically (default 30 min)
- **Service Isolation**: Sessions grant access to specific services only
- **Transport Security**: Cloudflare Tunnel provides encrypted HTTPS tunnel

## Core Requirements

### Local Server Requirement
The MCP server must run locally on the user's machine, not on cloud infrastructure like Cloudflare Workers. This is a non-negotiable requirement for the credential proxy architecture - credentials must stay on the local machine.

## Service Configuration

Each service in `credentials.json` specifies:
- `base_url`: API base URL
- `auth_type`: `bearer`, `header`, or `query`
- `credential`: The secret token
- `auth_header`: Custom header name (for `auth_type: header`)
- `query_param`: Query param name (for `auth_type: query`)
