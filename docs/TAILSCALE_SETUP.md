# Tailscale Funnel Setup Guide

Complete guide for exposing the git proxy via Tailscale Funnel with stable URLs and auto-start.

## Why Tailscale Funnel?

- **Free** with stable URLs
- **Auto-starts** when your Mac boots
- **Zero maintenance** after setup
- **Works across WiFi changes** seamlessly
- URL format: `https://<machine-name>.<tailnet>.ts.net`

## Prerequisites

- macOS (your MacBook Air M2)
- Tailscale account (free at tailscale.com)
- Port 8443 available (already configured in this project)

## One-Time Setup Steps

### 1. Install Tailscale

Run these commands outside Claude Code:

```bash
# Option A: Via Homebrew
brew install tailscale

# Option B: Download from App Store
# Search "Tailscale" in Mac App Store
```

### 2. Start Tailscale and Authenticate

```bash
# Start Tailscale (requires sudo)
sudo tailscale up

# This will open a browser for authentication
# Login with Google, GitHub, or create account
```

### 3. Get Your Machine Name

```bash
# Check your Tailscale machine name
tailscale status

# You'll see output like:
# joshuas-macbook    joshua@    macOS   -
# Your machine name is the first part
```

### 4. Enable Funnel (First Time Only)

```bash
# Try to start Funnel
tailscale funnel 8443

# If Funnel isn't enabled yet, you'll be prompted to:
# 1. Visit your admin console
# 2. Enable Funnel in your tailnet policy (one click)
# 3. Run the command again
```

### 5. Start Persistent Funnel

```bash
# Start Funnel in background mode (auto-restarts on reboot)
tailscale funnel --bg 8443

# Get your stable URL
tailscale funnel status

# You'll see something like:
# https://joshuas-macbook.tail12345.ts.net:8443
# This is your permanent stable URL!
```

### 6. Configure Your .env File

**IMPORTANT**: This .env file goes in your **Claude.ai Project instructions**, NOT in the Git repo.

```bash
# Copy the URL from funnel status
GIT_PROXY_URL=https://joshuas-macbook.tail12345.ts.net:8443

# Use the same secret key from your local .env
GIT_PROXY_KEY=<your-secret-from-local-env>
```

## Auto-Start Configuration

### Option A: Tailscale Handles It (Recommended)

The `--bg` flag makes Funnel auto-restart when:
- Your Mac reboots
- WiFi changes
- Tailscale restarts

**No additional configuration needed!**

### Option B: LaunchAgent (If You Want Flask Auto-Start Too)

If you also want your Flask server to auto-start on boot, see `docs/LAUNCHAGENT_SETUP.md`.

## Verification

### Test Locally

```bash
# Start your Flask server
./scripts/start_server.sh

# In another terminal, test the public URL
curl https://your-machine.your-tailnet.ts.net:8443/health
```

### Test from Claude.ai

1. Upload `client/git_client.py` to Claude.ai skill
2. Set environment variables in skill config:
   ```
   GIT_PROXY_URL=https://your-machine.your-tailnet.ts.net:8443
   GIT_PROXY_KEY=your-secret-key
   ```
3. Run test script

## Management Commands

```bash
# Check Funnel status
tailscale funnel status

# Stop Funnel (if needed)
tailscale funnel --bg 8443 off

# Restart Funnel
tailscale funnel --bg 8443

# Check Tailscale connection
tailscale status
```

## Troubleshooting

### Funnel won't start
- Check Tailscale is running: `tailscale status`
- Verify port 8443 is free: `lsof -i :8443`
- Enable Funnel in admin console if prompted

### URL not accessible
- Verify your Mac is awake and connected to internet
- Check Flask server is running: `curl http://127.0.0.1:8443/health`
- Check Funnel status: `tailscale funnel status`

### After Mac restart
- Both Tailscale and Funnel auto-start (with `--bg` flag)
- Flask server needs manual start OR use LaunchAgent

## Security Notes

- Tailscale Funnel uses Let's Encrypt for SSL certificates
- All traffic is encrypted end-to-end
- Your auth key protects the proxy endpoints
- Funnel traffic goes through Tailscale's infrastructure
  - They can see metadata (timing, sizes)
  - They cannot see your auth key (if transmitted via headers)
  - Your git commands are base64 encoded but could be decoded

## Cost

**Free forever** for personal use (up to 3 users, 100 devices).
