# Claude Git Bridge - Technical Reference

## Project Purpose
Proxy server enabling Claude.ai web interface to execute git operations via HTTPS tunnel.

## Architecture
- **Server**: `server/proxy_server.py` - Flask app, executes git commands, auth validation
- **Client**: `client/git_client.py` - Python client for Claude.ai skills, communicates with server
- **Auth**: Token-based via `X-Auth-Key` header
- **Workspace**: Isolated directory for git operations (default: `~/git-proxy-workspace`)

## Key Files

### Server (`server/proxy_server.py`)
- Endpoints: `/health`, `/git-exec`, `/workspace/list`
- Security: Validates auth, ensures commands start with `git `, restricts to workspace
- Logging: All requests logged to `workspace/requests.log`
- Config: Env vars `PROXY_SECRET_KEY`, `GIT_WORKSPACE`, `PORT`, `DEBUG`

### Client (`client/git_client.py`)
- `GitProxyClient` class with methods: `clone()`, `commit()`, `push()`, `pull()`, `log()`, `branch()`, `checkout()`
- Config: Env vars `GIT_PROXY_URL`, `GIT_PROXY_KEY`
- Base64 encodes commands, sends to proxy, decodes results

### Configuration (`.env`)
```
PROXY_SECRET_KEY=<secret>      # Required: auth token
GIT_PROXY_URL=<url>            # Required: proxy URL
GIT_PROXY_KEY=<secret>         # Required: must match PROXY_SECRET_KEY
GIT_WORKSPACE=~/git-proxy-workspace  # Optional
PORT=8443                      # Optional
```

## Common Operations

### Start Server
```bash
./scripts/start_server.sh
# Or: python3 server/proxy_server.py
```

### Expose Server
```bash
ngrok http 8443
# Copy https://*.ngrok-free.app URL to .env as GIT_PROXY_URL
```

### Client Usage
```python
from client.git_client import GitProxyClient
client = GitProxyClient()
repo = client.clone('https://github.com/user/repo.git')
client.status(repo)
client.commit(repo, "message")
client.push(repo, branch='main')
```

## Security Model
- Auth token required (401 if missing/invalid)
- Only `git ` commands allowed (403 otherwise)
- Working directory must be within workspace
- Timeout: 60s per command
- Audit trail in `requests.log`

## Primary Use Case
Enable Claude.ai Projects to manage their own knowledge repositories:
1. Clone project knowledge repo
2. Analyze git history
3. Identify improvements
4. Create feature branches
5. Push for human review

See `examples/claude_self_improvement.py`

## Dependencies
- Flask (server)
- requests (client)
- Python 3.7+
- git installed on server machine

## Deployment Options
1. **Tailscale Funnel** (Current): Free stable URLs, auto-start on boot, zero maintenance
   - URL: `https://<machine>.<tailnet>.ts.net:8443`
   - Setup: `tailscale funnel --bg 8443`
   - Auto-restarts: On reboot, WiFi change, Tailscale restart
2. **VPS**: Deploy as systemd service (always-on option)
3. **Custom domain**: nginx + SSL + DNS A record (advanced)

## ToS Compliance
Compliant with Anthropic Usage Policy - equivalent to VPN/ngrok/SSH tunneling for legitimate development.
