"""
Transparent Proxy for Credential Proxy

Forwards requests to upstream services with credential injection.
Streams responses back to avoid buffering large payloads.
"""

import logging
from urllib.parse import unquote, urlparse

import requests
from credentials import CredentialStore
from flask import Response, stream_with_context

logger = logging.getLogger(__name__)

# Only these request headers are forwarded to upstream services.
# Using an allowlist prevents leaking internal or sensitive headers.
ALLOWED_FORWARD_HEADERS = {
    "content-type",
    "accept",
    "accept-language",
    "accept-encoding",
    "user-agent",
    "content-length",
    "content-encoding",
}

# Response headers that should not be forwarded back
EXCLUDED_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "content-encoding",  # Let Flask handle encoding
    "content-length",  # Will be recalculated
}


def filter_request_headers(headers: dict) -> dict:
    """
    Filter request headers to only include allowed headers.

    Uses an allowlist approach to prevent leaking internal,
    hop-by-hop, or authentication headers to upstream services.

    Args:
        headers: Original request headers

    Returns:
        Filtered headers dict containing only allowed headers
    """
    return {k: v for k, v in headers.items() if k.lower() in ALLOWED_FORWARD_HEADERS}


def filter_response_headers(headers: dict) -> dict:
    """
    Filter response headers for forwarding back to client.

    Args:
        headers: Upstream response headers

    Returns:
        Filtered headers dict
    """
    return {k: v for k, v in headers.items() if k.lower() not in EXCLUDED_RESPONSE_HEADERS}


def forward_request(
    service: str,
    path: str,
    method: str,
    headers: dict,
    body: bytes | None,
    query_string: str,
    credential_store: CredentialStore,
) -> Response:
    """
    Forward a request to an upstream service with credential injection.

    Args:
        service: Service name to forward to
        path: URL path after the service base URL
        method: HTTP method (GET, POST, etc.)
        headers: Request headers
        body: Request body (if any)
        query_string: Query string from original request
        credential_store: CredentialStore instance for credential lookup

    Returns:
        Flask Response object with streamed upstream response
    """
    # Get service credentials
    cred = credential_store.get(service)
    if cred is None:
        logger.warning(f"Unknown service requested: {service}")
        return Response(f'{{"error": "unknown service: {service}"}}', status=404, mimetype="application/json")

    # Build target URL
    base_url = cred.base_url.rstrip("/")
    target_url = f"{base_url}/{path}"

    # Validate against path traversal
    decoded_path = unquote(path)
    if ".." in decoded_path or ".." in path:
        logger.warning(f"Path traversal detected in proxy path: {path}")
        return Response(
            '{"error": "path traversal detected"}',
            status=400,
            mimetype="application/json",
        )

    # Verify the resolved URL still starts with the base URL
    parsed_base = urlparse(base_url)
    parsed_target = urlparse(target_url)
    if parsed_target.netloc != parsed_base.netloc:
        logger.warning(f"Proxy target host mismatch: {parsed_target.netloc} != {parsed_base.netloc}")
        return Response(
            '{"error": "proxy target host mismatch"}',
            status=400,
            mimetype="application/json",
        )

    if query_string:
        target_url = f"{target_url}?{query_string}"

    # Filter and prepare headers
    forward_headers = filter_request_headers(headers)

    # Inject authentication
    forward_headers, target_url = cred.inject_auth(forward_headers, target_url)

    logger.info(f"Proxying {method} {service}/{path}")

    try:
        # Make upstream request with streaming
        upstream_resp = requests.request(
            method=method, url=target_url, headers=forward_headers, data=body, stream=True, timeout=60
        )

        # Stream response back
        response_headers = filter_response_headers(dict(upstream_resp.headers))

        return Response(
            stream_with_context(upstream_resp.iter_content(chunk_size=8192)),
            status=upstream_resp.status_code,
            headers=response_headers,
            content_type=upstream_resp.headers.get("Content-Type", "application/octet-stream"),
        )

    except requests.exceptions.Timeout:
        logger.error(f"Timeout proxying to {service}/{path}")
        return Response('{"error": "upstream timeout"}', status=504, mimetype="application/json")

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error proxying to {service}/{path}: {e}")
        return Response('{"error": "upstream connection failed"}', status=502, mimetype="application/json")

    except Exception as e:
        # Log full exception for local debugging
        logger.error(f"Error proxying to {service}/{path}: {e}")
        # Return generic error to client (don't expose exception details)
        return Response(
            '{"what": "Proxy error occurred", "why": "Request forwarding failed", "action": "Check proxy server logs for details"}',
            status=500,
            mimetype="application/json",
        )
