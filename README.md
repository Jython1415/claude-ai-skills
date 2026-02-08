# Claude AI Skills

A collection of skills for Claude.ai, powered by a credential proxy that enables Claude to access APIs (Bluesky, GitHub, etc.) and clone/push git repos without exposing credentials.

## Features

- **Session-based authentication**: Time-limited sessions for secure API access
- **Transparent credential proxy**: Forward requests to APIs with credentials injected server-side
- **Git bundle operations**: Clone repos into Claude's environment, push changes back
- **MCP custom connector**: Claude.ai browser integration via Streamable HTTP

## Setup

### 1. Install Dependencies

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
brew install cloudflared
```

### 2. Configure `.env`

```bash
cp .env.example .env
# Edit .env with your values
```

Required env vars:
- `PROXY_SECRET_KEY` - generate with `openssl rand -hex 32`
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` - from a [GitHub OAuth App](https://github.com/settings/developers)
- `GITHUB_ALLOWED_USERS` - comma-separated GitHub usernames
- `BASE_URL` - your Cloudflare Tunnel domain (e.g. `https://mcp.yourdomain.com`)

GitHub OAuth App callback URL must be `<BASE_URL>/oauth/callback`.

### 3. Configure API Credentials

```bash
cp server/credentials.example.json server/credentials.json
# Edit with your API tokens
```

### 4. Set Up Cloudflare Tunnel

Create a tunnel in [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) > Networks > Tunnels:
- Point your hostname (e.g. `mcp.yourdomain.com`) to `http://localhost:10000`
- Install the connector locally:
  ```bash
  sudo cloudflared service install <token>
  ```
- **Disable "Block AI Bots"** in Cloudflare dashboard (Security > Bots) — this silently blocks Claude.ai's requests

### 5. Start Services

```bash
./scripts/setup-launchagents.sh
```

This installs LaunchAgents for auto-start on login:
- **Flask proxy** on port 8443
- **MCP server** on port 10000
- **Cloudflare Tunnel** via system LaunchDaemon

### 6. Add MCP Connector in Claude.ai

1. Settings > Connectors > Add Custom Connector
2. Name: `Credential Proxy`
3. URL: `<BASE_URL>/mcp`
4. Click Add — authorize via GitHub when prompted

## Usage in Claude.ai

Once connected, use the MCP tools:

```
# Create a session for API access
Use create_session with services: ["bsky", "git"]
```

## Server Management

```bash
# Restart servers
./scripts/setup-launchagents.sh

# Check status
launchctl list | grep joshuashew

# View logs
tail -f ~/Library/Logs/com.joshuashew.credential-proxy.log
tail -f ~/Library/Logs/com.joshuashew.mcp-server.log
tail -f ~/Library/Logs/com.joshuashew.cloudflare-tunnel.log

# Audit log (JSON Lines — session lifecycle, proxy requests, git operations)
tail -f ~/Library/Logs/credential-proxy-audit.jsonl
```

If the Cloudflare Tunnel system service is missing (e.g. after `brew upgrade cloudflared`),
re-run `sudo cloudflared service install <token>`.

## Documentation

- [CLAUDE.md](CLAUDE.md) - Technical reference for Claude Code
- [mcp/README.md](mcp/README.md) - MCP server details

## License

MIT
