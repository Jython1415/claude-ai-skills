#!/usr/bin/env python3
"""
Git Proxy Server
Executes git commands on behalf of Claude.ai skills via HTTPS
"""

from flask import Flask, request, jsonify, send_file
import subprocess
import base64
import os
import logging
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

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

WORKSPACE_DIR = Path(os.environ.get('GIT_WORKSPACE', os.path.expanduser('~/git-proxy-workspace')))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Request logging
REQUEST_LOG = WORKSPACE_DIR / 'requests.log'


def log_request(endpoint, status, details=''):
    """Log all requests for audit trail"""
    with open(REQUEST_LOG, 'a') as f:
        timestamp = datetime.now().isoformat()
        f.write(f"{timestamp} | {endpoint} | {status} | {details}\n")


def verify_auth(auth_header):
    """Verify authentication token"""
    return auth_header == SECRET_KEY


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'workspace': str(WORKSPACE_DIR),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/git-exec', methods=['POST'])
def git_exec():
    """Execute git command"""

    # Verify authentication
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        log_request('/git-exec', 'UNAUTHORIZED', 'Invalid auth key')
        return jsonify({'error': 'unauthorized'}), 401

    try:
        data = request.json

        # Decode command
        encoded_cmd = data.get('command')
        if not encoded_cmd:
            return jsonify({'error': 'missing command'}), 400

        cmd = base64.b64decode(encoded_cmd).decode('utf-8')

        # Security: only allow git and gh commands
        allowed_commands = ('git ', 'gh ')
        if not cmd.strip().startswith(allowed_commands):
            log_request('/git-exec', 'FORBIDDEN', f'Disallowed command: {cmd}')
            return jsonify({'error': 'only git and gh commands allowed'}), 403

        # Get working directory
        cwd = data.get('cwd', str(WORKSPACE_DIR))
        cwd_path = Path(cwd)

        # Security: ensure cwd is within workspace
        try:
            cwd_path.resolve().relative_to(WORKSPACE_DIR.resolve())
        except ValueError:
            # If cwd is not relative to workspace, use workspace
            cwd_path = WORKSPACE_DIR

        # Ensure directory exists
        cwd_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Executing: {cmd} in {cwd_path}")
        log_request('/git-exec', 'EXECUTING', cmd)

        # Execute command
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=60,
            cwd=str(cwd_path)
        )

        # Encode results
        response = {
            'stdout': base64.b64encode(result.stdout).decode('utf-8'),
            'stderr': base64.b64encode(result.stderr).decode('utf-8'),
            'returncode': result.returncode
        }

        log_request('/git-exec', 'SUCCESS', f'returncode={result.returncode}')
        return jsonify(response)

    except subprocess.TimeoutExpired:
        log_request('/git-exec', 'TIMEOUT', cmd)
        return jsonify({'error': 'command timeout'}), 408

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        log_request('/git-exec', 'ERROR', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/workspace/list', methods=['GET'])
def list_workspace():
    """List repositories in workspace"""

    # Verify authentication
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        return jsonify({'error': 'unauthorized'}), 401

    try:
        repos = []
        for item in WORKSPACE_DIR.iterdir():
            if item.is_dir() and (item / '.git').exists():
                repos.append({
                    'name': item.name,
                    'path': str(item)
                })

        return jsonify({'repositories': repos})

    except Exception as e:
        logger.error(f"Error listing workspace: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/git/fetch-bundle', methods=['POST'])
def fetch_bundle():
    """
    Clone repository and return as git bundle

    Input: {"repo_url": "https://github.com/user/repo.git", "branch": "main"}
    Output: Binary bundle file
    """
    # Verify authentication
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        log_request('/git/fetch-bundle', 'UNAUTHORIZED', 'Invalid auth key')
        return jsonify({'error': 'unauthorized'}), 401

    try:
        data = request.json
        repo_url = data.get('repo_url')
        branch = data.get('branch', 'main')

        if not repo_url:
            return jsonify({'error': 'missing repo_url'}), 400

        # Extract repo name from URL
        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = WORKSPACE_DIR / repo_name

        logger.info(f"Fetching bundle for {repo_url}")
        log_request('/git/fetch-bundle', 'PROCESSING', repo_url)

        # Clone or update repository
        if not repo_path.exists():
            logger.info(f"Cloning {repo_url} to {repo_path}")
            result = subprocess.run(
                ['git', 'clone', repo_url, str(repo_path)],
                capture_output=True,
                timeout=300,
                text=True
            )
            if result.returncode != 0:
                logger.error(f"Clone failed: {result.stderr}")
                return jsonify({'error': f'clone failed: {result.stderr}'}), 500
        else:
            logger.info(f"Updating existing repo at {repo_path}")
            result = subprocess.run(
                ['git', 'fetch', '--all'],
                cwd=str(repo_path),
                capture_output=True,
                timeout=300,
                text=True
            )
            if result.returncode != 0:
                logger.warning(f"Fetch failed: {result.stderr}")

        # Create bundle
        bundle_file = tempfile.NamedTemporaryFile(delete=False, suffix='.bundle')
        bundle_path = bundle_file.name
        bundle_file.close()

        logger.info(f"Creating bundle at {bundle_path}")
        result = subprocess.run(
            ['git', 'bundle', 'create', bundle_path, '--all'],
            cwd=str(repo_path),
            capture_output=True,
            timeout=60,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"Bundle creation failed: {result.stderr}")
            os.unlink(bundle_path)
            return jsonify({'error': f'bundle creation failed: {result.stderr}'}), 500

        log_request('/git/fetch-bundle', 'SUCCESS', f'{repo_name}.bundle created')

        # Return bundle file
        return send_file(
            bundle_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=f'{repo_name}.bundle'
        )

    except subprocess.TimeoutExpired:
        log_request('/git/fetch-bundle', 'TIMEOUT', repo_url)
        return jsonify({'error': 'operation timeout'}), 408

    except Exception as e:
        logger.error(f"Error creating bundle: {e}")
        log_request('/git/fetch-bundle', 'ERROR', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/git/push-bundle', methods=['POST'])
def push_bundle():
    """
    Apply bundle and push to GitHub

    Input:
        - bundle file (multipart/form-data)
        - repo_url (form field)
        - branch (form field)
        - create_pr (optional, form field: "true"/"false")
        - pr_title (optional, form field)
        - pr_body (optional, form field)
    Output: {"status": "success", "branch": "...", "pr_url": "..." (if created)}
    """
    # Verify authentication
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
        log_request('/git/push-bundle', 'UNAUTHORIZED', 'Invalid auth key')
        return jsonify({'error': 'unauthorized'}), 401

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
        bundle_file.save(temp_bundle.name)
        temp_bundle.close()

        logger.info(f"Pushing bundle for {repo_url}, branch {branch}")
        log_request('/git/push-bundle', 'PROCESSING', f'{repo_url} {branch}')

        # Extract repo name from URL
        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = WORKSPACE_DIR / repo_name

        # Clone repository if not exists
        if not repo_path.exists():
            logger.info(f"Cloning {repo_url} to {repo_path}")
            result = subprocess.run(
                ['git', 'clone', repo_url, str(repo_path)],
                capture_output=True,
                timeout=300,
                text=True
            )
            if result.returncode != 0:
                os.unlink(temp_bundle.name)
                logger.error(f"Clone failed: {result.stderr}")
                return jsonify({'error': f'clone failed: {result.stderr}'}), 500

        # Fetch bundle
        logger.info(f"Fetching bundle into {branch}")
        result = subprocess.run(
            ['git', 'fetch', temp_bundle.name, f'{branch}:{branch}'],
            cwd=str(repo_path),
            capture_output=True,
            timeout=60,
            text=True
        )

        os.unlink(temp_bundle.name)

        if result.returncode != 0:
            logger.error(f"Bundle fetch failed: {result.stderr}")
            return jsonify({'error': f'bundle fetch failed: {result.stderr}'}), 500

        # Push branch to remote
        logger.info(f"Pushing {branch} to origin")
        result = subprocess.run(
            ['git', 'push', 'origin', branch],
            cwd=str(repo_path),
            capture_output=True,
            timeout=60,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"Push failed: {result.stderr}")
            return jsonify({'error': f'push failed: {result.stderr}'}), 500

        response = {
            'status': 'success',
            'branch': branch,
            'message': f'Branch {branch} pushed successfully'
        }

        # Create PR if requested
        if create_pr:
            logger.info(f"Creating PR for {branch}")

            # Use pr_title or generate from branch name
            if not pr_title:
                pr_title = f"Changes from {branch}"

            gh_cmd = ['gh', 'pr', 'create', '--title', pr_title, '--body', pr_body or 'Automated PR from Claude', '--head', branch]

            result = subprocess.run(
                gh_cmd,
                cwd=str(repo_path),
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
                logger.warning(f"PR creation failed: {result.stderr}")
                response['pr_created'] = False
                response['pr_error'] = result.stderr

        log_request('/git/push-bundle', 'SUCCESS', f'{branch} pushed')
        return jsonify(response)

    except subprocess.TimeoutExpired:
        log_request('/git/push-bundle', 'TIMEOUT', f'{repo_url} {branch}')
        return jsonify({'error': 'operation timeout'}), 408

    except Exception as e:
        logger.error(f"Error pushing bundle: {e}")
        log_request('/git/push-bundle', 'ERROR', str(e))
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info(f"Starting Git Proxy Server")
    logger.info(f"Workspace: {WORKSPACE_DIR}")
    logger.info(f"Secret key configured: {bool(os.environ.get('PROXY_SECRET_KEY'))}")

    # Run server
    app.run(
        host='127.0.0.1',
        port=int(os.environ.get('PORT', 8443)),
        debug=os.environ.get('DEBUG', 'False').lower() == 'true'
    )
