#!/usr/bin/env python3
"""
MCP Server for Credential Proxy Session Management

Exposes session management as MCP tools for Claude.ai custom connector.
Uses Streamable HTTP transport for compatibility with Claude.ai browser.

Authentication: GitHub OAuth with username allowlist
"""

import os
import sys
import logging
import httpx
from functools import wraps
from typing import Callable, Any
from fastmcp import FastMCP, Context
from fastmcp.server.auth.providers.github import GitHubProvider

# Add parent directory to path to import server modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from server.error_redaction import get_redactor

logger = logging.getLogger(__name__)

# Initialize credential redactor
redactor = get_redactor()

# Configuration
FLASK_URL = os.environ.get('FLASK_URL', 'http://localhost:8443')
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')
GITHUB_ALLOWED_USERS = set(os.environ.get('GITHUB_ALLOWED_USERS', '').split(','))
BASE_URL = os.environ.get('BASE_URL', 'https://ganymede.tail0410a7.ts.net:10000')

# Validate GitHub OAuth configuration
if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
    logger.error("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set!")
    raise ValueError("Missing GitHub OAuth configuration")

if not GITHUB_ALLOWED_USERS or GITHUB_ALLOWED_USERS == {''}:
    logger.warning("No GitHub users in allowlist! Set GITHUB_ALLOWED_USERS")

# Create GitHub auth provider
auth = GitHubProvider(
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    base_url=BASE_URL,
    redirect_path="/oauth/callback"  # Match GitHub OAuth App callback URL
)

# Initialize MCP server with auth
mcp = FastMCP(
    "credential-proxy",
    stateless_http=True,  # Important for scalability with remote connections
    auth=auth  # GitHub OAuth authentication
)


def require_allowlist(func: Callable) -> Callable:
    """Decorator to check if authenticated user is in the allowlist."""
    @wraps(func)
    async def wrapper(context: Context, *args, **kwargs) -> Any:
        # Get authenticated GitHub username
        user_claims = context.request_context.user
        github_username = user_claims.get("login", "unknown")

        # Check if user is in allowlist
        if github_username not in GITHUB_ALLOWED_USERS:
            logger.warning(f"Access denied for user: {github_username}")
            return {
                "error": "Access denied",
                "message": f"User '{github_username}' is not authorized to use this service"
            }

        logger.info(f"Authorized user '{github_username}' accessing {func.__name__}")
        return await func(context, *args, **kwargs)

    return wrapper


@mcp.tool()
@require_allowlist
async def create_session(context: Context, services: list[str], ttl_minutes: int = 30) -> dict:
    """
    Create a new session granting access to specified services.

    Use this to get a session_id and proxy_url for accessing APIs through
    the credential proxy. The session will automatically expire after the
    specified TTL.

    Args:
        services: List of service names to grant access to.
                  Common services: "bsky" (Bluesky), "github_api", "git"
                  Use list_services() to see all available services.
        ttl_minutes: Session lifetime in minutes (default: 30, max: 480)

    Returns:
        Dictionary containing:
        - session_id: Use this in X-Session-Id header for requests
        - proxy_url: Base URL for proxy requests
        - expires_in_minutes: Session lifetime
        - services: List of services this session can access

    Example:
        result = create_session(["bsky", "git"], ttl_minutes=60)
        # Use result["session_id"] and result["proxy_url"] in your scripts
    """
    # Validate TTL
    if ttl_minutes < 1:
        return {"error": "ttl_minutes must be at least 1"}
    if ttl_minutes > 480:  # 8 hours max
        return {"error": "ttl_minutes cannot exceed 480 (8 hours)"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FLASK_URL}/sessions",
                json={"services": services, "ttl_minutes": ttl_minutes},
                timeout=10
            )

            if response.status_code == 400:
                return response.json()

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        return {"error": "timeout connecting to proxy server"}
    except httpx.ConnectError:
        return {"error": f"could not connect to proxy server at {FLASK_URL}"}
    except Exception as e:
        # Log full exception for local debugging
        logger.error(f"MCP tool error: {e}")
        # Return generic error to client (don't expose exception details)
        return {"error": "Operation failed", "details": "An unexpected error occurred. Check server logs."}


@mcp.tool()
@require_allowlist
async def revoke_session(context: Context, session_id: str) -> dict:
    """
    Revoke an active session immediately.

    Use this to invalidate a session before its natural expiry.
    After revocation, the session_id can no longer be used.

    Args:
        session_id: The session ID to revoke

    Returns:
        Dictionary with status ("revoked") or error message
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{FLASK_URL}/sessions/{session_id}",
                timeout=10
            )

            if response.status_code == 404:
                return {"status": "not_found", "message": "Session not found or already expired"}

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        return {"error": "timeout connecting to proxy server"}
    except httpx.ConnectError:
        return {"error": f"could not connect to proxy server at {FLASK_URL}"}
    except Exception as e:
        # Log full exception for local debugging
        logger.error(f"MCP tool error: {e}")
        # Return generic error to client (don't expose exception details)
        return {"error": "Operation failed", "details": "An unexpected error occurred. Check server logs."}


@mcp.tool()
@require_allowlist
async def list_services(context: Context) -> dict:
    """
    List all available services that can be included in sessions.

    Returns the names of services configured on the proxy server.
    Use these names when calling create_session().

    Returns:
        Dictionary with "services" key containing list of service names.
        Always includes "git" for git bundle operations.

    Common services:
        - "git": Git bundle operations (clone, push via bundles)
        - "bsky": Bluesky/ATProtocol API
        - "github_api": GitHub REST API
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FLASK_URL}/services",
                timeout=10
            )
            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        return {"error": "timeout connecting to proxy server"}
    except httpx.ConnectError:
        return {"error": f"could not connect to proxy server at {FLASK_URL}"}
    except Exception as e:
        # Log full exception for local debugging
        logger.error(f"MCP tool error: {e}")
        # Return generic error to client (don't expose exception details)
        return {"error": "Operation failed", "details": "An unexpected error occurred. Check server logs."}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Default to port 10000 (Tailscale Funnel compatible)
    port = int(os.environ.get('MCP_PORT', 10000))

    logger.info(f"Starting MCP server on port {port}")
    logger.info(f"Flask backend: {FLASK_URL}")
    logger.info(f"Authentication: GitHub OAuth")
    logger.info(f"Allowed GitHub users: {', '.join(sorted(GITHUB_ALLOWED_USERS))}")
    logger.info(f"OAuth callback URL: {BASE_URL}/oauth/callback")

    # Run with FastMCP's built-in server (handles HTTP transport and auth)
    mcp.run(transport="http", port=port, host="127.0.0.1")
