#!/usr/bin/env python3
"""
Git Client for Claude.ai Skills
Communicates with git proxy server to execute git operations
"""

import requests
import base64
import os
import json
from pathlib import Path
from typing import Optional, Tuple


class GitProxyClient:
    """Client for communicating with git proxy server"""

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

        # Default workspace path
        self.workspace = os.environ.get('GIT_WORKSPACE', '/tmp/git-workspace')

    def _execute(self, command: str, cwd: Optional[str] = None) -> Tuple[str, str, int]:
        """
        Execute git command via proxy

        Args:
            command: Git command to execute (e.g., "git status")
            cwd: Working directory (defaults to workspace)

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        if cwd is None:
            cwd = self.workspace

        # Encode command
        encoded_cmd = base64.b64encode(command.encode()).decode()

        # Send request
        response = requests.post(
            f'{self.proxy_url}/git-exec',
            json={'command': encoded_cmd, 'cwd': cwd},
            headers={'X-Auth-Key': self.auth_key},
            timeout=120
        )

        if response.status_code != 200:
            raise Exception(f"Proxy error: {response.status_code} - {response.text}")

        result = response.json()

        # Decode results
        stdout = base64.b64decode(result['stdout']).decode('utf-8', errors='replace')
        stderr = base64.b64decode(result['stderr']).decode('utf-8', errors='replace')

        return stdout, stderr, result['returncode']

    def health_check(self) -> dict:
        """Check proxy server health"""
        response = requests.get(
            f'{self.proxy_url}/health',
            timeout=5
        )
        return response.json()

    def clone(self, repo_url: str, local_path: Optional[str] = None) -> str:
        """
        Clone a repository

        Args:
            repo_url: URL of repository to clone
            local_path: Local path to clone to (defaults to workspace/repo_name)

        Returns:
            Path to cloned repository
        """
        if local_path is None:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            local_path = os.path.join(self.workspace, repo_name)

        cmd = f"git clone {repo_url} {local_path}"
        stdout, stderr, code = self._execute(cmd, cwd=self.workspace)

        if code != 0:
            raise Exception(f"Clone failed: {stderr}")

        return local_path

    def status(self, repo_path: str, short: bool = True) -> str:
        """Get git status"""
        flag = "--short" if short else ""
        stdout, stderr, code = self._execute(f"git status {flag}", cwd=repo_path)
        return stdout

    def add(self, repo_path: str, files: str = "-A") -> None:
        """Add files to staging area"""
        stdout, stderr, code = self._execute(f"git add {files}", cwd=repo_path)
        if code != 0:
            raise Exception(f"Add failed: {stderr}")

    def commit(self, repo_path: str, message: str, files: Optional[list] = None) -> bool:
        """
        Commit changes

        Args:
            repo_path: Path to repository
            message: Commit message
            files: Optional list of files to add (defaults to all)

        Returns:
            True if commit succeeded
        """
        if files:
            for file in files:
                self.add(repo_path, file)
        else:
            self.add(repo_path, "-A")

        # Escape quotes in message
        safe_message = message.replace('"', '\\"')
        stdout, stderr, code = self._execute(
            f'git commit -m "{safe_message}"',
            cwd=repo_path
        )

        return code == 0

    def push(self, repo_path: str, branch: str = 'main', remote: str = 'origin') -> bool:
        """Push changes to remote"""
        stdout, stderr, code = self._execute(
            f"git push {remote} {branch}",
            cwd=repo_path
        )
        return code == 0

    def pull(self, repo_path: str, branch: str = 'main', remote: str = 'origin') -> str:
        """Pull changes from remote"""
        stdout, stderr, code = self._execute(
            f"git pull {remote} {branch}",
            cwd=repo_path
        )
        if code != 0:
            raise Exception(f"Pull failed: {stderr}")
        return stdout

    def log(self, repo_path: str, n: int = 10, oneline: bool = True) -> str:
        """Get commit history"""
        flag = "--oneline" if oneline else ""
        stdout, stderr, code = self._execute(
            f"git log {flag} -n {n}",
            cwd=repo_path
        )
        return stdout

    def branch(self, repo_path: str, branch_name: Optional[str] = None,
               checkout: bool = False) -> str:
        """
        List or create branches

        Args:
            repo_path: Path to repository
            branch_name: Name of branch to create (None to list)
            checkout: If True, checkout new branch

        Returns:
            Command output
        """
        if branch_name is None:
            # List branches
            cmd = "git branch"
        elif checkout:
            # Create and checkout
            cmd = f"git checkout -b {branch_name}"
        else:
            # Create only
            cmd = f"git branch {branch_name}"

        stdout, stderr, code = self._execute(cmd, cwd=repo_path)
        return stdout

    def checkout(self, repo_path: str, branch: str) -> None:
        """Checkout a branch"""
        stdout, stderr, code = self._execute(
            f"git checkout {branch}",
            cwd=repo_path
        )
        if code != 0:
            raise Exception(f"Checkout failed: {stderr}")

    def list_workspace(self) -> list:
        """List repositories in workspace"""
        response = requests.get(
            f'{self.proxy_url}/workspace/list',
            headers={'X-Auth-Key': self.auth_key},
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"Failed to list workspace: {response.status_code}")

        return response.json()['repositories']

    def gh(self, command: str, repo_path: Optional[str] = None) -> Tuple[str, str, int]:
        """
        Execute GitHub CLI command

        Args:
            command: gh command (e.g., "gh pr create --title 'Fix bug'")
            repo_path: Working directory (defaults to workspace)

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        if repo_path is None:
            repo_path = self.workspace

        return self._execute(command, cwd=repo_path)

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


# Convenience functions for direct usage
_client = None

def get_client() -> GitProxyClient:
    """Get or create singleton client instance"""
    global _client
    if _client is None:
        _client = GitProxyClient()
    return _client


def clone(repo_url: str, local_path: Optional[str] = None) -> str:
    """Clone a repository"""
    return get_client().clone(repo_url, local_path)


def status(repo_path: str, short: bool = True) -> str:
    """Get git status"""
    return get_client().status(repo_path, short)


def commit(repo_path: str, message: str, files: Optional[list] = None) -> bool:
    """Commit changes"""
    return get_client().commit(repo_path, message, files)


def push(repo_path: str, branch: str = 'main') -> bool:
    """Push changes"""
    return get_client().push(repo_path, branch)


def pull(repo_path: str, branch: str = 'main') -> str:
    """Pull changes"""
    return get_client().pull(repo_path, branch)
