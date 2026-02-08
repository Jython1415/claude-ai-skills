"""
Credential Store for Credential Proxy

Service-aware credential handling with built-in support for:
- ATProto (Bluesky): Automatic session management with identifier + app_password
- Bearer token APIs: Simple token injection
- Git: Pseudo-service using local git/gh CLI (no credentials needed)
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from error_redaction import get_redactor

logger = logging.getLogger(__name__)

# Initialize credential redactor for tracking runtime JWTs
redactor = get_redactor()


# Known service configurations (base URLs, auth flows)
KNOWN_SERVICES = {
    "bsky": {"base_url": "https://bsky.social/xrpc", "type": "atproto"},
    "github_api": {"base_url": "https://api.github.com", "type": "bearer"},
}


@dataclass
class ATProtoSession:
    """Cached ATProto session with access and refresh tokens."""

    access_jwt: str
    refresh_jwt: str
    did: str
    handle: str
    expires_at: datetime


@dataclass
class ServiceCredential:
    """Configuration for a proxied service."""

    service_type: str  # "atproto", "bearer", "header", "query"
    base_url: str

    # For bearer/header/query types
    credential: str | None = None
    auth_header: str | None = None  # For type="header"
    query_param: str | None = None  # For type="query"

    # For ATProto type
    identifier: str | None = None
    app_password: str | None = None
    _atproto_session: ATProtoSession | None = field(default=None, repr=False)
    _session_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inject_auth(self, headers: dict, url: str) -> tuple[dict, str]:
        """
        Inject authentication into request headers and/or URL.

        Args:
            headers: Request headers dict (will be modified)
            url: Request URL

        Returns:
            Tuple of (modified headers, modified URL)
        """
        headers = dict(headers)  # Copy to avoid modifying original

        if self.service_type == "atproto":
            # Get or refresh ATProto session token
            token = self._get_atproto_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                logger.error("Failed to get ATProto session token")

        elif self.service_type == "bearer":
            if self.credential:
                headers["Authorization"] = f"Bearer {self.credential}"

        elif self.service_type == "header":
            header_name = self.auth_header or "X-API-Key"
            if self.credential:
                headers[header_name] = self.credential

        elif self.service_type == "query":
            param_name = self.query_param or "api_key"
            if self.credential:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}{param_name}={self.credential}"

        return headers, url

    def _get_atproto_token(self) -> str | None:
        """Get a valid ATProto access token, creating/refreshing session as needed."""
        with self._session_lock:
            now = datetime.utcnow()

            # Check if we have a valid cached session
            if self._atproto_session:
                # Refresh if token expires in less than 5 minutes
                if self._atproto_session.expires_at > now + timedelta(minutes=5):
                    return self._atproto_session.access_jwt

                # Try to refresh
                if self._refresh_atproto_session():
                    return self._atproto_session.access_jwt

            # Create new session
            if self._create_atproto_session():
                return self._atproto_session.access_jwt

            return None

    def _create_atproto_session(self) -> bool:
        """Create a new ATProto session using identifier and app password."""
        if not self.identifier or not self.app_password:
            logger.error("ATProto service missing identifier or app_password")
            return False

        try:
            response = requests.post(
                f"{self.base_url}/com.atproto.server.createSession",
                json={"identifier": self.identifier, "password": self.app_password},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            # ATProto access tokens typically expire in 2 hours
            self._atproto_session = ATProtoSession(
                access_jwt=data["accessJwt"],
                refresh_jwt=data["refreshJwt"],
                did=data["did"],
                handle=data["handle"],
                expires_at=datetime.utcnow() + timedelta(hours=2),
            )

            # Track JWTs for redaction in error messages
            redactor.track_runtime_credential(data["accessJwt"])
            redactor.track_runtime_credential(data["refreshJwt"])

            logger.info(f"Created ATProto session for {data['handle']}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create ATProto session: {e}")
            return False

    def _refresh_atproto_session(self) -> bool:
        """Refresh an existing ATProto session."""
        if not self._atproto_session:
            return False

        try:
            response = requests.post(
                f"{self.base_url}/com.atproto.server.refreshSession",
                headers={"Authorization": f"Bearer {self._atproto_session.refresh_jwt}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            self._atproto_session = ATProtoSession(
                access_jwt=data["accessJwt"],
                refresh_jwt=data["refreshJwt"],
                did=data["did"],
                handle=data["handle"],
                expires_at=datetime.utcnow() + timedelta(hours=2),
            )

            # Track refreshed JWTs for redaction in error messages
            redactor.track_runtime_credential(data["accessJwt"])
            redactor.track_runtime_credential(data["refreshJwt"])

            logger.info(f"Refreshed ATProto session for {data['handle']}")
            return True

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to refresh ATProto session: {e}")
            self._atproto_session = None
            return False


class CredentialStore:
    """
    Load and manage service credentials from a JSON configuration file.

    Simplified JSON structure:
    {
        "bsky": {
            "identifier": "handle.bsky.social",
            "app_password": "xxxx-xxxx-xxxx-xxxx"
        },
        "github_api": {
            "token": "ghp_..."
        }
    }

    Known services (bsky, github_api) have hardcoded base URLs and auth types.
    Custom services can specify full configuration.
    """

    def __init__(self, config_path: str | None = None):
        """
        Initialize credential store from config file.

        Args:
            config_path: Path to credentials.json. Defaults to same directory as this file.
        """
        self._credentials: dict[str, ServiceCredential] = {}
        self._last_mtime: float = 0

        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "credentials.json")

        self._config_path = config_path
        self._load()

    def _check_reload(self) -> None:
        """Reload credentials if the config file has been modified."""
        try:
            mtime = os.path.getmtime(self._config_path)
        except OSError:
            return
        if mtime != self._last_mtime:
            logger.info("Credentials file changed, reloading...")
            self.reload()

    def _load(self) -> None:
        """Load credentials from JSON file."""
        if not os.path.exists(self._config_path):
            logger.warning(f"Credentials file not found: {self._config_path}")
            logger.info("Create credentials.json from credentials.example.json")
            return

        try:
            self._last_mtime = os.path.getmtime(self._config_path)
            with open(self._config_path) as f:
                config = json.load(f)

            for service_name, service_config in config.items():
                try:
                    cred = self._parse_service_config(service_name, service_config)
                    if cred:
                        self._credentials[service_name] = cred
                        logger.info(f"Loaded credentials for service: {service_name} (type: {cred.service_type})")
                except Exception as e:
                    logger.error(f"Error loading service {service_name}: {e}")

            logger.info(f"Loaded {len(self._credentials)} service(s) from {self._config_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self._config_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")

    def _parse_service_config(self, name: str, config: dict) -> ServiceCredential | None:
        """Parse a service configuration, using known defaults where applicable."""

        # Check if this is a known service
        known = KNOWN_SERVICES.get(name, {})
        base_url = config.get("base_url") or known.get("base_url")
        service_type = config.get("type") or known.get("type")

        if not base_url:
            logger.error(f"Service {name}: base_url required (not a known service)")
            return None

        # Infer type from config keys if not specified
        if not service_type:
            if "identifier" in config or "app_password" in config:
                service_type = "atproto"
            elif "token" in config or "credential" in config:
                service_type = "bearer"
            else:
                logger.error(f"Service {name}: cannot infer service type")
                return None

        # Build ServiceCredential based on type
        if service_type == "atproto":
            return ServiceCredential(
                service_type="atproto",
                base_url=base_url,
                identifier=config.get("identifier"),
                app_password=config.get("app_password"),
            )

        elif service_type == "bearer":
            return ServiceCredential(
                service_type="bearer", base_url=base_url, credential=config.get("token") or config.get("credential")
            )

        elif service_type == "header":
            return ServiceCredential(
                service_type="header",
                base_url=base_url,
                credential=config.get("credential"),
                auth_header=config.get("auth_header"),
            )

        elif service_type == "query":
            return ServiceCredential(
                service_type="query",
                base_url=base_url,
                credential=config.get("credential"),
                query_param=config.get("query_param"),
            )

        else:
            logger.error(f"Service {name}: unknown service type '{service_type}'")
            return None

    def get(self, service: str) -> ServiceCredential | None:
        """
        Get credential configuration for a service.

        Args:
            service: Service name

        Returns:
            ServiceCredential if found, None otherwise
        """
        self._check_reload()
        return self._credentials.get(service)

    def list_services(self) -> list[str]:
        """
        List all configured service names.

        Returns:
            List of service names
        """
        self._check_reload()
        return sorted(self._credentials.keys())

    def has_service(self, service: str) -> bool:
        """
        Check if a service is configured.

        Args:
            service: Service name to check

        Returns:
            True if service exists in credential store
        """
        return service in self._credentials

    def reload(self) -> None:
        """Reload credentials from config file."""
        self._credentials.clear()
        self._load()
