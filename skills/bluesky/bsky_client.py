"""
Shared Bluesky API client with automatic auth routing.

Routes requests to the public API or credential proxy based on endpoint
classification and session availability. One session can grant access to
multiple services (e.g., Bluesky + Gmail), so the env vars are
service-agnostic: SESSION_ID and PROXY_URL.

Usage:
    from bsky_client import api, resolve_handle_to_did, url_to_at_uri

    # Auto-routes to public API or proxy based on endpoint and session
    data = api.get("app.bsky.actor.getProfile", {"actor": "bsky.app"})

    # Utility helpers
    did = resolve_handle_to_did("bsky.app")
    uri = url_to_at_uri("https://bsky.app/profile/bsky.app/post/3abc123")
"""

import os
import re

import requests

PUBLIC_API = "https://public.api.bsky.app/xrpc"
DEFAULT_TIMEOUT = 30


class AuthRequiredError(Exception):
    """Raised when an endpoint requires auth but no session is available."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        super().__init__(
            f"Endpoint '{endpoint}' requires authentication. Set SESSION_ID and PROXY_URL environment variables."
        )


# ---------------------------------------------------------------------------
# Endpoint classification
# ---------------------------------------------------------------------------
# Categories:
#   public_only    – Never needs auth; always use public API.
#   auth_required  – Always requires proxy; error without session.
#
# Endpoints not listed here default to auth_required (fail-safe).
# ---------------------------------------------------------------------------

_PUBLIC_ONLY = {
    # Identity
    "com.atproto.identity.resolveHandle",
    # Actor
    "app.bsky.actor.getProfile",
    "app.bsky.actor.getProfiles",
    "app.bsky.actor.searchActors",
    "app.bsky.actor.searchActorsTypeahead",
    "app.bsky.actor.getSuggestions",
    # Feed (read)
    "app.bsky.feed.searchPosts",
    "app.bsky.feed.getAuthorFeed",
    "app.bsky.feed.getPostThread",
    "app.bsky.feed.getPosts",
    "app.bsky.feed.getQuotes",
    "app.bsky.feed.getFeed",
    "app.bsky.feed.getListFeed",
    "app.bsky.feed.getLikes",
    "app.bsky.feed.getRepostedBy",
    "app.bsky.feed.getActorFeeds",
    "app.bsky.feed.getFeedGenerator",
    "app.bsky.feed.getFeedGenerators",
    "app.bsky.feed.getSuggestedFeeds",
    "app.bsky.feed.describeFeedGenerator",
    # Graph (public)
    "app.bsky.graph.getFollowers",
    "app.bsky.graph.getFollows",
    "app.bsky.graph.getRelationships",
    "app.bsky.graph.getSuggestedFollowsByActor",
    "app.bsky.graph.getList",
    "app.bsky.graph.getLists",
    "app.bsky.graph.getStarterPack",
    "app.bsky.graph.getStarterPacks",
    "app.bsky.graph.getActorStarterPacks",
    "app.bsky.graph.searchStarterPacks",
    # Labeler
    "app.bsky.labeler.getServices",
    # Trending / discovery (unspecced)
    "app.bsky.unspecced.getTrendingTopics",
    "app.bsky.unspecced.getTrends",
    "app.bsky.unspecced.getPopularFeedGenerators",
    "app.bsky.unspecced.getTaggedSuggestions",
    # Repository (low-level reads)
    "com.atproto.repo.describeRepo",
    "com.atproto.repo.getRecord",
    "com.atproto.repo.listRecords",
    # Labels
    "com.atproto.label.queryLabels",
}


def _classify(endpoint: str) -> str:
    """Return the auth category for an endpoint."""
    if endpoint in _PUBLIC_ONLY:
        return "public_only"
    return "auth_required"


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


class _API:
    """Namespace for API request methods."""

    @staticmethod
    def _get_session():
        """Return (session_id, proxy_url) or (None, None)."""
        session_id = os.environ.get("SESSION_ID")
        proxy_url = os.environ.get("PROXY_URL")
        if session_id and proxy_url:
            return session_id, proxy_url
        return None, None

    @staticmethod
    def get(endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request to a Bluesky XRPC endpoint.

        Routes to the public API or credential proxy based on endpoint
        classification and session availability.

        Args:
            endpoint: XRPC endpoint NSID (e.g., "app.bsky.actor.getProfile")
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            AuthRequiredError: If the endpoint needs auth and no session exists
            requests.exceptions.HTTPError: On non-2xx responses
        """
        category = _classify(endpoint)
        session_id, proxy_url = _API._get_session()

        if category == "public_only":
            url = f"{PUBLIC_API}/{endpoint}"
            headers = {}
        else:  # auth_required
            if session_id and proxy_url:
                url = f"{proxy_url}/proxy/bsky/{endpoint}"
                headers = {"X-Session-Id": session_id}
            else:
                raise AuthRequiredError(endpoint)

        response = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def post(endpoint: str, json: dict | None = None) -> dict:
        """Make a POST request to a Bluesky XRPC endpoint.

        All POST endpoints require authentication via the credential proxy.

        Args:
            endpoint: XRPC endpoint NSID (e.g., "com.atproto.repo.createRecord")
            json: JSON body

        Returns:
            Parsed JSON response

        Raises:
            AuthRequiredError: If no session is available
            requests.exceptions.HTTPError: On non-2xx responses
        """
        session_id, proxy_url = _API._get_session()
        if not session_id or not proxy_url:
            raise AuthRequiredError(endpoint)

        url = f"{proxy_url}/proxy/bsky/{endpoint}"
        headers = {"X-Session-Id": session_id}

        response = requests.post(url, json=json, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()


api = _API()


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


def resolve_handle_to_did(handle: str) -> str:
    """Resolve a Bluesky handle to a DID via the public API."""
    data = api.get("com.atproto.identity.resolveHandle", {"handle": handle})
    return data["did"]


def resolve_did_to_handle(did: str) -> str | None:
    """Resolve a DID to a handle via getProfile. Returns None on failure."""
    try:
        data = api.get("app.bsky.actor.getProfile", {"actor": did})
        return data.get("handle")
    except requests.exceptions.RequestException:
        return None


def url_to_at_uri(url: str) -> str:
    """Convert a bsky.app post URL to an AT-URI.

    Accepts URLs like:
        https://bsky.app/profile/handle.bsky.social/post/3abc123
        https://bsky.app/profile/did:plc:xxx/post/3abc123
    """
    match = re.match(r"https://bsky\.app/profile/([^/]+)/post/([^/?#]+)", url)
    if not match:
        raise ValueError(f"Invalid bsky.app post URL: {url}")

    actor, rkey = match.groups()
    if not actor.startswith("did:"):
        actor = resolve_handle_to_did(actor)

    return f"at://{actor}/app.bsky.feed.post/{rkey}"
