# Auto-Start Flask Server with LaunchAgent

Optional: Configure your Flask server to auto-start when you log in to macOS.

## Why Use LaunchAgent?

With Tailscale Funnel running with `--bg`, it auto-starts on boot. But your Flask server still needs to be started manually. A LaunchAgent makes it automatic.

## Setup Steps

### 1. Find Your Python Path

```bash
# Get the path to your virtual environment Python
cd /Users/Joshua/Documents/_programming/claude-git-bridge
source .venv/bin/activate
which python

# Copy this path, you'll need it below
# Should be something like: /Users/Joshua/Documents/_programming/claude-git-bridge/.venv/bin/python
```

### 2. Create LaunchAgent File

Create file at: `~/Library/LaunchAgents/com.joshuashew.gitproxy.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.joshuashew.gitproxy</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/Joshua/Documents/_programming/claude-git-bridge/.venv/bin/python</string>
        <string>/Users/Joshua/Documents/_programming/claude-git-bridge/server/proxy_server.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/Joshua/Documents/_programming/claude-git-bridge</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/Joshua/Library/Logs/gitproxy.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/Joshua/Library/Logs/gitproxy-error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

### 3. Load LaunchAgent

```bash
# Load the agent (starts immediately and on login)
launchctl load ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist

# Verify it's running
launchctl list | grep gitproxy
```

## Management Commands

```bash
# Stop the service
launchctl unload ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist

# Start the service
launchctl load ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist

# View logs
tail -f ~/Library/Logs/gitproxy.log
tail -f ~/Library/Logs/gitproxy-error.log
```

## Testing

After loading the LaunchAgent:

```bash
# Check if server is running
curl http://127.0.0.1:8443/health

# Restart your Mac to test auto-start
# After reboot, check again:
curl http://127.0.0.1:8443/health
```

## Troubleshooting

### Service won't start
- Check Python path is correct in plist file
- Verify .env file exists in project root
- Check error logs: `cat ~/Library/Logs/gitproxy-error.log`

### Service keeps restarting
- Check for port conflicts: `lsof -i :8443`
- Review error logs for issues

### Changes not taking effect
```bash
# Unload, make changes, then reload
launchctl unload ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist
# Edit the plist file
launchctl load ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist
```

## Removal

If you want to remove auto-start:

```bash
# Unload the agent
launchctl unload ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist

# Remove the plist file
rm ~/Library/LaunchAgents/com.joshuashew.gitproxy.plist
```
