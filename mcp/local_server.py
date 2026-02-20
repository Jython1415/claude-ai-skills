"""Local MCP server for service management and proxy testing.

Runs as a stdio server launched by Claude Code via .mcp.json.
Provides tools to check status, control, and read logs for
the project's LaunchAgent-managed services, plus a test_proxy
tool for making authenticated requests to the local Flask proxy.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

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


def _load_proxy_config() -> tuple[str, str]:
    """Load proxy URL and admin key from .env.

    Returns:
        (base_url, admin_key) tuple.

    Raises:
        RuntimeError: If .env is missing or PROXY_SECRET_KEY is not set.
    """
    env_path = _PROJECT_DIR / ".env"
    if not env_path.exists():
        raise RuntimeError(f".env not found at {env_path}")

    env = dotenv_values(env_path)
    admin_key = env.get("PROXY_SECRET_KEY", "")
    if not admin_key:
        raise RuntimeError("PROXY_SECRET_KEY not set in .env")

    port = env.get("PORT", "8443")
    return f"http://localhost:{port}", admin_key


def _test_proxy_impl(
    method: str,
    path: str,
    body: str | None = None,
    session_id: str | None = None,
) -> str:
    """Implementation for test_proxy tool (separated for testability)."""
    try:
        base_url, admin_key = _load_proxy_config()
    except RuntimeError as e:
        return f"Error: {e}"

    url = f"{base_url}{path}"
    headers: dict[str, str] = {}

    if session_id:
        headers["X-Session-Id"] = session_id
    else:
        headers["X-Auth-Key"] = admin_key

    json_body = None
    if body:
        try:
            json_body = json.loads(body)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON body: {e}"

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_body,
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to {base_url}. Is the proxy running? Check with service_status('proxy')."
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"

    parts = [f"HTTP {response.status_code}"]

    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        try:
            parts.append(json.dumps(response.json(), indent=2))
        except ValueError:
            parts.append(response.text)
    else:
        parts.append(response.text)

    return "\n".join(parts)


@mcp.tool()
def test_proxy(
    method: str,
    path: str,
    body: str | None = None,
    session_id: str | None = None,
) -> str:
    """Make an authenticated request to the local Flask proxy for testing.

    Reads PROXY_SECRET_KEY from .env automatically. No manual key handling needed.

    Args:
        method: HTTP method ("GET", "POST", "DELETE").
        path: Request path (e.g., "/health", "/services", "/proxy/bsky/...").
        body: Optional JSON body as a string (for POST/PUT requests).
        session_id: Optional session ID for session-authenticated endpoints.
            If provided, sends X-Session-Id header instead of X-Auth-Key.
    """
    return _test_proxy_impl(method, path, body, session_id)


if __name__ == "__main__":
    mcp.run()
