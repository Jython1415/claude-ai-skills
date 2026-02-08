#!/usr/bin/env python3
"""
Credential Proxy Server

Provides:
- Git bundle operations for Claude.ai
- Session-based authentication
- Transparent credential proxying to upstream APIs

All file operations use temporary directories with automatic cleanup.
"""

from flask import Flask, request, jsonify, send_file
import subprocess
import os
import logging
from datetime import datetime
import tempfile
import shutil

# Local modules
from sessions import SessionStore
from credentials import CredentialStore
from proxy import forward_request
from error_redaction import get_redactor
from error_utils import error_response

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system env vars

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
SECRET_KEY = os.environ.get('PROXY_SECRET_KEY')
if not SECRET_KEY:
    logger.warning("PROXY_SECRET_KEY not set! Using insecure default.")
    SECRET_KEY = 'CHANGE-ME-INSECURE'

# Public URL for proxy (returned to Claude.ai scripts in session responses)
PUBLIC_PROXY_URL = os.environ.get('PUBLIC_PROXY_URL', 'https://proxy.joshuashew.com')

# Detect gh CLI at startup
GH_PATH = shutil.which('gh')
if not GH_PATH:
    # Try common Homebrew locations
    for path in ['/opt/homebrew/bin/gh', '/usr/local/bin/gh']:
        if os.path.exists(path) and os.access(path, os.X_OK):
            GH_PATH = path
            break

if GH_PATH:
    logger.info(f"GitHub CLI found at: {GH_PATH}")
else:
    logger.warning("GitHub CLI (gh) not found - PR creation will fail")

# Initialize session and credential stores
session_store = SessionStore()
credential_store = CredentialStore()

# Initialize credential redactor for sanitizing error messages
redactor = get_redactor()

logger.info(f"Loaded {len(credential_store.list_services())} service(s) from credential store")


def verify_auth(auth_header):
    """Verify legacy authentication token (X-Auth-Key)"""
    return auth_header == SECRET_KEY


