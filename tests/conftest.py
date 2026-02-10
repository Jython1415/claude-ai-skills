"""
Shared test fixtures for Flask app integration tests.

CRITICAL: PROXY_SECRET_KEY must be set at module level before importing
proxy_server, because proxy_server.py checks it at import time.
"""

import os
import sys

# Set required env var BEFORE any server imports
os.environ.setdefault("PROXY_SECRET_KEY", "test-secret-key-for-testing")

# Add server/ to path so bare imports work (server/ is not a package)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import pytest  # noqa: E402

from server.proxy_server import app, limiter  # noqa: E402


@pytest.fixture
def flask_app():
    """Provide the Flask app configured for testing."""
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False  # Disable rate limiting in tests
    limiter.enabled = False
    return app


@pytest.fixture
def client(flask_app):
    """Provide a Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def auth_headers():
    """Headers with valid admin auth key."""
    return {"X-Auth-Key": "test-secret-key-for-testing"}
