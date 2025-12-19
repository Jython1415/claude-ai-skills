# Setup Instructions for Joshua

Commands to run **outside Claude Code** (in a privileged terminal).

## Step 1: Install Tailscale

```bash
# Install via Homebrew
brew install tailscale

# After install completes, paste the output here
```

## Step 2: Start Tailscale

```bash
# This requires sudo and will open browser for auth
sudo tailscale up

# After authentication completes, paste the output here
```

## Step 3: Check Your Machine Name

```bash
# See your Tailscale status
tailscale status

# Paste the output - we need your machine name
```

## Step 4: Enable and Start Funnel

```bash
# First attempt - may prompt for Funnel enablement
tailscale funnel 8443

# If it asks you to enable Funnel:
# 1. Visit the admin console link it provides
# 2. Click to enable Funnel
# 3. Run the command again

# Paste the output (or error message if Funnel needs enabling)
```

## Step 5: Start Persistent Funnel

```bash
# Start Funnel in background mode (auto-restarts on reboot)
tailscale funnel --bg 8443

# Paste the output
```

## Step 6: Get Your Stable URL

```bash
# Check Funnel status and get your URL
tailscale funnel status

# Paste the output - we need the URL!
# It will look like: https://joshuas-macbook.tail12345.ts.net:8443
```

## Step 7: Test the Setup

```bash
# Start the Flask server (from project directory)
cd /Users/Joshua/Documents/_programming/claude-git-bridge
./scripts/start_server.sh

# In another terminal, test the public URL
# Replace with your actual URL from step 6
curl https://your-machine.your-tailnet.ts.net:8443/health

# Paste both outputs
```

## What to Send Back

After running these commands, send me:
1. Output from each step (especially any errors)
2. Your Tailscale Funnel URL from step 6
3. Whether the curl test in step 7 succeeded

Then I can help you:
- Configure the .env file for Claude.ai
- Set up auto-start (if desired)
- Test the complete flow