def verify_session_or_key(service: str = 'git') -> bool:
    """
    Verify request has valid session (with service access) OR legacy auth key.

    Args:
        service: The service to check access for (default 'git')

    Returns:
        True if authorized, False otherwise
    """
    # Try session-based auth first
    session_id = request.headers.get('X-Session-Id')
    if session_id and session_store.has_service(session_id, service):
        return True

    # Fall back to legacy key-based auth
    auth_key = request.headers.get('X-Auth-Key')
    return verify_auth(auth_key)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint (no sensitive data exposed)"""
    return jsonify({
        'status': 'healthy',
        'mode': 'credential-proxy',
        'timestamp': datetime.now().isoformat()
    })


# =============================================================================
# Session Management Endpoints
# =============================================================================

@app.route('/sessions', methods=['POST'])
def create_session():
    """
    Create a new session granting access to specified services.

    Input: {"services": ["bsky", "github", "git"], "ttl_minutes": 30}
    Output: {"session_id": "...", "proxy_url": "...", "expires_in_minutes": 30, "services": [...]}

    Requires X-Auth-Key header (admin-only: MCP server creates sessions on behalf of users).
    """
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        logger.warning(f"Unauthorized session creation attempt from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401

    data = request.json or {}
    services = data.get('services', [])
    ttl_minutes = data.get('ttl_minutes', 30)

    if not services:
        return jsonify({'error': 'services list is required'}), 400

    if not isinstance(services, list):
        return jsonify({'error': 'services must be a list'}), 400

    # Validate services exist (git is always valid as pseudo-service)
    available = set(credential_store.list_services()) | {'git'}
    invalid = set(services) - available
    if invalid:
        return jsonify({
            'error': f'unknown services: {list(invalid)}',
            'available': sorted(available)
        }), 400

    session = session_store.create(services, ttl_minutes)

    # Use configured public URL (request.host resolves to localhost for internal callers)
    proxy_url = PUBLIC_PROXY_URL

    logger.info(f"Created session {session.session_id[:8]}... for services: {services}")

    return jsonify({
        'session_id': session.session_id,
        'proxy_url': proxy_url,
        'expires_in_minutes': ttl_minutes,
        'services': services
    })


@app.route('/sessions/<session_id>', methods=['DELETE'])
def revoke_session(session_id: str):
    """Revoke a session. Requires X-Auth-Key header."""
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        logger.warning(f"Unauthorized session revocation attempt from {request.remote_addr}")
        return jsonify({'error': 'unauthorized'}), 401

    if session_store.revoke(session_id):
        logger.info(f"Revoked session {session_id[:8]}...")
        return jsonify({'status': 'revoked'})
    return jsonify({'error': 'session not found'}), 404


@app.route('/services', methods=['GET'])
def list_services():
    """List available services. Requires X-Auth-Key header."""
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        return jsonify({'error': 'unauthorized'}), 401

    services = credential_store.list_services()
    # Always include 'git' as a pseudo-service
    if 'git' not in services:
        services = services + ['git']
    return jsonify({'services': sorted(services)})


# =============================================================================
# Transparent Proxy Endpoint
# =============================================================================

@app.route('/proxy/<service>/<path:rest>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
def proxy_request(service: str, rest: str):
    """
    Transparent proxy to upstream service.

    Requires valid X-Session-Id header with access to the service.
    Forwards request with credentials injected based on service config.
    """
    # Reject 'git' as a proxy service (it's not an upstream API)
    if service == 'git':
        return jsonify({
            'error': 'git is not a proxy service',
            'hint': 'Use /git/fetch-bundle or /git/push-bundle for git operations'
        }), 400

    session_id = request.headers.get('X-Session-Id')
    if not session_id:
        return jsonify({'error': 'missing X-Session-Id header'}), 401

    session = session_store.get(session_id)
    if session is None:
        return jsonify({'error': 'invalid or expired session'}), 401

    if not session.has_service(service):
        return jsonify({
            'error': f'session does not have access to {service}',
            'session_services': session.services
        }), 403

    return forward_request(
        service=service,
        path=rest,
        method=request.method,
        headers=dict(request.headers),
        body=request.get_data() if request.method in ['POST', 'PUT', 'PATCH'] else None,
        query_string=request.query_string.decode(),
        credential_store=credential_store
    )


# =============================================================================
# Git Bundle Endpoints
# =============================================================================

@app.route('/git/fetch-bundle', methods=['POST'])
def fetch_bundle():
    """
    Clone repository and return as git bundle (temporary operation)

    Input: {"repo_url": "https://github.com/user/repo.git", "branch": "main"}
    Output: Binary bundle file

    Files are cloned to temporary directory and cleaned up immediately after bundling.

    Authentication: X-Session-Id (with 'git' service) OR X-Auth-Key
    """
    # Verify authentication (session or legacy key)
    if not verify_session_or_key('git'):
        logger.warning("Unauthorized fetch-bundle attempt")
        return jsonify({'error': 'unauthorized'}), 401

    repo_url = None
    try:
        data = request.json
        repo_url = data.get('repo_url')
        branch = data.get('branch', 'main')

        if not repo_url:
            return jsonify({'error': 'missing repo_url'}), 400

        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        logger.info(f"Fetching bundle for {repo_url}")

        # Use temporary directory for clone (auto-cleanup)
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = os.path.join(temp_dir, repo_name)

            # Clone repository
            logger.info(f"Cloning {repo_url} to temporary directory")
            result = subprocess.run(
                ['git', 'clone', repo_url, repo_path],
                capture_output=True,
                timeout=300,
                text=True
            )
            if result.returncode != 0:
                # Log full details locally for debugging
                logger.error(f"Clone failed: {result.stderr}")

                # Interpret common git errors for client response
                stderr_lower = result.stderr.lower()
                if 'permission denied' in stderr_lower or 'authentication failed' in stderr_lower:
                    why = "SSH key authentication failed"
                    action = "Run 'ssh -T git@github.com' to test SSH access"
                elif 'not found' in stderr_lower or 'repository not found' in stderr_lower:
                    why = "Repository URL is incorrect or doesn't exist"
                    action = "Verify repository URL and credentials are correct"
                else:
                    why = "Git clone operation failed"
                    action = "Check repository URL and GitHub credentials"

                return error_response(
                    what="Clone failed",
                    why=why,
                    action=action,
                    status=500
                )

            # Create bundle file
            bundle_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bundle')
            bundle_path = bundle_file.name
            bundle_file.close()

            logger.info(f"Creating bundle")
            result = subprocess.run(
                ['git', 'bundle', 'create', bundle_path, '--all'],
                cwd=repo_path,
                capture_output=True,
                timeout=60,
                text=True
            )

            if result.returncode != 0:
                # Log full details locally for debugging
                logger.error(f"Bundle creation failed: {result.stderr}")
                os.unlink(bundle_path)
                return error_response(
                    what="Bundle creation failed",
                    why="Git bundle operation encountered an error",
                    action="Verify the repository has commits and is accessible",
                    status=500
                )

            logger.info(f"Bundle created successfully, temp repo cleaned up")

            # Return bundle file (temp bundle file will be cleaned up by Flask after sending)
            return send_file(
                bundle_path,
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=f'{repo_name}.bundle'
            )

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while fetching bundle for {repo_url}")
        return jsonify({'error': 'operation timeout'}), 408

    except Exception as e:
        # Log full exception for local debugging
        logger.error(f"Error creating bundle: {e}")
        # Return generic error to client (don't expose exception details)
        return error_response(
            what="Bundle operation failed",
            why="An unexpected error occurred",
            action="Check proxy server logs for details",
            status=500
        )


@app.route('/git/push-bundle', methods=['POST'])
def push_bundle():
    """
    Apply bundle and push to GitHub (temporary operation)

    Input:
        - bundle file (multipart/form-data)
        - repo_url (form field)
        - branch (form field)
        - create_pr (optional, form field: "true"/"false")
        - pr_title (optional, form field)
        - pr_body (optional, form field)
    Output: {"status": "success", "branch": "...", "pr_url": "..." (if created)}

    Files are cloned to temporary directory and cleaned up immediately after pushing.

    Authentication: X-Session-Id (with 'git' service) OR X-Auth-Key
    """
    # Verify authentication (session or legacy key)
    if not verify_session_or_key('git'):
        logger.warning("Unauthorized push-bundle attempt")
        return jsonify({'error': 'unauthorized'}), 401

    repo_url = None
    branch = None
    temp_bundle_path = None

    try:
        # Get form data
        repo_url = request.form.get('repo_url')
        branch = request.form.get('branch')
        create_pr = request.form.get('create_pr', 'false').lower() == 'true'
        pr_title = request.form.get('pr_title', '')
        pr_body = request.form.get('pr_body', '')

        if not repo_url or not branch:
            return jsonify({'error': 'missing repo_url or branch'}), 400

        # Get bundle file
        if 'bundle' not in request.files:
            return jsonify({'error': 'missing bundle file'}), 400

        bundle_file = request.files['bundle']

        # Save bundle to temp file
        temp_bundle = tempfile.NamedTemporaryFile(delete=False, suffix='.bundle')
        temp_bundle_path = temp_bundle.name
        bundle_file.save(temp_bundle_path)
        temp_bundle.close()

        logger.info(f"Pushing bundle for {repo_url}, branch {branch}")

        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')

        # Use temporary directory for all operations
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = os.path.join(temp_dir, repo_name)

            # Clone repository
            logger.info(f"Cloning {repo_url} to temporary directory")
            result = subprocess.run(
                ['git', 'clone', repo_url, repo_path],
                capture_output=True,
                timeout=300,
                text=True
            )
            if result.returncode != 0:
                # Log full details locally for debugging
                logger.error(f"Clone failed: {result.stderr}")

                # Interpret common git errors for client response
                stderr_lower = result.stderr.lower()
                if 'permission denied' in stderr_lower or 'authentication failed' in stderr_lower:
                    why = "SSH key authentication failed"
                    action = "Run 'ssh -T git@github.com' to test SSH access"
                elif 'not found' in stderr_lower or 'repository not found' in stderr_lower:
                    why = "Repository URL is incorrect or doesn't exist"
                    action = "Verify repository URL and credentials are correct"
                else:
                    why = "Git clone operation failed"
                    action = "Check repository URL and GitHub credentials"

                return error_response(
                    what="Clone failed",
                    why=why,
                    action=action,
                    status=500
                )

            # Fetch bundle into repository
            logger.info(f"Fetching bundle into {branch}")
            result = subprocess.run(
                ['git', 'fetch', temp_bundle_path, f'{branch}:{branch}'],
                cwd=repo_path,
                capture_output=True,
                timeout=60,
                text=True
            )

            if result.returncode != 0:
                # Log full details locally for debugging
                logger.error(f"Bundle fetch failed: {result.stderr}")
                return error_response(
                    what="Bundle fetch failed",
                    why="Failed to apply bundle to repository",
                    action=f"Verify the bundle file is valid and branch '{branch}' is correct",
                    status=500
                )

            # Push branch to remote
            logger.info(f"Pushing {branch} to origin")
            result = subprocess.run(
                ['git', 'push', 'origin', branch],
                cwd=repo_path,
                capture_output=True,
                timeout=60,
                text=True
            )

            if result.returncode != 0:
                # Log full details locally for debugging
                logger.error(f"Push failed: {result.stderr}")

                # Interpret common push errors for client response
                stderr_lower = result.stderr.lower()
                if 'rejected' in stderr_lower or 'protected branch' in stderr_lower:
                    why = "Branch is protected or push was rejected"
                    action = f"Check branch protection rules for '{branch}' on GitHub"
                elif 'permission denied' in stderr_lower or 'authentication failed' in stderr_lower:
                    why = "SSH key authentication failed"
                    action = "Verify GitHub SSH access and push permissions"
                else:
                    why = "Git push operation failed"
                    action = "Check repository push permissions and network connectivity"

                return error_response(
                    what="Push failed",
                    why=why,
                    action=action,
                    status=500
                )

            response = {
                'status': 'success',
                'branch': branch,
                'message': f'Branch {branch} pushed successfully'
            }

            # Create PR if requested
            if create_pr:
                if not GH_PATH:
                    # gh CLI not available - provide manual URL
                    logger.warning("PR creation requested but gh CLI not available")
                    response['pr_created'] = False
                    try:
                        repo_parts = repo_url.rstrip('/').replace('.git', '').split('/')
                        owner = repo_parts[-2]
                        repo = repo_parts[-1]
                        manual_url = f"https://github.com/{owner}/{repo}/pull/new/{branch}"
                        response['manual_pr_url'] = manual_url
                        response['pr_message'] = f"GitHub CLI not available on server. Create PR manually at: {manual_url}"
                    except:
                        response['pr_message'] = "GitHub CLI not available. Create PR manually on GitHub."
                else:
                    logger.info(f"Creating PR for {branch} using {GH_PATH}")

                    if not pr_title:
                        pr_title = f"Changes from {branch}"

                    gh_cmd = [GH_PATH, 'pr', 'create', '--title', pr_title, '--body', pr_body or 'Automated PR from Claude', '--head', branch]

                    result = subprocess.run(
                        gh_cmd,
                        cwd=repo_path,
                        capture_output=True,
                        timeout=60,
                        text=True
                    )

                    if result.returncode == 0:
                        pr_url = result.stdout.strip()
                        response['pr_created'] = True
                        response['pr_url'] = pr_url
                        logger.info(f"PR created: {pr_url}")
                    else:
                        # Log full details locally for debugging
                        logger.warning(f"PR creation failed: {result.stderr}")
                        response['pr_created'] = False
                        response['pr_error'] = "PR creation failed"  # Generic error for client

                        # Provide manual PR URL as fallback
                        try:
                            repo_parts = repo_url.rstrip('/').replace('.git', '').split('/')
                            owner = repo_parts[-2]
                            repo = repo_parts[-1]
                            manual_url = f"https://github.com/{owner}/{repo}/pull/new/{branch}"
                            response['manual_pr_url'] = manual_url
                            response['pr_message'] = f"PR creation failed. Create manually at: {manual_url}"
                        except:
                            pass

            logger.info(f"Push complete, temp repo cleaned up")
            return jsonify(response)

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while pushing bundle for {repo_url} {branch}")
        return jsonify({'error': 'operation timeout'}), 408

    except Exception as e:
        # Log full exception for local debugging
        logger.error(f"Error pushing bundle: {e}")
        # Return generic error to client (don't expose exception details)
        return error_response(
            what="Push operation failed",
            why="An unexpected error occurred",
            action="Check proxy server logs for details",
            status=500
        )

    finally:
        # Clean up temp bundle file
        if temp_bundle_path and os.path.exists(temp_bundle_path):
            os.unlink(temp_bundle_path)


if __name__ == '__main__':
    logger.info("Starting Credential Proxy Server")
    logger.info("Mode: Session-based auth + transparent credential proxy")
    logger.info(f"Legacy auth key configured: {bool(os.environ.get('PROXY_SECRET_KEY'))}")
    logger.info(f"Services available: {credential_store.list_services() + ['git']}")

    # Run server
    app.run(
        host='127.0.0.1',
        port=int(os.environ.get('PORT', 8443)),
        debug=os.environ.get('DEBUG', 'False').lower() == 'true'
    )
