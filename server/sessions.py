"""
Session Management for Credential Proxy

Provides in-memory session storage with automatic expiry.
Sessions grant time-limited access to specified services.
"""

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Session:
    """Represents an authenticated session with access to specific services."""

    session_id: str
    services: list[str]
    created_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() > self.expires_at

    def has_service(self, service: str) -> bool:
        """Check if session grants access to a service."""
        return service in self.services

    def time_remaining(self) -> timedelta:
        """Get time remaining until expiry."""
        remaining = self.expires_at - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


class SessionStore:
    """
    Thread-safe in-memory session store with automatic expiry.

    Sessions are checked for expiry lazily on access.
    Use cleanup_expired() for periodic cleanup if needed.
    """

    def __init__(self, on_session_expired=None):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._on_session_expired = on_session_expired

    def create(self, services: list[str], ttl_minutes: int = 30) -> Session:
        """
        Create a new session granting access to specified services.

        Args:
            services: List of service names this session can access
            ttl_minutes: Session lifetime in minutes (default 30)

        Returns:
            The created Session object
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()
        session = Session(
            session_id=session_id,
            services=list(services),  # Copy to prevent external modification
            created_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )

        with self._lock:
            self._sessions[session_id] = session

        return session

    def get(self, session_id: str) -> Session | None:
        """
        Get a session by ID if it exists and hasn't expired.

        Expired sessions are lazily removed on access.

        Args:
            session_id: The session ID to look up

        Returns:
            Session if found and valid, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            if session.is_expired():
                del self._sessions[session_id]
                if self._on_session_expired:
                    self._on_session_expired(session_id)
                return None

            return session

    def revoke(self, session_id: str) -> bool:
        """
        Revoke (delete) a session.

        Args:
            session_id: The session ID to revoke

        Returns:
            True if session existed and was revoked, False otherwise
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def has_service(self, session_id: str, service: str) -> bool:
        """
        Check if a session grants access to a specific service.

        Args:
            session_id: The session ID to check
            service: The service name to check access for

        Returns:
            True if session is valid and grants access to service
        """
        session = self.get(session_id)
        if session is None:
            return False
        return session.has_service(service)

    def cleanup_expired(self) -> int:
        """
        Remove all expired sessions.

        This is optional - sessions are also cleaned up lazily on access.
        Useful for periodic cleanup to free memory.

        Returns:
            Number of expired sessions removed
        """
        removed = 0

        with self._lock:
            expired_ids = [sid for sid, session in self._sessions.items() if session.is_expired()]
            for sid in expired_ids:
                del self._sessions[sid]
                if self._on_session_expired:
                    self._on_session_expired(sid)
                removed += 1

        return removed

    def count(self) -> int:
        """Get the number of active (non-expired) sessions."""
        with self._lock:
            return sum(1 for session in self._sessions.values() if not session.is_expired())

    def list_sessions(self) -> list[dict]:
        """
        List all active sessions (for debugging/admin).

        Returns:
            List of session info dicts (without exposing full session objects)
        """
        with self._lock:
            return [
                {
                    "session_id": session.session_id,
                    "services": session.services,
                    "created_at": session.created_at.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "minutes_remaining": int(session.time_remaining().total_seconds() / 60),
                }
                for session in self._sessions.values()
                if not session.is_expired()
            ]
