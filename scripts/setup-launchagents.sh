#!/bin/bash
#
# Setup LaunchAgents and Tailscale Funnel for Credential Proxy
#
# This script configures:
# 1. LaunchAgents to auto-start Flask proxy and MCP server on login
# 2. Tailscale Funnel to expose both servers via HTTPS
#
# Features:
# - Idempotent: Safe to run multiple times (detects and restarts existing servers)
# - Validates GitHub OAuth credentials from .env before starting
# - Verifies both servers started successfully after configuration
# - Handles graceful shutdown with sleep delays for clean restarts
#
# Usage:
#   ./scripts/setup-launchagents.sh    # First install OR restart servers
#
# Requirements:
# - .env file with GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_ALLOWED_USERS
# - uv package manager installed
# - Tailscale installed (optional, for Funnel setup)
#
# To check status:
#   launchctl list | grep joshuashew
#   tailscale funnel status
#
# To manually stop/start:
#   launchctl stop com.joshuashew.credential-proxy
#   launchctl start com.joshuashew.credential-proxy
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.joshuashew.credential-proxy.plist
#   launchctl unload ~/Library/LaunchAgents/com.joshuashew.mcp-server.plist
#   rm ~/Library/LaunchAgents/com.joshuashew.credential-proxy.plist
#   rm ~/Library/LaunchAgents/com.joshuashew.mcp-server.plist
#   tailscale funnel off 8443
#   tailscale funnel off 10000

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$HOME/Library/Logs"
ENV_FILE="$PROJECT_DIR/.env"

# Ports (10000 is Tailscale Funnel compatible, 8001 is not)
PROXY_PORT=8443
MCP_PORT=10000

# Find uv binary
UV_BIN=$(which uv 2>/dev/null || echo "$HOME/.local/bin/uv")
if [ ! -x "$UV_BIN" ]; then
    echo "Error: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "========================================"
echo "Credential Proxy Setup"
echo "========================================"
echo "Project directory: $PROJECT_DIR"
echo "uv binary: $UV_BIN"
echo ""

# Check if this is a restart or fresh install
if launchctl list 2>/dev/null | grep -q "com.joshuashew.credential-proxy"; then
    echo "Note: Existing servers detected - will restart them"
    echo ""
fi

# Ensure .venv exists and dependencies are installed
echo "Syncing dependencies..."
(cd "$PROJECT_DIR" && "$UV_BIN" sync --quiet)
echo "Dependencies synced."
echo ""

# Load and validate GitHub OAuth configuration
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

# Validate GitHub OAuth configuration
if [ -z "$GITHUB_CLIENT_ID" ] || [ -z "$GITHUB_CLIENT_SECRET" ]; then
    echo "ERROR: GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set in .env"
    echo ""
    echo "Steps to configure:"
    echo "1. Go to https://github.com/settings/developers"
    echo "2. Create new OAuth App with callback: https://ganymede.tail0410a7.ts.net:10000/oauth/callback"
    echo "3. Add to .env file:"
    echo "   GITHUB_CLIENT_ID=your-client-id"
    echo "   GITHUB_CLIENT_SECRET=your-client-secret"
    echo "   GITHUB_ALLOWED_USERS=Jython1415"
    echo "   BASE_URL=https://ganymede.tail0410a7.ts.net:10000"
    exit 1
fi

if [ -z "$GITHUB_ALLOWED_USERS" ]; then
    echo "WARNING: GITHUB_ALLOWED_USERS not set. No users will be allowed access!"
    echo "Add to .env file: GITHUB_ALLOWED_USERS=Jython1415"
fi

echo "GitHub OAuth Configuration:"
echo "  Client ID: $GITHUB_CLIENT_ID"
echo "  Allowed Users: $GITHUB_ALLOWED_USERS"
echo ""

# Ensure LaunchAgents directory exists
mkdir -p "$LAUNCH_AGENTS_DIR"

# --- Flask Credential Proxy Server ---
echo "----------------------------------------"
echo "Setting up Flask Proxy Server (port $PROXY_PORT)"
echo "----------------------------------------"

PROXY_PLIST="$LAUNCH_AGENTS_DIR/com.joshuashew.credential-proxy.plist"
PROXY_LABEL="com.joshuashew.credential-proxy"

# Unload existing if present (handles both restart and fresh install)
if launchctl list 2>/dev/null | grep -q "$PROXY_LABEL"; then
    echo "Stopping existing credential proxy..."
    launchctl unload "$PROXY_PLIST" 2>/dev/null || true
    sleep 1  # Give it time to stop
fi

# Also unload old gitproxy if present
OLD_PROXY_LABEL="com.joshuashew.gitproxy"
OLD_PROXY_PLIST="$LAUNCH_AGENTS_DIR/com.joshuashew.gitproxy.plist"
if launchctl list 2>/dev/null | grep -q "$OLD_PROXY_LABEL"; then
    echo "Removing old gitproxy LaunchAgent..."
    launchctl unload "$OLD_PROXY_PLIST" 2>/dev/null || true
    rm -f "$OLD_PROXY_PLIST"
fi

echo "Creating $PROXY_PLIST..."
cat > "$PROXY_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PROXY_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$UV_BIN</string>
        <string>run</string>
        <string>--frozen</string>
        <string>python</string>
        <string>$PROJECT_DIR/server/proxy_server.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOGS_DIR/com.joshuashew.credential-proxy.log</string>

    <key>StandardErrorPath</key>
    <string>$LOGS_DIR/com.joshuashew.credential-proxy.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin</string>
        <key>PORT</key>
        <string>$PROXY_PORT</string>
    </dict>
