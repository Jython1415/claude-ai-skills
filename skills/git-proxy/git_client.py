#!/usr/bin/env python3
"""
Git Bundle Client for Claude.ai Skills
Communicates with git bundle proxy server for temporary git operations
"""

import requests
import os
import subprocess
from typing import Optional

class GitProxyClient:
    """Client for communicating with git bundle proxy server"""

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        auth_key: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize git proxy client

        Authentication priority:
        1. session_id (if provided or SESSION_ID env var) - new session-based auth
        2. auth_key (if provided or GIT_PROXY_KEY env var) - legacy key-based auth

        Args:
            proxy_url: URL of proxy server (or set GIT_PROXY_URL/PROXY_URL env var)
            auth_key: Authentication key (or set GIT_PROXY_KEY env var)
            session_id: Session ID for session-based auth (or set SESSION_ID env var)
        """
        self.proxy_url = (
            proxy_url or
            os.environ.get('GIT_PROXY_URL') or
            os.environ.get('PROXY_URL')
        )
        self.session_id = session_id or os.environ.get('SESSION_ID')
        self.auth_key = auth_key or os.environ.get('GIT_PROXY_KEY')

        if not self.proxy_url:
            raise ValueError(
                "Missing proxy_url. "
                "Set GIT_PROXY_URL or PROXY_URL environment variable."
            )

        if not self.session_id and not self.auth_key:
            raise ValueError(
                "Missing authentication. "
                "Set SESSION_ID (for session auth) or GIT_PROXY_KEY (for key auth)."
            )

    def _auth_headers(self) -> dict:
        """Get authentication headers based on available credentials"""
        if self.session_id:
            return {'X-Session-Id': self.session_id}
        return {'X-Auth-Key': self.auth_key}

    def health_check(self) -> dict:
        """Check proxy server health"""
        response = requests.get(
            f'{self.proxy_url}/health',
            timeout=5
        )
        return response.json()

    def fetch_bundle(self, repo_url: str, output_path: str, branch: str = 'main') -> None:
        """
        Fetch repository as git bundle (for cloning in Claude's environment)

        Args:
            repo_url: URL of repository to fetch
            output_path: Local path to save bundle file
            branch: Branch to fetch (default: main)

        Example:
            client.fetch_bundle('https://github.com/user/repo.git', 'repo.bundle')
            # Then: git clone repo.bundle repo/
        """
        response = requests.post(
            f'{self.proxy_url}/git/fetch-bundle',
            json={'repo_url': repo_url, 'branch': branch},
            headers=self._auth_headers(),
            timeout=600  # Larger repos may take time
        )

        if response.status_code != 200:
            # Don't include response.text (may contain credentials)
            raise Exception(f"Fetch bundle failed: HTTP {response.status_code}")

        # Save bundle file
        with open(output_path, 'wb') as f:
            f.write(response.content)

    def push_bundle(self, bundle_path: str, repo_url: str, branch: str,
                   create_pr: bool = False, pr_title: str = '', pr_body: str = '') -> dict:
        """
        Push bundled changes to GitHub

        Args:
            bundle_path: Path to bundle file
            repo_url: URL of repository
            branch: Branch name to push
            create_pr: Whether to create a pull request
            pr_title: PR title (if create_pr=True)
            pr_body: PR description (if create_pr=True)

        Returns:
            Response dict with status, branch, and optionally pr_url

        Example:
            # After making changes and creating bundle:
            # git bundle create changes.bundle origin/main..HEAD
            result = client.push_bundle(
                'changes.bundle',
                'https://github.com/user/repo.git',
                'feature/improvements',
                create_pr=True,
                pr_title='Improvements from Claude'
            )
            print(result['pr_url'])
        """
        with open(bundle_path, 'rb') as f:
            files = {'bundle': f}
            data = {
                'repo_url': repo_url,
                'branch': branch,
                'create_pr': 'true' if create_pr else 'false',
                'pr_title': pr_title,
                'pr_body': pr_body
            }

            response = requests.post(
                f'{self.proxy_url}/git/push-bundle',
                files=files,
                data=data,
                headers=self._auth_headers(),
                timeout=600
            )

        if response.status_code != 200:
            # Don't include response.text (may contain credentials)
            raise Exception(f"Push bundle failed: HTTP {response.status_code}")

        return response.json()


# Convenience singleton
_client = None

def get_client() -> GitProxyClient:
    """Get or create singleton client instance"""
    global _client
    if _client is None:
        _client = GitProxyClient()
    return _client


def load_env_from_file(env_file: str = '/mnt/project/_env') -> None:
    """
    Load environment variables from file

    Args:
        env_file: Path to environment file (default: /mnt/project/_env for Claude.ai Projects)

    Example:
        load_env_from_file()  # Load from default location
        client = GitProxyClient()  # Now has access to GIT_PROXY_URL and GIT_PROXY_KEY
    """
    if not os.path.exists(env_file):
        raise FileNotFoundError(f"Environment file not found: {env_file}")

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value


def setup_git_user(repo_dir: str, email: str = 'claude@anthropic.com', name: str = 'Claude') -> None:
    """
    Configure git user identity for commits

    Args:
        repo_dir: Repository directory
        email: Git user email (default: claude@anthropic.com)
        name: Git user name (default: Claude)

    Example:
        clone_repo('https://github.com/user/repo.git', '/tmp/repo')
        setup_git_user('/tmp/repo')  # Configure git identity
    """
    subprocess.run(
        ['git', 'config', 'user.email', email],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'config', 'user.name', name],
        cwd=repo_dir,
        check=True,
        capture_output=True
    )


def clone_repo(repo_url: str, target_dir: str, branch: str = 'main',
               setup_user: bool = True) -> str:
    """
    One-step clone: fetch bundle and clone into directory

    This is a convenience wrapper that combines fetch_bundle + git clone.
    Requires environment variables to be loaded first (use load_env_from_file()).

    Args:
        repo_url: GitHub repository URL
        target_dir: Directory to clone into (will be created)
        branch: Branch to clone (default: main)
        setup_user: Automatically configure git user (default: True)

    Returns:
        Path to cloned repository

    Example:
        load_env_from_file()
        clone_repo('https://github.com/user/repo.git', '/tmp/myrepo')
        # Repository is now cloned at /tmp/myrepo with git user configured
    """
    client = GitProxyClient()

    # Create bundle file
    bundle_path = f"{target_dir}.bundle"

    # Fetch bundle
    client.fetch_bundle(repo_url, bundle_path, branch)

    # Clone from bundle
    result = subprocess.run(
        ['git', 'clone', bundle_path, target_dir],
        capture_output=True,
        text=True,
        check=True
    )

    # Set remote URL
    subprocess.run(
        ['git', 'remote', 'set-url', 'origin', repo_url],
        cwd=target_dir,
        capture_output=True,
        text=True,
        check=True
    )

    # Setup git user if requested
    if setup_user:
        setup_git_user(target_dir)

    # Clean up bundle file
    os.unlink(bundle_path)

    return target_dir
