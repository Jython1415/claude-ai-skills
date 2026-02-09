"""
Credential redaction utility for sanitizing error messages and logs.

Uses exact string matching to redact actual credentials loaded from
configuration files, preventing credential leakage in error outputs.

IMPORTANT USAGE:
- Use redactor for HTTP responses, MCP tool returns, and client-facing messages
- DO NOT use for local server logs (keep full details for debugging)
- Local logs run on the user's machine and don't need redaction
- Only external communication to Claude should be sanitized

This prevents credentials from leaking in error messages sent to external clients
while preserving full details in local logs for debugging.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class CredentialRedactor:
    """
    Loads actual credential values from credentials.json and .env,
    uses exact string matching to redact them from error messages.

    USAGE:
    - Use for HTTP responses, MCP tool returns, client-facing messages
    - DO NOT use for local server logs (keep full details for debugging)
    - Local logs stay on user's machine; external responses go to Claude

    This prevents credential leakage in external communication while
    preserving full details in local logs for debugging.
    """

    def __init__(self):
        """Initialize the redactor and load credentials from config files."""
        self.credentials_to_redact: set[str] = set()
        self._load_credentials()
        logger.info(f"Credential redactor initialized with {len(self.credentials_to_redact)} credentials tracked")

    def _load_credentials(self) -> None:
        """Load exact credential values from credentials.json and .env files."""
        # Load from credentials.json
        self._load_from_credentials_json()

        # Load from .env file
        self._load_from_env()

    def _load_from_credentials_json(self) -> None:
        """Load credentials from credentials.json file."""
        credentials_path = Path(__file__).parent / "credentials.json"

        if not credentials_path.exists():
            logger.warning(f"credentials.json not found at {credentials_path}, skipping credential loading")
            return

        try:
            with open(credentials_path) as f:
                credentials = json.load(f)

            # Extract all credential values from the JSON structure
            for service_name, service_config in credentials.items():
                if isinstance(service_config, dict):
                    # Handle different credential structures
                    for key, value in service_config.items():
                        if isinstance(value, str) and len(value) > 0:
                            # Track specific credential fields
                            if key in (
                                "token",
                                "credential",
                                "app_password",
                                "identifier",
                                "auth_token",
                                "api_key",
                                "secret",
                                "client_id",
                                "client_secret",
                                "refresh_token",
                            ):
                                self.credentials_to_redact.add(value)

            logger.info(f"Loaded {len(self.credentials_to_redact)} credentials from credentials.json")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse credentials.json: {e}")
        except Exception as e:
            logger.error(f"Error loading credentials from credentials.json: {e}")

    def _load_from_env(self) -> None:
        """Load sensitive environment variables for redaction."""
        # List of environment variables containing credentials
        sensitive_env_vars = [
            "PROXY_SECRET_KEY",
            "GITHUB_CLIENT_SECRET",
            "GITHUB_CLIENT_ID",
            "GIT_PROXY_KEY",
        ]

        for env_var in sensitive_env_vars:
            value = os.environ.get(env_var)
            if value and len(value) > 0:
                self.credentials_to_redact.add(value)

        logger.debug(f"Loaded {len([v for v in sensitive_env_vars if os.environ.get(v)])} credentials from environment")

    def track_runtime_credential(self, credential: str) -> None:
        """
        Track runtime-generated credentials (e.g., ATProto JWTs).

        Some credentials are generated at runtime (like ATProto access/refresh JWTs)
        and need to be tracked separately since they won't be in config files.

        Args:
            credential: The credential string to track for redaction
        """
        if credential and len(credential) > 0:
            self.credentials_to_redact.add(credential)
            logger.debug(f"Tracking runtime credential (length: {len(credential)})")

    def redact(self, text: str) -> str:
        """
        Replace exact credential strings with [REDACTED].

        Uses simple string replacement for exact matching - no regex needed.
        This prevents false positives on similar-looking patterns.

        Args:
            text: The text to redact credentials from

        Returns:
            The text with all known credentials replaced with [REDACTED]
        """
        if not text:
            return text

        result = text
        for cred in self.credentials_to_redact:
            if cred and len(cred) > 0:
                result = result.replace(cred, "[REDACTED]")

        return result


# Global singleton instance
# Will be initialized when imported by proxy_server.py
_redactor_instance = None


def get_redactor() -> CredentialRedactor:
    """Get the global credential redactor instance."""
    global _redactor_instance
    if _redactor_instance is None:
        _redactor_instance = CredentialRedactor()
    return _redactor_instance
