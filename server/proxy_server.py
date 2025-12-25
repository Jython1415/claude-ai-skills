#!/usr/bin/env python3
"""
Git Bundle Proxy Server
Provides bundle-based git operations for Claude.ai via HTTPS
Files are processed in temporary directories and cleaned up immediately
"""

from flask import Flask, request, jsonify, send_file
import subprocess
import os
import logging
from datetime import datetime
import tempfile

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


def verify_auth(auth_header):
    """Verify authentication token"""
    return auth_header == SECRET_KEY


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'mode': 'bundle-proxy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/git/fetch-bundle', methods=['POST'])
def fetch_bundle():
    """
    Clone repository and return as git bundle (temporary operation)

    Input: {"repo_url": "https://github.com/user/repo.git", "branch": "main"}
    Output: Binary bundle file

    Files are cloned to temporary directory and cleaned up immediately after bundling.
    """
    # Verify authentication
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
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
                logger.error(f"Clone failed: {result.stderr}")
                return jsonify({'error': f'clone failed: {result.stderr}'}), 500

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
                logger.error(f"Bundle creation failed: {result.stderr}")
                os.unlink(bundle_path)
                return jsonify({'error': f'bundle creation failed: {result.stderr}'}), 500

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
        logger.error(f"Error creating bundle: {e}")
        return jsonify({'error': str(e)}), 500


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
    """
    # Verify authentication
    auth_key = request.headers.get('X-Auth-Key')
    if not verify_auth(auth_key):
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
                logger.error(f"Clone failed: {result.stderr}")
                return jsonify({'error': f'clone failed: {result.stderr}'}), 500

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
                logger.error(f"Bundle fetch failed: {result.stderr}")
                return jsonify({'error': f'bundle fetch failed: {result.stderr}'}), 500

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

                if not pr_title:
                    pr_title = f"Changes from {branch}"

                gh_cmd = ['gh', 'pr', 'create', '--title', pr_title, '--body', pr_body or 'Automated PR from Claude', '--head', branch]

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
                    logger.warning(f"PR creation failed: {result.stderr}")
                    response['pr_created'] = False
                    response['pr_error'] = result.stderr

            logger.info(f"Push complete, temp repo cleaned up")
            return jsonify(response)

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while pushing bundle for {repo_url} {branch}")
        return jsonify({'error': 'operation timeout'}), 408

    except Exception as e:
        logger.error(f"Error pushing bundle: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        # Clean up temp bundle file
        if temp_bundle_path and os.path.exists(temp_bundle_path):
            os.unlink(temp_bundle_path)


if __name__ == '__main__':
    logger.info(f"Starting Git Bundle Proxy Server")
    logger.info(f"Mode: Temporary operations (no persistent storage)")
    logger.info(f"Secret key configured: {bool(os.environ.get('PROXY_SECRET_KEY'))}")

    # Run server
    app.run(
        host='127.0.0.1',
        port=int(os.environ.get('PORT', 8443)),
        debug=os.environ.get('DEBUG', 'False').lower() == 'true'
    )
