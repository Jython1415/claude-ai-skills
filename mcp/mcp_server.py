#!/usr/bin/env python3
"""
MCP Server for Credential Proxy Session Management

Exposes session management as MCP tools for Claude.ai custom connector.
Uses Streamable HTTP transport with unified /mcp endpoint.

Authentication: GitHub OAuth with username allowlist
Transport: Cloudflare Tunnel required (Tailscale Funnel unreachable from Anthropic IPs)
"""

import logging
import os
import sys
from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx
import uvicorn
from fastmcp import Context, FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.dependencies import get_access_token

from mcp.server.fastmcp.exceptions import ToolError

# Add parent directory to path to import server modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

# Configuration
FLASK_URL = os.environ.get("FLASK_URL", "http://localhost:8443")
PROXY_SECRET_KEY = os.environ.get("PROXY_SECRET_KEY")
if not PROXY_SECRET_KEY:
    logger.error("PROXY_SECRET_KEY must be set for Flask API access!")
    raise ValueError("Missing PROXY_SECRET_KEY configuration")

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
GITHUB_ALLOWED_USERS = {u.strip() for u in os.environ.get("GITHUB_ALLOWED_USERS", "").split(",") if u.strip()}
BASE_URL = os.environ.get("BASE_URL", "https://mcp.joshuashew.com")
KNOWN_SKILLS = {"bluesky", "git-proxy", "gmail", "sift"}

if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
    logger.error("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set!")
    raise ValueError("Missing GitHub OAuth configuration")

if not GITHUB_ALLOWED_USERS:
    raise ValueError(
        "No GitHub users in allowlist. Set the GITHUB_ALLOWED_USERS environment variable (comma-separated usernames)."
    )

auth = GitHubProvider(
    client_id=GITHUB_CLIENT_ID, client_secret=GITHUB_CLIENT_SECRET, base_url=BASE_URL, redirect_path="/oauth/callback"
)

mcp = FastMCP(
    "credential-proxy",
    stateless_http=True,
    auth=auth,
)


