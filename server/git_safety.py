"""
Git command safety validation for the credential proxy.

Validates client-provided inputs (repo_url, branch name) before any git
operations are executed. The server constructs all git commands internally,
so this module focuses on INPUT validation rather than command parsing.

All validation functions return (is_valid: bool, error_message: str) tuples.
When is_valid is True, error_message is an empty string.
"""

import re
from typing import Tuple


# Protected branches that should not receive direct pushes (must go through PRs)
PROTECTED_BRANCHES = frozenset({
    'main',
    'master',
    'production',
    'release',
    'develop',
})

# Git push flags that must never appear in push commands (defense-in-depth)
DANGEROUS_PUSH_FLAGS = frozenset({
    '--force',
    '-f',
    '--force-with-lease',
    '--delete',
    '--mirror',
    '--force-if-includes',
})

# Valid GitHub URL patterns
# Supports: https://github.com/owner/repo, https://github.com/owner/repo.git
_GITHUB_HTTPS_PATTERN = re.compile(
    r'^https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(\.git)?$'
)
# Supports: git@github.com:owner/repo.git
_GITHUB_SSH_PATTERN = re.compile(
    r'^git@github\.com:[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(\.git)?$'
)

# Valid git branch name pattern
# Based on git-check-ref-format rules:
# - No double dots (..)
# - No ASCII control characters or space, tilde, caret, colon
# - Cannot begin or end with a dot, or end with .lock
# - No backslash, question mark, asterisk, open bracket
# - Cannot be a single @
# We use a strict allowlist approach: alphanumeric, hyphens, underscores,
# forward slashes, and dots (with additional constraints).
_BRANCH_NAME_PATTERN = re.compile(
    r'^[A-Za-z0-9][A-Za-z0-9._/-]*[A-Za-z0-9]$|^[A-Za-z0-9]$'
)

# Characters that could enable shell injection
_SHELL_METACHARACTERS = re.compile(r'[;&|`$(){}!\'"\\<>\n\r\x00]')


def validate_repo_url(url: str) -> Tuple[bool, str]:
    """
    Validate that a repository URL is a legitimate GitHub URL.

    Rejects:
    - Local file paths (e.g., /tmp/evil-repo, file:///...)
    - Non-GitHub URLs
    - URLs with shell metacharacters
    - URLs with embedded credentials (user:pass@)
    - Empty or whitespace-only values

    Args:
        url: The repository URL to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is empty when valid.
    """
    if not url or not url.strip():
        return False, "Repository URL is required"

    url = url.strip()

    # Block shell metacharacters (before URL parsing)
    if _SHELL_METACHARACTERS.search(url):
        return False, "Repository URL contains invalid characters"

    # Block embedded credentials in URL
    if '@' in url and not url.startswith('git@'):
        return False, "Repository URL must not contain embedded credentials"

    # Block local paths and file:// URLs
    if url.startswith('/') or url.startswith('file://') or url.startswith('.'):
        return False, "Only remote GitHub repository URLs are allowed (not local paths)"

    # Must match GitHub HTTPS or SSH patterns
    if _GITHUB_HTTPS_PATTERN.match(url):
        return True, ""

    if _GITHUB_SSH_PATTERN.match(url):
        return True, ""

    return False, (
        "Repository URL must be a GitHub URL "
        "(https://github.com/owner/repo or git@github.com:owner/repo.git)"
    )


def validate_branch_name(branch: str) -> Tuple[bool, str]:
    """
    Validate that a branch name is safe and well-formed.

    Rejects:
    - Empty or whitespace-only names
    - Names with shell metacharacters (;, |, &, `, $, etc.)
    - Names with double dots (..) which git also rejects
    - Names ending in .lock
    - Names starting with a hyphen (could be interpreted as flags)
    - Names containing only whitespace or control characters

    Args:
        branch: The branch name to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is empty when valid.
    """
    if not branch or not branch.strip():
        return False, "Branch name is required"

    branch = branch.strip()

    # Block shell metacharacters
    if _SHELL_METACHARACTERS.search(branch):
        return False, "Branch name contains invalid characters"

    # Block names starting with hyphen (could be interpreted as flags)
    if branch.startswith('-'):
        return False, "Branch name must not start with a hyphen"

    # Block double dots (git ref traversal)
    if '..' in branch:
        return False, "Branch name must not contain '..'"

    # Block .lock suffix (git internal)
    if branch.endswith('.lock'):
        return False, "Branch name must not end with '.lock'"

    # Block refs/ prefix (raw ref manipulation)
    if branch.startswith('refs/'):
        return False, "Branch name must not start with 'refs/'"

    # Must match the allowed pattern (alphanumeric, hyphens, underscores,
    # forward slashes, dots)
    if not _BRANCH_NAME_PATTERN.match(branch):
        return False, (
            "Branch name must contain only letters, numbers, hyphens, "
            "underscores, forward slashes, and dots"
        )

    # Reasonable length limit
    if len(branch) > 255:
        return False, "Branch name is too long (max 255 characters)"

    return True, ""


def is_protected_branch(branch: str) -> Tuple[bool, str]:
    """
    Check if a branch is protected and should not receive direct pushes.

    Protected branches (main, master, production, release, develop) should
    only be updated through pull requests, not direct pushes.

    Args:
        branch: The branch name to check

    Returns:
        Tuple of (is_protected, error_message). error_message is empty when
        the branch is NOT protected (i.e., it's safe to push to).
    """
    if not branch:
        return True, "Branch name is required"

    branch_normalized = branch.strip().lower()

    if branch_normalized in PROTECTED_BRANCHES:
        return True, (
            f"Direct push to '{branch}' is blocked. "
            f"Protected branches ({', '.join(sorted(PROTECTED_BRANCHES))}) "
            f"must be updated through pull requests."
        )

    return False, ""


def validate_push_command_safety(command_args: list) -> Tuple[bool, str]:
    """
    Defense-in-depth check that a constructed git push command does not
    contain dangerous flags.

    This is an INTERNAL safety check on server-constructed commands,
    not client input validation. It guards against programming errors
    that might introduce force-push or deletion flags.

    Args:
        command_args: List of command arguments (e.g., ['git', 'push', 'origin', 'branch'])

    Returns:
        Tuple of (is_safe, error_message). error_message is empty when safe.
    """
    for arg in command_args:
        if arg in DANGEROUS_PUSH_FLAGS:
            return False, f"Dangerous git push flag detected: {arg}"

    # Check for colon-prefix deletion syntax (e.g., :branch-name)
    for arg in command_args:
        if arg.startswith(':') and len(arg) > 1:
            return False, f"Remote branch deletion syntax detected: {arg}"

    return True, ""
