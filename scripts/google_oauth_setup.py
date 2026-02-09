#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///

"""
Interactive CLI script for one-time Google OAuth2 setup.

This script helps you set up OAuth2 credentials for Google services
(Gmail, Calendar, Drive) and stores them in credentials.json for use
with the claude-ai-skills MCP server.

Usage:
    python google_oauth_setup.py

The script will:
1. Prompt for Google Cloud client_id and client_secret
2. Let you select which Google services to authorize
3. Open a browser for Google consent
4. Exchange the authorization code for a refresh token
5. Save credentials to ../server/credentials.json
"""

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: This script requires the 'requests' package.")
    print("Install it with: pip install requests")
    sys.exit(1)

# Google OAuth2 endpoints
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Scope mappings
SCOPE_MAPPINGS = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ],
    "calendar": ["https://www.googleapis.com/auth/calendar"],
    "drive": ["https://www.googleapis.com/auth/drive.readonly"],
}

# Known service names (these have defaults in the server)
KNOWN_SERVICES = {"gmail", "gcal", "gdrive"}

# Base URLs for custom service names
SERVICE_BASE_URLS = {
    "gmail": "https://gmail.googleapis.com",
    "calendar": "https://www.googleapis.com/calendar/v3",
    "drive": "https://www.googleapis.com/drive/v3",
}


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):
        """Handle GET request from OAuth callback."""
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"""
                <html>
                <head><title>Authorization Successful</title></head>
                <body>
                <h1>Authorization successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
                """
            )
        elif "error" in params:
            OAuthCallbackHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
                <html>
                <head><title>Authorization Failed</title></head>
                <body>
                <h1>Authorization failed</h1>
                <p>Error: {params['error'][0]}</p>
                <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
                """.encode()
            )
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Invalid callback</h1></body></html>")

    def log_message(self, format, *args):
        """Suppress server log messages."""
        pass


def get_input(prompt: str, required: bool = True) -> str:
    """Get user input with optional requirement."""
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("This field is required. Please try again.")


def select_scopes() -> list[str]:
    """Present scope menu and return selected scopes."""
    print("\nSelect Google services to authorize:")
    print("1. Gmail (read + send)")
    print("2. Calendar (full access)")
    print("3. Drive (read-only)")
    print("4. All of the above")

    while True:
        choice = get_input("\nEnter choice (1-4): ")
        if choice == "1":
            return SCOPE_MAPPINGS["gmail"]
        elif choice == "2":
            return SCOPE_MAPPINGS["calendar"]
        elif choice == "3":
            return SCOPE_MAPPINGS["drive"]
        elif choice == "4":
            scopes = []
            for scope_list in SCOPE_MAPPINGS.values():
                scopes.extend(scope_list)
            return scopes
        else:
            print("Invalid choice. Please enter 1-4.")


def start_oauth_flow(
    client_id: str, client_secret: str, scopes: list[str], port: int = 8080
) -> Optional[str]:
    """
    Start OAuth flow and return refresh token.

    Args:
        client_id: Google Cloud OAuth client ID
        client_secret: Google Cloud OAuth client secret
        scopes: List of OAuth scopes to request
        port: Local port for callback server

    Returns:
        Refresh token if successful, None otherwise
    """
    redirect_uri = f"http://localhost:{port}"

    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"

    print(f"\nOpening browser for Google authorization...")
    print(f"If the browser doesn't open, visit this URL manually:")
    print(f"\n{auth_url}\n")

    # Open browser
    webbrowser.open(auth_url)

    # Start local server to receive callback
    print(f"Starting local server on port {port}...")
    print("Waiting for authorization callback...\n")

    server = HTTPServer(("localhost", port), OAuthCallbackHandler)

    # Handle a single request
    server.handle_request()

    if OAuthCallbackHandler.error:
        print(f"\nAuthorization failed: {OAuthCallbackHandler.error}")
        return None

    if not OAuthCallbackHandler.auth_code:
        print("\nNo authorization code received.")
        return None

    auth_code = OAuthCallbackHandler.auth_code
    print("Authorization code received! Exchanging for refresh token...\n")

    # Exchange authorization code for tokens
    try:
        token_data = {
            "code": auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(TOKEN_URL, data=token_data, timeout=30)
        response.raise_for_status()

        tokens = response.json()

        if "refresh_token" not in tokens:
            print(
                "Warning: No refresh token received. This can happen if you've "
                "already authorized this app."
            )
            print(
                "Try revoking access at https://myaccount.google.com/permissions "
                "and run this script again."
            )
            return None

        return tokens["refresh_token"]

    except requests.RequestException as e:
        print(f"Error exchanging authorization code: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Server response: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Server response: {e.response.text}")
        return None


def determine_service_type(service_name: str, scopes: list[str]) -> str:
    """Determine service type based on service name or scopes."""
    service_lower = service_name.lower()

    # Check for known patterns in service name
    if "gmail" in service_lower or "mail" in service_lower:
        return "gmail"
    elif "cal" in service_lower:
        return "calendar"
    elif "drive" in service_lower:
        return "drive"

    # Check scopes
    scope_str = " ".join(scopes)
    if "gmail" in scope_str:
        return "gmail"
    elif "calendar" in scope_str:
        return "calendar"
    elif "drive" in scope_str:
        return "drive"

    # Default to gmail
    return "gmail"


def save_credentials(
    service_name: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str],
) -> bool:
    """
    Save credentials to credentials.json.

    Args:
        service_name: Name of the service (e.g., 'gmail', 'gmail_work')
        client_id: Google Cloud OAuth client ID
        client_secret: Google Cloud OAuth client secret
        refresh_token: OAuth refresh token
        scopes: List of authorized scopes

    Returns:
        True if successful, False otherwise
    """
    # Determine credentials file path (../server/credentials.json relative to script)
    script_dir = Path(__file__).parent
    creds_file = script_dir.parent / "server" / "credentials.json"

    # Load existing credentials if present
    credentials = {}
    if creds_file.exists():
        try:
            with open(creds_file, "r") as f:
                credentials = json.load(f)
            print(f"Loaded existing credentials from {creds_file}")
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse existing credentials.json: {e}")
            print("Creating new credentials file.")
        except Exception as e:
            print(f"Warning: Could not read credentials.json: {e}")
            print("Creating new credentials file.")

    # Create service entry
    service_entry = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    # For custom service names (not in KNOWN_SERVICES), add base_url and type
    if service_name not in KNOWN_SERVICES:
        service_type = determine_service_type(service_name, scopes)
        service_entry["type"] = "oauth2"

        # Add base_url based on service type
        if service_type in SERVICE_BASE_URLS:
            service_entry["base_url"] = SERVICE_BASE_URLS[service_type]

    # Merge into credentials
    credentials[service_name] = service_entry

    # Ensure parent directory exists
    creds_file.parent.mkdir(parents=True, exist_ok=True)

    # Write credentials file
    try:
        with open(creds_file, "w") as f:
            json.dump(credentials, f, indent=2)
        print(f"\nCredentials saved to {creds_file}")
        print(f"Service name: {service_name}")
        return True
    except Exception as e:
        print(f"Error saving credentials: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Google OAuth2 Setup for claude-ai-skills")
    print("=" * 60)

    print(
        """
