# Claude Git Bridge

Proxy enabling Claude.ai Projects to execute git operations through Tailscale Funnel.

## Recommended: Skill-Based Setup

**Best for Claude.ai Projects** - Keeps code out of context, works across all projects.

**Quick start:**
1. Build skill: `./scripts/build_skill.sh`
2. Upload `skill-package/git-proxy-skill.zip` to Claude.ai Settings → Skills
3. Upload `.env` to each project
4. Add domain to project allowed list

See [skill-package/README.md](skill-package/README.md) for details.

## Alternative: Direct Integration

For custom setups or Claude Code CLI:

### Setup (One-Time)

```bash
# 1. Install dependencies
./scripts/setup.sh

# 2. Install Tailscale from Mac App Store
# Login and authenticate

# 3. Start Tailscale Funnel (auto-restarts on boot)
tailscale funnel --bg 8443

# 4. Auto-start Flask server on login
./scripts/install_launchagent.sh

# 5. Get your URL
tailscale funnel status
# Example: https://your-machine.tail-abc123.ts.net
```

## Usage in Claude.ai

1. **Add domain to allowed list**: Project Settings → Add your `*.ts.net` domain
2. **Upload**: `client/git_client.py` to project
3. **Create `.env`**:
   ```
   GIT_PROXY_URL=https://your-machine.tail-id.ts.net
   GIT_PROXY_KEY=<from local .env>
   ```
4. **Use it**:
   ```python
   from git_client import GitProxyClient
   client = GitProxyClient()
   repo = client.clone('https://github.com/user/repo.git')
   client.commit(repo, "message")
   client.push(repo)
   ```

## Architecture

```
Claude.ai → Tailscale Funnel → Your Mac → Flask Proxy → Git → GitHub
```

**Key files**:
- `server/proxy_server.py` - Flask server (auto-starts via LaunchAgent)
- `client/git_client.py` - Client for Claude.ai
- `.env` - Local config (secret key, workspace)

**Endpoints**:
- `/health` - Health check
- `/git-exec` - Execute git commands (requires auth)
- `/workspace/list` - List repos

## Management

```bash
# View server logs
tail -f ~/Library/Logs/gitproxy.log

# Restart server
launchctl unload ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist
launchctl load ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist

# Remove auto-start
./scripts/uninstall_launchagent.sh
```

## Docs

- [CLAUDE.md](CLAUDE.md) - Technical reference
- [docs/TAILSCALE_SETUP.md](docs/TAILSCALE_SETUP.md) - Detailed Tailscale setup
- [docs/CLAUDE_AI_TESTING.md](docs/CLAUDE_AI_TESTING.md) - Testing from Claude.ai
- [skill-package/README.md](skill-package/README.md) - Skill installation guide

## License

MIT