def require_allowlist(func: Callable) -> Callable:
    """Decorator to check if authenticated user is in the allowlist."""

    @wraps(func)
    async def wrapper(context: Context, *args, **kwargs) -> Any:
        access_token = get_access_token()
        if access_token is None:
            raise ToolError("Authentication required")
        github_username = access_token.claims.get("login", "unknown")

        if github_username not in GITHUB_ALLOWED_USERS:
            logger.warning(f"Access denied for user: {github_username}")
            raise ToolError("Access denied")

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
                  Common services: "bsky" (Bluesky), "github_api", "git",
                  "gmail" (Gmail API), "gcal" (Google Calendar), "gdrive" (Google Drive)
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
    if ttl_minutes < 1:
        return {"error": "ttl_minutes must be at least 1"}
    if ttl_minutes > 480:
        return {"error": "ttl_minutes cannot exceed 480 (8 hours)"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FLASK_URL}/sessions",
                json={"services": services, "ttl_minutes": ttl_minutes},
                headers={"X-Auth-Key": PROXY_SECRET_KEY},
                timeout=10,
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
                f"{FLASK_URL}/sessions/{session_id}", headers={"X-Auth-Key": PROXY_SECRET_KEY}, timeout=10
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
        - "gmail": Gmail API (OAuth2, auto-refresh)
        - "gcal": Google Calendar API (OAuth2, auto-refresh)
        - "gdrive": Google Drive API (OAuth2, auto-refresh)
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{FLASK_URL}/services", headers={"X-Auth-Key": PROXY_SECRET_KEY}, timeout=10)
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
async def report_skill_issue(
    context: Context,
    skill_name: str,
    title: str,
    description: str,
    issue_type: str = "bug",
    skill_version: str | None = None,
    interaction_log: str | None = None,
    observed_behavior: str | None = None,
    suggestions: str | None = None,
) -> dict:
    """
    Report an observation or propose an idea about a skill.

    Use this tool to document what you encountered while using a skill —
    a script that returned unexpected output, documentation that led you
    down an inefficient path, or a pattern you discovered that could be
    made easier. Frame your report as a factual record of what you tried
    and what happened, not as a directive about what should change.

    Writing style:
        - Title: Describe what you observed, not what should change.
          Good: "searchPosts routes to public endpoint, returns 403"
          Avoid: "searchPosts needs to be reclassified as auth_required"
        - Description: Lead with context — what you were trying to
          accomplish and which parts of the skill you interacted with.
        - Present findings as observations, not verdicts. Use "appeared
          to", "seemed to", "returned" rather than "is broken", "fails",
          "is dead code".
        - For suggestions, frame as proposals: "One approach might be..."
          or "It could help to..." rather than "The fix is..." or
          "This needs to...".

    Args:
        skill_name: Name of the skill ("bluesky", "git-proxy", "gmail", "sift")
        title: Brief, observational issue title (max 200 chars). Describe
            what you observed rather than prescribing a change.
        description: Context for the observation — what you were trying to
            accomplish and which parts of the skill system you interacted with.
        issue_type: "bug" (unexpected behavior observed) or "enhancement"
            (idea for improvement). Default: "bug"
        skill_version: Version from the skill's CHANGELOG.md (the version
            number in the most recent entry, e.g., "2.0.4"). Always check
            the CHANGELOG.md file packaged with the skill and include this
            so the maintainer knows what version of the skill you were
            working with.
        interaction_log: Step-by-step record of what you did — which skill
            files you read, scripts you executed (with commands in code
            blocks), tool calls you made, and how you troubleshot. Include
            commands and their outputs. Mark each step as succeeded or
            failed without explaining why.
        observed_behavior: Numbered factual statements of what occurred.
            Present comparative data neutrally — show before/after states,
            different error messages, or alternate approaches as
            observations rather than conclusions about which is better.
        suggestions: Proposed improvements or ideas, framed as proposals
            rather than directives. E.g., "One approach might be to add
            an auth routing example to the quickstart section."

    Returns:
        Dictionary containing:
        - issue_url: URL to the created GitHub issue
        - issue_number: Issue number on GitHub
        Or {"error": "..."} on failure

    Example:
        report_skill_issue(
            skill_name="bluesky",
            title="searchPosts routes to public endpoint, returns 403",
            description="While searching for posts by a specific user, "
                "the client routed searchPosts to the public API.",
            issue_type="bug",
            skill_version="2.0.1",
            interaction_log="1. Read bsky_client.py, noted searchPosts "
                "in _PUBLIC_ONLY set\\n"
                "2. Ran: `api.get('app.bsky.feed.searchPosts', "
                "{'q': 'claude', 'limit': 3})` — returned 403\\n"
                "3. Tested direct curl to public endpoint — also 403\\n"
                "4. Tested via proxy path — returned 200 with results",
            observed_behavior="1. Public endpoint "
                "(public.api.bsky.app) returned 403 from BunnyCDN\\n"
                "2. Authenticated endpoint (bsky.social) returned 401 "
                "AuthMissing\\n"
                "3. Proxy-routed request returned 200 with expected data",
            suggestions="searchPosts could be moved from _PUBLIC_ONLY to "
                "the default auth-required path, which appeared to "
                "resolve the 403 in testing."
        )
    """
    # Validate skill name
    if skill_name not in KNOWN_SKILLS:
        return {"error": f"Unknown skill: {skill_name}. Must be one of: {', '.join(sorted(KNOWN_SKILLS))}"}

    # Validate title length
    if len(title) > 200:
        return {"error": "Title must be 200 characters or less"}

    # Validate issue type
    if issue_type not in ("bug", "enhancement"):
        return {"error": "issue_type must be 'bug' or 'enhancement'"}

    # Build metadata table
    metadata_rows = [
        "| Field | Value |",
        "|-------|-------|",
        f"| Skill | `{skill_name}` |",
        f"| Type | {issue_type} |",
    ]
    if skill_version:
        metadata_rows.append(f"| Version | `{skill_version}` |")

    metadata_table = "\n".join(metadata_rows)

    # Build issue body
    agent_note = (
        "> *This issue was reported by a Claude.ai agent using the "
        "`report_skill_issue` tool.*"
    )
    body_parts = [agent_note, "", metadata_table, "", "## Description", "", description]

    if interaction_log:
        body_parts.extend(["", "## Interaction Log", "", interaction_log])
    if observed_behavior:
        body_parts.extend(["", "## Observed Behavior", "", observed_behavior])
    if suggestions:
        body_parts.extend(["", "## Suggestions", "", suggestions])

    body = "\n".join(body_parts)

    # Set labels
    labels = [f"skill:{skill_name}", issue_type]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FLASK_URL}/issues",
                json={"title": title, "body": body, "labels": labels},
                headers={"X-Auth-Key": PROXY_SECRET_KEY},
                timeout=10,
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    port = int(os.environ.get("MCP_PORT", 10000))

    logger.info(f"MCP Server starting on port {port}")
    logger.info("Transport: Streamable HTTP (/mcp)")
    logger.info(f"Flask backend: {FLASK_URL}")
    logger.info(f"Base URL: {BASE_URL}")
    logger.info("Auth: GitHub OAuth")
    logger.info(f"Allowed users: {', '.join(sorted(GITHUB_ALLOWED_USERS))}")
    logger.info(f"OAuth callback: {BASE_URL}/oauth/callback")

    app = mcp.http_app(transport="streamable-http")
    uvicorn.run(app, host="127.0.0.1", port=port)