This script will help you set up Google OAuth2 credentials.

Before starting, make sure you have:
1. Created a Google Cloud project
2. Enabled the required APIs (Gmail, Calendar, Drive)
3. Created OAuth 2.0 credentials (Desktop app type)
4. Added http://localhost:8080 to authorized redirect URIs

You can do this at: https://console.cloud.google.com/apis/credentials
"""
    )

    input("Press Enter to continue...")

    # Get client credentials
    print("\n" + "-" * 60)
    print("Step 1: Enter Google Cloud OAuth credentials")
    print("-" * 60)

    client_id = get_input("\nEnter client_id: ")
    client_secret = get_input("Enter client_secret: ")

    # Select scopes
    print("\n" + "-" * 60)
    print("Step 2: Select services to authorize")
    print("-" * 60)

    scopes = select_scopes()
    print(f"\nSelected scopes: {', '.join(scopes)}")

    # Get service name
    print("\n" + "-" * 60)
    print("Step 3: Choose service name")
    print("-" * 60)
    print(
        """
Service name is used to identify this credential set.
For known services (gmail, gcal, gdrive), use these exact names.
For multi-account setup, use descriptive names like 'gmail_work' or 'gmail_personal'.
"""
    )

    service_name = get_input("Enter service name: ")

    # Get port (optional)
    print("\n" + "-" * 60)
    print("Step 4: Configure callback server")
    print("-" * 60)

    port_input = get_input("Enter callback port (default: 8080): ", required=False)
    port = int(port_input) if port_input else 8080

    # Start OAuth flow
    print("\n" + "-" * 60)
    print("Step 5: Authorize with Google")
    print("-" * 60)

    try:
        refresh_token = start_oauth_flow(client_id, client_secret, scopes, port)

        if not refresh_token:
            print("\nOAuth flow failed. Please try again.")
            sys.exit(1)

        print("Successfully obtained refresh token!")

        # Save credentials
        print("\n" + "-" * 60)
        print("Step 6: Save credentials")
        print("-" * 60)

        if save_credentials(
            service_name, client_id, client_secret, refresh_token, scopes
        ):
            print("\n" + "=" * 60)
            print("Setup completed successfully!")
            print("=" * 60)
            print(
                f"""
Your credentials have been saved. You can now use the service '{service_name}'
with the claude-ai-skills MCP server.

To set up additional Google accounts, run this script again with a different
service name (e.g., 'gmail_work', 'gmail_personal').
"""
            )
        else:
            print("\nFailed to save credentials. Please try again.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
