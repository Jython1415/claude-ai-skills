"""
Error response utilities for structured, actionable error messages.

Provides helper functions for creating consistent error responses with
mandatory "what" field and optional "why" and "action" hints for Claude.
"""

from flask import jsonify
from typing import Optional, Union, List


def error_response(
    what: str,
    why: Optional[str] = None,
    action: Optional[Union[str, List[str]]] = None,
    code: Optional[str] = None,
    status: int = 500
):
    """
    Build a structured error response.

    Creates a JSON error response with a consistent format:
    - "what" (mandatory): What happened - the error description
    - "why" (optional): Why it happened - for Claude's understanding
    - "action" (optional): What to do about it - hints for the user
    - "code" (optional): Error code for documentation/tracking

    Args:
        what: MANDATORY - Description of what happened (the error)
        why: OPTIONAL - Explanation of why it happened (for Claude)
        action: OPTIONAL - What the user should do next (string or list of strings)
        code: OPTIONAL - Error code for documentation/tracking
        status: HTTP status code (default: 500)

    Returns:
        Tuple of (jsonify response, status_code) ready for Flask to return

    Examples:
        >>> return error_response(
        ...     what="Clone failed",
        ...     why="Repository not found or access denied",
        ...     action="Verify repo URL and GitHub credentials",
        ...     status=500
        ... )

        >>> return error_response(
        ...     what="Authentication required",
        ...     why="Request is missing X-Session-Id header",
        ...     action="Include X-Session-Id from create_session()",
        ...     status=401
        ... )
    """
    response = {'what': what}

    if why:
        response['why'] = why

    if action:
        response['action'] = action

    if code:
        response['code'] = code

    return jsonify(response), status
