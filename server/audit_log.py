"""
Audit logging for Credential Proxy

Appends structured JSON Lines entries to a log file for security-relevant
events: session lifecycle, proxy requests, and git operations.

Each line is a self-contained JSON object. Thread-safe file writing.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = os.path.expanduser("~/Library/Logs/credential-proxy-audit.jsonl")


class AuditLog:
    """Append-only JSON Lines audit logger."""

    def __init__(self, log_path: str | None = None):
        self._log_path = log_path or DEFAULT_LOG_PATH
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
        logger.info(f"Audit log: {self._log_path}")

    def _write(self, entry: dict) -> None:
        """Write a single JSON line to the log file."""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            line = json.dumps(entry, separators=(",", ":"))
            with self._lock:
                with open(self._log_path, "a") as f:
                    f.write(line + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def session_created(self, session_id: str, services: list[str], ttl_minutes: int) -> None:
        self._write(
            {
                "event": "session_created",
                "session_id": session_id,
                "services": services,
                "ttl_minutes": ttl_minutes,
            }
        )

    def session_revoked(self, session_id: str) -> None:
        self._write(
            {
                "event": "session_revoked",
                "session_id": session_id,
            }
        )

    def session_expired(self, session_id: str) -> None:
        self._write(
            {
                "event": "session_expired",
                "session_id": session_id,
            }
        )

    def proxy_request(
        self,
        session_id: str,
        service: str,
        method: str,
        path: str,
        upstream_url: str,
        status_code: int,
        blocked_reason: str | None = None,
    ) -> None:
        entry = {
            "event": "proxy_request",
            "session_id": session_id,
            "service": service,
            "method": method,
            "path": path,
            "upstream_url": upstream_url,
            "status": status_code,
        }
        if blocked_reason:
            entry["blocked_reason"] = blocked_reason
        self._write(entry)

    def git_fetch(self, session_id: str | None, repo_url: str, status_code: int, auth_type: str | None = None) -> None:
        self._write(
            {
                "event": "git_fetch",
                "session_id": session_id,
                "repo_url": repo_url,
                "status": status_code,
                "auth_type": auth_type,
            }
        )

    def issue_created(
        self, issue_url: str, issue_number: int, title: str, labels: list[str] | None = None
    ) -> None:
        self._write(
            {
                "event": "issue_created",
                "issue_url": issue_url,
                "issue_number": issue_number,
                "title": title,
                "labels": labels or [],
            }
        )

    def git_push(
        self,
        session_id: str | None,
        repo_url: str,
        branch: str,
        status_code: int,
        pr_url: str | None = None,
        auth_type: str | None = None,
    ) -> None:
        self._write(
            {
                "event": "git_push",
                "session_id": session_id,
                "repo_url": repo_url,
                "branch": branch,
                "status": status_code,
                "pr_url": pr_url,
                "auth_type": auth_type,
            }
        )


_instance: AuditLog | None = None


def get_audit_log() -> AuditLog:
    """Get the global audit log instance."""
    global _instance
    if _instance is None:
        _instance = AuditLog()
    return _instance
