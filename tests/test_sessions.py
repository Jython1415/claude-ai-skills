"""
Unit tests for session management.

Tests Session and SessionStore classes from server/sessions.py.
No Flask dependency -- pure unit tests.
"""

from datetime import datetime, timedelta

from server.sessions import Session, SessionStore

# =============================================================================
# Session tests
# =============================================================================


class TestSession:
    """Tests for the Session dataclass."""

    def _make_session(self, services=None, ttl_minutes=30):
        """Create a test session."""
        now = datetime.now()
        return Session(
            session_id="test-session-id",
            services=services or ["git", "bsky"],
            created_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )

    def test_not_expired_when_fresh(self):
        session = self._make_session()
        assert session.is_expired() is False

    def test_expired_when_past(self):
        session = self._make_session()
        session.expires_at = datetime.now() - timedelta(minutes=1)
        assert session.is_expired() is True

    def test_has_service_true(self):
        session = self._make_session(services=["git", "bsky"])
        assert session.has_service("git") is True
        assert session.has_service("bsky") is True

    def test_has_service_false(self):
        session = self._make_session(services=["git"])
        assert session.has_service("bsky") is False

    def test_time_remaining_positive(self):
        session = self._make_session(ttl_minutes=30)
        remaining = session.time_remaining()
        assert remaining.total_seconds() > 0

    def test_time_remaining_zero_when_expired(self):
        session = self._make_session()
        session.expires_at = datetime.now() - timedelta(minutes=1)
        remaining = session.time_remaining()
        assert remaining.total_seconds() == 0


# =============================================================================
# SessionStore tests
# =============================================================================


class TestSessionStore:
    """Tests for the SessionStore class."""

    def test_create_returns_session(self):
        store = SessionStore()
        session = store.create(["git"], ttl_minutes=30)
        assert session.session_id is not None
        assert "git" in session.services

    def test_get_valid_session(self):
        store = SessionStore()
        session = store.create(["git"], ttl_minutes=30)
        retrieved = store.get(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_returns_none_for_unknown(self):
        store = SessionStore()
        assert store.get("nonexistent-id") is None

    def test_get_returns_none_for_expired(self):
        store = SessionStore()
        session = store.create(["git"], ttl_minutes=30)
        # Force expiry
        session.expires_at = datetime.now() - timedelta(minutes=1)
        assert store.get(session.session_id) is None

    def test_revoke_existing_session(self):
        store = SessionStore()
        session = store.create(["git"])
        assert store.revoke(session.session_id) is True
        assert store.get(session.session_id) is None

    def test_revoke_nonexistent_returns_false(self):
        store = SessionStore()
        assert store.revoke("nonexistent") is False

    def test_cleanup_expired(self):
        store = SessionStore()
        s1 = store.create(["git"], ttl_minutes=30)
        s2 = store.create(["bsky"], ttl_minutes=30)
        # Force one to expire
        s1.expires_at = datetime.now() - timedelta(minutes=1)
        removed = store.cleanup_expired()
        assert removed == 1
        assert store.get(s1.session_id) is None
        assert store.get(s2.session_id) is not None

    def test_expired_callback_called(self):
        expired_ids = []
        store = SessionStore(on_session_expired=lambda sid: expired_ids.append(sid))
        session = store.create(["git"], ttl_minutes=30)
        session.expires_at = datetime.now() - timedelta(minutes=1)
        store.get(session.session_id)  # Triggers lazy cleanup
        assert session.session_id in expired_ids

    def test_service_isolation(self):
        store = SessionStore()
        session = store.create(["git"])
        assert store.has_service(session.session_id, "git") is True
        assert store.has_service(session.session_id, "bsky") is False

    def test_has_service_returns_false_for_unknown_session(self):
        store = SessionStore()
        assert store.has_service("nonexistent", "git") is False
