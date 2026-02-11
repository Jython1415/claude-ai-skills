"""
Integration tests for Flask routes.

Tests endpoint behavior via Flask test client.
Uses fixtures from conftest.py (flask_app, client, auth_headers).
"""


# =============================================================================
# Health endpoint
# =============================================================================


class TestHealth:
    """Tests for GET /health."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_json(self, client):
        resp = client.get("/health")
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_health_no_auth_required(self, client):
        """Health endpoint should work without any auth headers."""
        resp = client.get("/health")
        assert resp.status_code == 200


# =============================================================================
# Session management endpoints
# =============================================================================


class TestSessions:
    """Tests for session management endpoints."""

    def test_create_session_requires_auth(self, client):
        resp = client.post("/sessions", json={"services": ["git"]})
        assert resp.status_code == 401

    def test_create_session_returns_session_id(self, client, auth_headers):
        resp = client.post(
            "/sessions",
            json={"services": ["git"], "ttl_minutes": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data
        assert "proxy_url" in data
        assert data["services"] == ["git"]

    def test_create_session_ttl_clamping(self, client, auth_headers):
        """TTL should be clamped to 1-480 range."""
        # Too high
        resp = client.post(
            "/sessions",
            json={"services": ["git"], "ttl_minutes": 9999},
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["expires_in_minutes"] == 480

        # Too low
        resp = client.post(
            "/sessions",
            json={"services": ["git"], "ttl_minutes": 0},
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["expires_in_minutes"] == 1

    def test_create_session_requires_services(self, client, auth_headers):
        resp = client.post("/sessions", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_revoke_session(self, client, auth_headers):
        # Create session first
        resp = client.post(
            "/sessions",
            json={"services": ["git"]},
            headers=auth_headers,
        )
        session_id = resp.get_json()["session_id"]

        # Revoke it
        resp = client.delete(f"/sessions/{session_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "revoked"

    def test_revoke_nonexistent_session(self, client, auth_headers):
        resp = client.delete("/sessions/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_services_requires_auth(self, client):
        resp = client.get("/services")
        assert resp.status_code == 401

    def test_list_services_includes_git(self, client, auth_headers):
        resp = client.get("/services", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "git" in data["services"]


# =============================================================================
# Proxy endpoint
# =============================================================================


class TestProxy:
    """Tests for proxy endpoint auth and validation."""

    def test_proxy_requires_session(self, client):
        resp = client.get("/proxy/bsky/some.endpoint")
        assert resp.status_code == 401

    def test_proxy_rejects_expired_session(self, client, auth_headers):
        """Create a session, expire it, then try to use it."""
        from datetime import datetime, timedelta

        from server.proxy_server import session_store

        session = session_store.create(["bsky"], ttl_minutes=30)
        session.expires_at = datetime.now() - timedelta(minutes=1)

        resp = client.get(
            "/proxy/bsky/some.endpoint",
            headers={"X-Session-Id": session.session_id},
        )
        assert resp.status_code == 401

    def test_proxy_rejects_wrong_service(self, client, auth_headers):
        """Session with 'git' service should not access 'bsky' proxy."""
        resp = client.post(
            "/sessions",
            json={"services": ["git"]},
            headers=auth_headers,
        )
        session_id = resp.get_json()["session_id"]

        resp = client.get(
            "/proxy/bsky/some.endpoint",
            headers={"X-Session-Id": session_id},
        )
        assert resp.status_code == 403

    def test_proxy_rejects_git_as_service(self, client, auth_headers):
        """'git' is not a proxy service -- use /git/* endpoints instead."""
        resp = client.post(
            "/sessions",
            json={"services": ["git"]},
            headers=auth_headers,
        )
        session_id = resp.get_json()["session_id"]

        resp = client.get(
            "/proxy/git/some/path",
            headers={"X-Session-Id": session_id},
        )
        assert resp.status_code == 400
        assert "not a proxy service" in resp.get_json()["error"]


# =============================================================================
# Git endpoints (auth/validation only)
# =============================================================================


class TestGitAuth:
    """Tests for git endpoint authentication (not actual git operations)."""

    def test_git_fetch_requires_auth(self, client):
        resp = client.post(
            "/git/fetch-bundle",
            json={"repo_url": "https://github.com/user/repo"},
        )
        assert resp.status_code == 401

    def test_git_push_requires_auth(self, client):
        resp = client.post(
            "/git/push-bundle",
            data={"repo_url": "https://github.com/user/repo", "branch": "test"},
        )
        assert resp.status_code == 401

    def test_git_fetch_rejects_admin_key(self, client, auth_headers):
        """Admin key alone should not grant access to git endpoints."""
        resp = client.post(
            "/git/fetch-bundle",
            json={"repo_url": "https://github.com/user/repo"},
            headers=auth_headers,
        )
        assert resp.status_code == 401

    def test_git_push_rejects_admin_key(self, client, auth_headers):
        """Admin key alone should not grant access to git endpoints."""
        resp = client.post(
            "/git/push-bundle",
            data={"repo_url": "https://github.com/user/repo", "branch": "test"},
            headers=auth_headers,
        )
        assert resp.status_code == 401


# =============================================================================
# Issue reporting endpoint
# =============================================================================


class TestIssues:
    """Tests for POST /issues endpoint."""

    def test_create_issue_requires_auth(self, client):
        resp = client.post(
            "/issues",
            json={"title": "Test Issue", "body": "Issue body"},
        )
        assert resp.status_code == 401

    def test_create_issue_requires_title(self, client, auth_headers):
        # Missing title
        resp = client.post(
            "/issues",
            json={"body": "Issue body"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

        # Empty title
        resp = client.post(
            "/issues",
            json={"title": "", "body": "Issue body"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_issue_requires_body(self, client, auth_headers):
        resp = client.post(
            "/issues",
            json={"title": "Test Issue"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_issue_title_too_long(self, client, auth_headers):
        long_title = "a" * 257
        resp = client.post(
            "/issues",
            json={"title": long_title, "body": "Issue body"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_issue_labels_must_be_list(self, client, auth_headers):
        resp = client.post(
            "/issues",
            json={"title": "Test Issue", "body": "Issue body", "labels": "bug"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_issue_too_many_labels(self, client, auth_headers):
        too_many_labels = [f"label{i}" for i in range(11)]
        resp = client.post(
            "/issues",
            json={
                "title": "Test Issue",
                "body": "Issue body",
                "labels": too_many_labels,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_issue_invalid_label(self, client, auth_headers):
        resp = client.post(
            "/issues",
            json={
                "title": "Test Issue",
                "body": "Issue body",
                "labels": ["bad label!"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_issue_github_not_configured(self, client, auth_headers):
        """Test returns 503 when github_api is not in the credential store."""
        from unittest.mock import patch

        with patch("server.proxy_server.credential_store") as mock_store:
            mock_store.get.return_value = None
            resp = client.post(
                "/issues",
                json={
                    "title": "Test Issue",
                    "body": "Issue body",
                    "labels": ["bug", "enhancement"],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 503
