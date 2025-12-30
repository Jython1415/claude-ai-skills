#!/bin/bash
#
# Setup LaunchAgents and Tailscale Funnel for Credential Proxy
#
# This script configures:
# 1. LaunchAgents to auto-start Flask proxy and MCP server on login
# 2. Tailscale Funnel to expose both servers via HTTPS
#
# Usage:
#   ./scripts/setup-launchagents.sh
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

# Ensure .venv exists and dependencies are installed
echo "Syncing dependencies..."
(cd "$PROJECT_DIR" && "$UV_BIN" sync --quiet)
echo "Dependencies synced."
echo ""

# Generate MCP auth token if not exists
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

if [ -z "$MCP_AUTH_TOKEN" ]; then
    MCP_AUTH_TOKEN=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    echo "Generated new MCP_AUTH_TOKEN"

    # Append to .env file
    if [ -f "$ENV_FILE" ]; then
        echo "" >> "$ENV_FILE"
        echo "# MCP Server Authentication" >> "$ENV_FILE"
        echo "MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN" >> "$ENV_FILE"
    else
        echo "# Credential Proxy Configuration" > "$ENV_FILE"
        echo "MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN" >> "$ENV_FILE"
    fi
    echo "Saved to $ENV_FILE"
fi

echo ""
echo "MCP Auth Token: $MCP_AUTH_TOKEN"
echo "(Use this as authorization_token in Claude.ai custom connector)"
echo ""

# Ensure LaunchAgents directory exists
mkdir -p "$LAUNCH_AGENTS_DIR"

# --- Flask Credential Proxy Server ---
echo "----------------------------------------"
echo "Setting up Flask Proxy Server (port $PROXY_PORT)"
echo "----------------------------------------"

PROXY_PLIST="$LAUNCH_AGENTS_DIR/com.joshuashew.credential-proxy.plist"
PROXY_LABEL="com.joshuashew.credential-proxy"

# Unload existing if present
if launchctl list 2>/dev/null | grep -q "$PROXY_LABEL"; then
    echo "Stopping existing credential proxy..."
    launchctl unload "$PROXY_PLIST" 2>/dev/null || true
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
    <string>$LOGS_DIR/credential-proxy.log</string>

    <key>StandardErrorPath</key>
    <string>$LOGS_DIR/credential-proxy-error.log</string>

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

# Unload existing if present
if launchctl list 2>/dev/null | grep -q "$MCP_LABEL"; then
    echo "Stopping existing MCP server..."
    launchctl unload "$MCP_PLIST" 2>/dev/null || true
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
    <string>$LOGS_DIR/mcp-server.log</string>

    <key>StandardErrorPath</key>
    <string>$LOGS_DIR/mcp-server-error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin</string>
        <key>FLASK_URL</key>
        <string>http://localhost:$PROXY_PORT</string>
        <key>MCP_PORT</key>
        <string>$MCP_PORT</string>
        <key>MCP_AUTH_TOKEN</key>
        <string>$MCP_AUTH_TOKEN</string>
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

# Check if tailscale is available
if ! command -v tailscale &> /dev/null; then
    echo "Warning: tailscale command not found"
    echo "Install Tailscale from https://tailscale.com/download"
    echo "Then run: tailscale funnel --bg $PROXY_PORT && tailscale funnel --bg $MCP_PORT"
else
    # Set up funnel for both ports
    echo "Configuring Tailscale Funnel for port $PROXY_PORT..."
    tailscale funnel --bg "$PROXY_PORT" 2>/dev/null || echo "  (may already be configured)"

    echo "Configuring Tailscale Funnel for port $MCP_PORT..."
    tailscale funnel --bg "$MCP_PORT" 2>/dev/null || echo "  (may already be configured)"

    echo ""
    echo "Tailscale Funnel status:"
    tailscale funnel status 2>/dev/null || echo "  (run 'tailscale funnel status' to check)"
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
echo "  tail -f ~/Library/Logs/credential-proxy.log"
echo "  tail -f ~/Library/Logs/mcp-server.log"
echo ""
echo "Claude.ai Custom Connector:"
# Get Tailscale hostname
TS_HOSTNAME=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" 2>/dev/null || echo "<your-machine>.<tailnet>.ts.net")
echo "  URL: https://$TS_HOSTNAME:$MCP_PORT/mcp"
echo "  Authorization Token: $MCP_AUTH_TOKEN"
echo ""
echo "Status commands:"
echo "  launchctl list | grep joshuashew"
echo "  tailscale funnel status"
