#!/bin/bash
#
# Setup LaunchAgents for Credential Proxy + Cloudflare Tunnel
#
# This script configures:
# 1. LaunchAgents to auto-start Flask proxy and MCP server on login
# 2. Verifies Cloudflare Tunnel system service is installed
#
# Features:
# - Idempotent: Safe to run multiple times (detects and restarts existing servers)
# - Validates GitHub OAuth credentials from .env before starting
# - Verifies all services started successfully after configuration
# - Handles graceful shutdown with sleep delays for clean restarts
#
# Usage:
#   ./scripts/setup-launchagents.sh    # First install OR restart servers
#
# Requirements:
# - .env file with GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_ALLOWED_USERS
# - uv package manager installed
# - cloudflared system service installed (sudo cloudflared service install <token>)
#
# To check status:
#   launchctl list | grep joshuashew
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
#   sudo cloudflared service uninstall  # (for the tunnel)

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="$HOME/Library/Logs"
ENV_FILE="$PROJECT_DIR/.env"

# Ports
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
    echo "2. Create new OAuth App with callback: https://mcp.joshuashew.com/oauth/callback"
    echo "3. Add to .env file:"
    echo "   GITHUB_CLIENT_ID=your-client-id"
    echo "   GITHUB_CLIENT_SECRET=your-client-secret"
    echo "   GITHUB_ALLOWED_USERS=Jython1415"
    echo "   BASE_URL=https://mcp.joshuashew.com"
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
        <string>$PROJECT_DIR/mcp/mcp_server.py</string>
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
        <string>${BASE_URL:-https://mcp.joshuashew.com}</string>
    </dict>
</dict>
</plist>
EOF

echo "Loading MCP server LaunchAgent..."
launchctl load "$MCP_PLIST"
echo "Done."

# --- Cloudflare Tunnel ---
echo ""
echo "----------------------------------------"
echo "Checking Cloudflare Tunnel"
echo "----------------------------------------"

TUNNEL_LABEL="com.joshuashew.cloudflare-tunnel"
TUNNEL_PLIST="$LAUNCH_AGENTS_DIR/com.joshuashew.cloudflare-tunnel.plist"
SYSTEM_TUNNEL_PLIST="/Library/LaunchDaemons/com.cloudflare.cloudflared.plist"

if [ -f "$SYSTEM_TUNNEL_PLIST" ]; then
    echo "  Cloudflare Tunnel is managed by system LaunchDaemon"
    echo "  ($SYSTEM_TUNNEL_PLIST)"
    echo "  To reinstall: sudo cloudflared service install <token>"
    # Clean up user-level agent if it exists from a previous setup
    if [ -f "$TUNNEL_PLIST" ]; then
        echo "  Removing redundant user-level LaunchAgent..."
        launchctl unload "$TUNNEL_PLIST" 2>/dev/null || true
        rm -f "$TUNNEL_PLIST"
    fi
else
    echo "  WARNING: No system LaunchDaemon found for cloudflared"
    echo "  The Cloudflare Tunnel will NOT survive a reboot."
    echo ""
    echo "  To fix, run:"
    echo "    sudo cloudflared service install <token>"
    echo ""
    echo "  Get your token from the Cloudflare Zero Trust dashboard:"
    echo "    Networks > Tunnels > credential-proxy > Configure > Install connector"
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
if [ -f "$SYSTEM_TUNNEL_PLIST" ]; then
echo "  $SYSTEM_TUNNEL_PLIST (system daemon)"
fi
echo ""
echo "Logs:"
echo "  tail -f ~/Library/Logs/com.joshuashew.credential-proxy.log"
echo "  tail -f ~/Library/Logs/com.joshuashew.mcp-server.log"
echo "  tail -f ~/Library/Logs/com.joshuashew.cloudflare-tunnel.log"
echo ""
echo "Claude.ai Custom Connector:"
echo "  Name: Credential Proxy"
echo "  URL: ${BASE_URL:-https://mcp.joshuashew.com}/mcp"
echo "  (OAuth is handled automatically via GitHub — no Advanced Settings needed)"
echo ""
echo "Allowed GitHub Users: $GITHUB_ALLOWED_USERS"
echo ""
echo "Status commands:"
echo "  launchctl list | grep joshuashew"
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

if pgrep -x cloudflared > /dev/null 2>&1; then
    echo "  ✓ Cloudflare Tunnel running"
elif [ -f "$SYSTEM_TUNNEL_PLIST" ]; then
    echo "  ✗ Cloudflare Tunnel NOT running - check: sudo launchctl list | grep cloudflare"
fi
