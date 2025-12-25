#!/usr/bin/env python3
"""
Git Bundle Client for Claude.ai Skills
Communicates with git bundle proxy server for temporary git operations
"""

import requests
import os
from typing import Optional

class GitProxyClient:
    """Client for communicating with git bundle proxy server"""

    def __init__(self, proxy_url: Optional[str] = None, auth_key: Optional[str] = None):
        """
        Initialize git proxy client

        Args:
            proxy_url: URL of proxy server (or set GIT_PROXY_URL env var)
            auth_key: Authentication key (or set GIT_PROXY_KEY env var)
        """
        self.proxy_url = proxy_url or os.environ.get('GIT_PROXY_URL')
        self.auth_key = auth_key or os.environ.get('GIT_PROXY_KEY')

        if not self.proxy_url or not self.auth_key:
            raise ValueError(
                "Missing proxy_url or auth_key. "
                "Set GIT_PROXY_URL and GIT_PROXY_KEY environment variables."
            )

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
            headers={'X-Auth-Key': self.auth_key},
            timeout=600  # Larger repos may take time
        )

        if response.status_code != 200:
            raise Exception(f"Fetch bundle failed: {response.status_code} - {response.text}")

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
                headers={'X-Auth-Key': self.auth_key},
                timeout=600
            )

        if response.status_code != 200:
            raise Exception(f"Push bundle failed: {response.status_code} - {response.text}")

        return response.json()


# Convenience singleton
_client = None

def get_client() -> GitProxyClient:
    """Get or create singleton client instance"""
    global _client
    if _client is None:
        _client = GitProxyClient()
    return _client
