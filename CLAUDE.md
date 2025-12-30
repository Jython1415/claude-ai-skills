# Claude Credential Proxy - Technical Reference

## Project Purpose

Credential proxy enabling Claude.ai to access APIs and clone repositories without exposing credentials. Credentials stay on your Mac; Claude only gets time-limited session tokens.

## Architecture

```
Claude.ai
    │
    ├── MCP Custom Connector (port 8001, Streamable HTTP)
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
- Runs on port 10000 with Streamable HTTP transport (Tailscale Funnel compatible)
- Requires bearer token authentication (set `MCP_AUTH_TOKEN` env var)

### Client (`skill-package/git-proxy/`)
- `git_client.py` - Python client supporting both session and key auth

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

Both servers auto-start on login via LaunchAgents:

```bash
# Install (one-time)
./scripts/setup-launchagents.sh

# Check status
launchctl list | grep joshuashew

# Logs
tail -f ~/Library/Logs/credential-proxy.log
tail -f ~/Library/Logs/mcp-server.log
```

## Tailscale Funnel

```bash
# Expose both servers
tailscale serve --bg --https=8443 http://127.0.0.1:8443
tailscale serve --bg --https=8001 http://127.0.0.1:8001
tailscale funnel 8443
tailscale funnel 8001
```

## Dependencies

Managed via `pyproject.toml` and uv:
- Flask, requests, python-dotenv (Flask server)
- mcp[cli], httpx (MCP server)
- Python 3.10+

## Security Model

- Credentials never leave the proxy server
- Sessions expire automatically (default 30 min)
- Sessions grant access to specific services only
- Tailscale Funnel provides encrypted, authenticated tunnel
- MCP server is authless (relies on Tailscale network security)

## Service Configuration

Each service in `credentials.json` specifies:
- `base_url`: API base URL
- `auth_type`: `bearer`, `header`, or `query`
- `credential`: The secret token
- `auth_header`: Custom header name (for `auth_type: header`)
- `query_param`: Query param name (for `auth_type: query`)
