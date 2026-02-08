# Credential Proxy MCP Server

MCP server providing session management for the credential proxy. Works as a Claude.ai custom connector via Cloudflare Tunnel.

## Setup

See the [main README](../README.md) for full setup instructions. In short:

```bash
./scripts/setup-launchagents.sh
```

## Available Tools

### create_session

Create a session granting access to specified services.

```
create_session(services=["bsky", "git"], ttl_minutes=30)
```

Returns `session_id`, `proxy_url`, and `expires_in_minutes`.

### revoke_session

Revoke an active session immediately.

```
revoke_session(session_id="...")
```

### list_services

List all available services.

```
list_services()
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_URL` | `http://localhost:8443` | Flask server URL |
| `MCP_PORT` | `10000` | MCP server port |
| `BASE_URL` | `https://mcp.joshuashew.com` | Public URL via Cloudflare Tunnel |
| `PROXY_SECRET_KEY` | — | **Required.** Shared secret for Flask API auth (`X-Auth-Key` header) |
| `GITHUB_CLIENT_ID` | — | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth App client secret |
| `GITHUB_ALLOWED_USERS` | — | Comma-separated GitHub usernames |

## Troubleshooting

- **MCP server can't connect to Flask**: Ensure Flask server is running, check `FLASK_URL`
- **Claude.ai can't connect**: Verify Cloudflare Tunnel is running (`launchctl list | grep cloudflare`), check "Block AI Bots" is disabled
- **Session creation fails**: Check Flask server logs, verify `credentials.json` exists
