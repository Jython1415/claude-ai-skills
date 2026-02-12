## Claude Code Local Environment — Active

You are running locally on the user's machine (Claude Code CLI).

**Available:**
- Credential proxy / MCP tools (create_session, report_skill_issue)
- Full network access
- Flask proxy server and MCP server (managed via LaunchAgents)

**Important:**
- Do NOT run setup-launchagents.sh — ask the user to run it if servers need restarting
- LaunchAgent scripts require user-level permissions that Claude cannot use

## Running Locally

```bash
# Sync dependencies
uv sync

# Start Flask server
uv run python server/proxy_server.py

# Start MCP server (separate terminal)
FLASK_URL=http://localhost:8443 uv run python mcp/mcp_server.py
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

# Audit log (JSON Lines — session lifecycle, proxy requests, git operations)
tail -f ~/Library/Logs/credential-proxy-audit.jsonl
```

## Cloudflare Tunnel

The MCP server is exposed via Cloudflare Tunnel (dashboard-managed).
The tunnel connector runs as a system LaunchDaemon (`com.cloudflare.cloudflared`),
installed via `sudo cloudflared service install <token>`.
Wildcard DNS `*.joshuashew.com` routes through the tunnel.

**Important:** Cloudflare's "Block AI Bots" setting (Security -> Bots) must be
disabled for the zone. It silently blocks Claude.ai's backend requests
(`python-httpx` User-Agent) through the tunnel.
