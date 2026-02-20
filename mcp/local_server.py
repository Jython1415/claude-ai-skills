"""Local MCP server for LaunchAgent service management.

Runs as a stdio server launched by Claude Code via .mcp.json.
Provides tools to check status, control, and read logs for
the project's LaunchAgent-managed services.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add mcp/ directory to path so we can import services.py
sys.path.insert(0, os.path.dirname(__file__))

import services  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("services")

_PROJECT_DIR = Path(__file__).resolve().parent.parent


@mcp.tool()
def service_status(service: str | None = None) -> str:
    """Check the status of LaunchAgent-managed services.

    Shows whether each service is running, its PID, and recent log output.

    Args:
        service: Service name ("proxy", "mcp", "tunnel") or omit for all.
    """
    services_info = services.discover_services()

    if not services_info:
        return "No claude-ai-skills services found. Run service_setup() to install them."

    if service:
        if service not in services_info:
            known = ", ".join(sorted(services_info.keys()))
            return f"Unknown service '{service}'. Available: {known}"
        return services.get_service_status_text(service, services_info[service])

    blocks = []
    for name in sorted(services_info.keys()):
        blocks.append(services.get_service_status_text(name, services_info[name]))
    return "\n\n".join(blocks)


@mcp.tool()
def service_control(service: str, action: str) -> str:
    """Start, stop, or restart a LaunchAgent-managed service.

    Args:
        service: Service name ("proxy", "mcp", "tunnel").
        action: One of "start", "stop", "restart".
    """
    valid_actions = ("start", "stop", "restart")
    if action not in valid_actions:
        return f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}"

    services_info = services.discover_services()
    if service not in services_info:
        known = ", ".join(sorted(services_info.keys()))
        return f"Unknown service '{service}'. Available: {known}"

    label = services_info[service]["label"]
    parts = []

    if service == "mcp" and action in ("stop", "restart"):
        parts.append("WARNING: This will stop the MCP server. It will restart automatically (KeepAlive is enabled).")

    if action == "restart":
        parts.append(services.restart_service(label))
    else:
        parts.append(services.run_launchctl(action, label))

    return "\n".join(parts)


@mcp.tool()
def service_logs(service: str, lines: int = 20) -> str:
    """Read recent log output from a service.

    Args:
        service: Service name ("proxy", "mcp", "tunnel").
        lines: Number of recent lines to return (default: 20, max: 200).
    """
    if lines < 1 or lines > 200:
        return "Error: lines must be between 1 and 200"

    services_info = services.discover_services()
    if service not in services_info:
        known = ", ".join(sorted(services_info.keys()))
        return f"Unknown service '{service}'. Available: {known}"

    label = services_info[service]["label"]
    logs = services.get_logs(label, lines)

    parts = []
    if logs.get("stderr"):
        parts.append(f"=== stderr ===\n{logs['stderr']}")
    if logs.get("stdout"):
        parts.append(f"=== stdout ===\n{logs['stdout']}")
    return "\n\n".join(parts) if parts else "(no log output)"


@mcp.tool()
def service_setup() -> str:
    """Run the setup-launchagents.sh script to install/restart all services.

    This syncs dependencies, validates configuration, generates LaunchAgent
    plists, and loads them. Handles both fresh installs and restarts.

    WARNING: This will restart the MCP server and proxy. Services will
    come back up automatically via KeepAlive.
    """
    result = services.run_setup_script(_PROJECT_DIR)

    parts = []
    if result.get("success"):
        parts.append("Setup completed successfully.")
    else:
        parts.append("Setup FAILED.")

    if result.get("stdout"):
        parts.append(f"\n=== stdout ===\n{result['stdout']}")
    if result.get("stderr"):
        parts.append(f"\n=== stderr ===\n{result['stderr']}")

    return "\n".join(parts)


if __name__ == "__main__":
    mcp.run()
