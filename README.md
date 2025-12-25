# Claude Git Bridge

Git bundle proxy enabling Claude.ai Projects to clone repos into their environment via Tailscale Funnel.

## Quick Start

### 1. Server Setup (One-Time)

```bash
# Install dependencies
./scripts/setup.sh

# Install Tailscale (Mac App Store or Homebrew)
# Login and authenticate

# Start Tailscale Funnel (auto-restarts on boot)
tailscale funnel --bg 8443

# Auto-start Flask server on login (macOS LaunchAgent)
./scripts/install_launchagent.sh

# Get your stable URL
tailscale funnel status
# Example: https://your-machine.tail-abc123.ts.net
```

**Notes:**
- **Tailscale Funnel**: Provides free stable HTTPS URL, auto-restarts on network changes/reboot
- **LaunchAgent**: Auto-starts Flask server on login via `~/Library/LaunchAgents/com.joshuashew.gitproxy.plist`
- **Logs**: Server logs to `~/Library/Logs/gitproxy.log` and `~/Library/Logs/gitproxy-error.log`

### 2. Install Skill in Claude.ai

**Option A: Download from GitHub Releases**
1. Go to [Releases](../../releases)
2. Download `git-proxy-skill.zip` from the latest release
3. Upload to claude.ai → Settings → Skills

**Option B: Build from source**
```bash
./scripts/build_skill.sh
# Upload skill-package/git-proxy-skill.zip to claude.ai → Settings → Skills
```

### 3. Configure Each Project

1. **Add domain to allowed list**: Project Settings → Add your `*.ts.net` domain
2. **Create `.env` file** in project:
   ```
   GIT_PROXY_URL=https://your-machine.tail-id.ts.net
   GIT_PROXY_KEY=<from local .env>
   ```

## How It Works

Claude.ai uses git bundles to clone repos into its own environment:

```
1. Claude requests bundle from proxy
2. Proxy clones repo temporarily, creates bundle, returns it
3. Claude clones bundle locally (in Anthropic infrastructure)
4. Claude edits files, commits, creates feature branch
5. Claude bundles changes and sends to proxy
6. Proxy pushes branch and creates PR
7. All temporary files cleaned up automatically
```

**Your Mac is a pure pass-through** - no persistent storage.

## Architecture

```
Claude.ai ←→ Tailscale Funnel ←→ Flask Proxy ←→ GitHub
  (files)        (tunnel)        (temp only)
```

**Key files**:
- `server/proxy_server.py` - Flask bundle proxy (auto-starts via LaunchAgent)
- `skill-package/git-proxy/git_client.py` - Client for Claude.ai skill
- `.env` - Local config (secret key only)

**Endpoints**:
- `/health` - Health check
- `/git/fetch-bundle` - Clone repo and return as bundle
- `/git/push-bundle` - Apply bundle, push branch, create PR

## Server Management

```bash
# View server logs
tail -f ~/Library/Logs/gitproxy.log

# Restart server
launchctl unload ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist
launchctl load ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist

# Remove auto-start
./scripts/uninstall_launchagent.sh
```

## Releases

Skill packages are automatically built and released to GitHub:

**Automatic Release** (when VERSION file changes):
1. Edit `skill-package/git-proxy/VERSION` (e.g., change to `1.0.1`)
2. Commit and push to main
3. GitHub Actions automatically creates a release with the skill ZIP

**Manual Release**:
1. Go to Actions → Release Skill → Run workflow
2. Optionally specify a version to override the VERSION file
3. Release is created with the skill ZIP attached

Download releases at: [github.com/Jython1415/claude-git-bridge/releases](https://github.com/Jython1415/claude-git-bridge/releases)

## Documentation

- [CLAUDE.md](CLAUDE.md) - Technical reference
- [skill-package/README.md](skill-package/README.md) - Skill installation guide

## License

MIT