</dict>
</plist>
EOF

echo "Loading credential proxy LaunchAgent..."
launchctl load "$PROXY_PLIST"
echo "Done."

# --- MCP Server ---
echo ""
echo "----------------------------------------"
echo "Setting up MCP Server (port $MCP_PORT)"
echo "----------------------------------------"

MCP_PLIST="$LAUNCH_AGENTS_DIR/com.joshuashew.mcp-server.plist"
MCP_LABEL="com.joshuashew.mcp-server"

# Unload existing if present (handles both restart and fresh install)
if launchctl list 2>/dev/null | grep -q "$MCP_LABEL"; then
    echo "Stopping existing MCP server..."
    launchctl unload "$MCP_PLIST" 2>/dev/null || true
    sleep 1  # Give it time to stop
fi

echo "Creating $MCP_PLIST..."
cat > "$MCP_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$MCP_LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$UV_BIN</string>
        <string>run</string>
        <string>--frozen</string>
        <string>python</string>
        <string>$PROJECT_DIR/mcp/server.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOGS_DIR/com.joshuashew.mcp-server.log</string>

    <key>StandardErrorPath</key>
    <string>$LOGS_DIR/com.joshuashew.mcp-server.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin</string>
        <key>FLASK_URL</key>
        <string>http://localhost:$PROXY_PORT</string>
        <key>MCP_PORT</key>
        <string>$MCP_PORT</string>
        <key>GITHUB_CLIENT_ID</key>
        <string>$GITHUB_CLIENT_ID</string>
        <key>GITHUB_CLIENT_SECRET</key>
        <string>$GITHUB_CLIENT_SECRET</string>
        <key>GITHUB_ALLOWED_USERS</key>
        <string>$GITHUB_ALLOWED_USERS</string>
        <key>BASE_URL</key>
        <string>https://ganymede.tail0410a7.ts.net:$MCP_PORT</string>
    </dict>
</dict>
</plist>
EOF

echo "Loading MCP server LaunchAgent..."
launchctl load "$MCP_PLIST"
echo "Done."

# --- Tailscale Funnel ---
echo ""
echo "----------------------------------------"
echo "Setting up Tailscale Funnel"
echo "----------------------------------------"

# Find tailscale binary (check both PATH and macOS app location)
TAILSCALE_BIN=$(command -v tailscale 2>/dev/null || echo "/Applications/Tailscale.app/Contents/MacOS/Tailscale")

if [ ! -x "$TAILSCALE_BIN" ]; then
    echo "Warning: tailscale not found"
    echo "Install Tailscale from https://tailscale.com/download"
    echo "Then run: tailscale funnel $PROXY_PORT && tailscale funnel $MCP_PORT"
else
    echo "Using tailscale at: $TAILSCALE_BIN"

    # Set up funnel for both ports with --bg flag for persistence
    echo "Configuring Tailscale Funnel for port $PROXY_PORT..."
    "$TAILSCALE_BIN" funnel --https=$PROXY_PORT --bg http://127.0.0.1:$PROXY_PORT 2>&1 | grep -v "Press Ctrl+C" || echo "  (configured)"

    echo "Configuring Tailscale Funnel for port $MCP_PORT..."
    "$TAILSCALE_BIN" funnel --https=$MCP_PORT --bg http://127.0.0.1:$MCP_PORT 2>&1 | grep -v "Press Ctrl+C" || echo "  (configured)"

    echo ""
    echo "Tailscale Funnel status:"
    "$TAILSCALE_BIN" serve status 2>/dev/null || echo "  (run 'tailscale serve status' to check)"
fi

# --- Summary ---
echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Services:"
echo "  Flask Proxy: http://localhost:$PROXY_PORT"
echo "  MCP Server:  http://localhost:$MCP_PORT"
echo ""
echo "LaunchAgents installed (auto-start on login):"
echo "  $PROXY_PLIST"
echo "  $MCP_PLIST"
echo ""
echo "Logs:"
echo "  tail -f ~/Library/Logs/com.joshuashew.credential-proxy.log"
echo "  tail -f ~/Library/Logs/com.joshuashew.mcp-server.log"
echo ""
echo "Claude.ai Custom Connector:"
# Get Tailscale hostname
TS_HOSTNAME=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" 2>/dev/null || echo "ganymede.tail0410a7.ts.net")
echo "  Name: Credential Proxy"
echo "  URL: https://$TS_HOSTNAME:$MCP_PORT/mcp"
echo ""
echo "Advanced Settings (OAuth):"
echo "  OAuth Client ID: $GITHUB_CLIENT_ID"
echo "  OAuth Client Secret: (from .env)"
echo ""
echo "Allowed GitHub Users: $GITHUB_ALLOWED_USERS"
echo ""
echo "Status commands:"
echo "  launchctl list | grep joshuashew"
echo "  tailscale funnel status"
echo ""

# Verify servers started
echo "Verifying servers started..."
sleep 2
if launchctl list 2>/dev/null | grep -q "$PROXY_LABEL"; then
    echo "  ✓ Flask Proxy server running"
else
    echo "  ✗ Flask Proxy server NOT running - check logs"
fi

if launchctl list 2>/dev/null | grep -q "$MCP_LABEL"; then
    echo "  ✓ MCP server running"
else
    echo "  ✗ MCP server NOT running - check logs"
fi
