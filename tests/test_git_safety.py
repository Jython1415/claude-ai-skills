"""
Unit tests for git command safety validation.

Tests the validation functions in server/git_safety.py that protect against
destructive git operations and malicious inputs (shell injection, path
traversal, etc.).
"""

import pytest

from server.git_safety import (
    DANGEROUS_PUSH_FLAGS,
    is_protected_branch,
    validate_branch_name,
    validate_push_command_safety,
    validate_repo_url,
)

# =============================================================================
# validate_repo_url tests
# =============================================================================


class TestValidateRepoUrl:
    """Tests for repository URL validation."""

    # --- Valid URLs ---

    def test_valid_github_https_url(self):
        valid, error = validate_repo_url("https://github.com/user/repo")
        assert valid is True
        assert error == ""

    def test_valid_github_https_url_with_git_suffix(self):
        valid, error = validate_repo_url("https://github.com/user/repo.git")
        assert valid is True
        assert error == ""

    def test_valid_github_ssh_url(self):
        valid, error = validate_repo_url("git@github.com:user/repo.git")
        assert valid is True
        assert error == ""

    def test_valid_github_ssh_url_without_git_suffix(self):
        valid, error = validate_repo_url("git@github.com:user/repo")
        assert valid is True
        assert error == ""

    def test_valid_github_url_with_dots_in_name(self):
        valid, error = validate_repo_url("https://github.com/user/my.repo.name")
        assert valid is True
        assert error == ""

    def test_valid_github_url_with_hyphens(self):
        valid, error = validate_repo_url("https://github.com/my-org/my-repo")
        assert valid is True
        assert error == ""

    def test_valid_github_url_with_underscores(self):
        valid, error = validate_repo_url("https://github.com/my_org/my_repo")
        assert valid is True
        assert error == ""

    # --- Empty / missing ---

    def test_empty_url(self):
        valid, error = validate_repo_url("")
        assert valid is False
        assert "required" in error.lower()

    def test_none_url(self):
        valid, error = validate_repo_url(None)
        assert valid is False
        assert "required" in error.lower()

    def test_whitespace_only_url(self):
        valid, error = validate_repo_url("   ")
        assert valid is False
        assert "required" in error.lower()

    # --- Local path attacks ---

    def test_local_absolute_path(self):
        valid, error = validate_repo_url("/tmp/evil-repo")
        assert valid is False
        assert "local path" in error.lower()

    def test_local_relative_path(self):
        valid, error = validate_repo_url("./evil-repo")
        assert valid is False
        assert "local path" in error.lower()

    def test_file_protocol_url(self):
        valid, error = validate_repo_url("file:///tmp/evil-repo")
        assert valid is False
        assert "local path" in error.lower()

    # --- Non-GitHub URLs ---

    def test_gitlab_url(self):
        valid, error = validate_repo_url("https://gitlab.com/user/repo")
        assert valid is False
        assert "github" in error.lower()

    def test_bitbucket_url(self):
        valid, error = validate_repo_url("https://bitbucket.org/user/repo")
        assert valid is False
        assert "github" in error.lower()

    def test_arbitrary_url(self):
        valid, error = validate_repo_url("https://evil.com/malicious/repo")
        assert valid is False
        assert "github" in error.lower()

    # --- Shell injection attacks ---

    def test_shell_injection_semicolon(self):
        valid, error = validate_repo_url("https://github.com/user/repo; rm -rf /")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_pipe(self):
        valid, error = validate_repo_url("https://github.com/user/repo | cat /etc/passwd")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_backtick(self):
        valid, error = validate_repo_url("https://github.com/user/`whoami`")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_dollar(self):
        valid, error = validate_repo_url("https://github.com/user/$(whoami)")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_ampersand(self):
        valid, error = validate_repo_url("https://github.com/user/repo && echo pwned")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_newline(self):
        valid, error = validate_repo_url("https://github.com/user/repo\nrm -rf /")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_null_byte(self):
        valid, error = validate_repo_url("https://github.com/user/repo\x00")
        assert valid is False
        assert "invalid characters" in error.lower()

    # --- Embedded credentials ---

    def test_url_with_embedded_credentials(self):
        valid, error = validate_repo_url("https://user:password@github.com/user/repo")
        assert valid is False
        assert "embedded credentials" in error.lower()

    def test_url_with_token_in_url(self):
        valid, error = validate_repo_url("https://ghp_token123@github.com/user/repo")
        assert valid is False
        assert "embedded credentials" in error.lower()

    # --- Whitespace trimming ---

    def test_leading_trailing_whitespace_trimmed(self):
        valid, error = validate_repo_url("  https://github.com/user/repo  ")
        assert valid is True
        assert error == ""


# =============================================================================
# validate_branch_name tests
# =============================================================================


class TestValidateBranchName:
    """Tests for branch name validation."""

    # --- Valid branch names ---

    def test_simple_branch_name(self):
        valid, error = validate_branch_name("feature-branch")
        assert valid is True
        assert error == ""

    def test_branch_with_slash(self):
        valid, error = validate_branch_name("feature/my-change")
        assert valid is True
        assert error == ""

    def test_branch_with_underscore(self):
        valid, error = validate_branch_name("feature_my_change")
        assert valid is True
        assert error == ""

    def test_branch_with_dot(self):
        valid, error = validate_branch_name("release.1.0")
        assert valid is True
        assert error == ""

    def test_single_character_branch(self):
        valid, error = validate_branch_name("x")
        assert valid is True
        assert error == ""

    def test_claude_feature_branch(self):
        """The intended workflow uses claude/ prefix branches."""
        valid, error = validate_branch_name("claude/fix-login-bug")
        assert valid is True
        assert error == ""

    def test_numeric_branch(self):
        valid, error = validate_branch_name("123")
        assert valid is True
        assert error == ""

    # --- Empty / missing ---

    def test_empty_branch_name(self):
        valid, error = validate_branch_name("")
        assert valid is False
        assert "required" in error.lower()

    def test_none_branch_name(self):
        valid, error = validate_branch_name(None)
        assert valid is False
        assert "required" in error.lower()

    def test_whitespace_only_branch_name(self):
        valid, error = validate_branch_name("   ")
        assert valid is False
        assert "required" in error.lower()

    # --- Shell injection attacks ---

    def test_shell_injection_semicolon(self):
        valid, error = validate_branch_name("branch; rm -rf /")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_pipe(self):
        valid, error = validate_branch_name("branch | cat /etc/passwd")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_backtick(self):
        valid, error = validate_branch_name("`whoami`")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_dollar_subshell(self):
        valid, error = validate_branch_name("$(rm -rf /)")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_ampersand(self):
        valid, error = validate_branch_name("branch && echo pwned")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_newline(self):
        valid, error = validate_branch_name("branch\nrm -rf /")
        assert valid is False
        assert "invalid characters" in error.lower()

    def test_shell_injection_null_byte(self):
        valid, error = validate_branch_name("branch\x00")
        assert valid is False
        assert "invalid characters" in error.lower()

    # --- Git ref traversal ---

    def test_double_dots(self):
        valid, error = validate_branch_name("main..feature")
        assert valid is False
        assert ".." in error

    def test_lock_suffix(self):
        valid, error = validate_branch_name("branch.lock")
        assert valid is False
        assert ".lock" in error

    # --- Flag injection ---

    def test_branch_starting_with_hyphen(self):
        valid, error = validate_branch_name("--force")
        assert valid is False
        assert "hyphen" in error.lower()

    def test_branch_starting_with_single_hyphen(self):
        valid, error = validate_branch_name("-f")
        assert valid is False
        assert "hyphen" in error.lower()

    def test_branch_starting_with_delete_flag(self):
        valid, error = validate_branch_name("--delete")
        assert valid is False
        assert "hyphen" in error.lower()

    # --- Refs manipulation ---

    def test_refs_prefix(self):
        valid, error = validate_branch_name("refs/heads/main")
        assert valid is False
        assert "refs/" in error

    def test_refs_tags(self):
        valid, error = validate_branch_name("refs/tags/v1.0")
        assert valid is False
        assert "refs/" in error

    # --- Length limit ---

    def test_very_long_branch_name(self):
        valid, error = validate_branch_name("a" * 256)
        assert valid is False
        assert "too long" in error.lower()

    def test_max_length_branch_name(self):
        valid, error = validate_branch_name("a" * 255)
        assert valid is True
        assert error == ""

    # --- Whitespace trimming ---

    def test_leading_trailing_whitespace_trimmed(self):
        valid, error = validate_branch_name("  feature-branch  ")
        assert valid is True
        assert error == ""


# =============================================================================
# is_protected_branch tests
# =============================================================================


class TestIsProtectedBranch:
    """Tests for protected branch detection."""

    def test_main_is_protected(self):
        protected, error = is_protected_branch("main")
        assert protected is True
        assert "pull request" in error.lower()

    def test_master_is_protected(self):
        protected, error = is_protected_branch("master")
        assert protected is True
        assert "pull request" in error.lower()

    def test_production_is_protected(self):
        protected, error = is_protected_branch("production")
        assert protected is True

    def test_release_is_protected(self):
        protected, error = is_protected_branch("release")
        assert protected is True

    def test_develop_is_protected(self):
        protected, error = is_protected_branch("develop")
        assert protected is True

    def test_feature_branch_not_protected(self):
        protected, error = is_protected_branch("feature/my-change")
        assert protected is False
        assert error == ""

    def test_claude_branch_not_protected(self):
        protected, error = is_protected_branch("claude/fix-bug")
        assert protected is False
        assert error == ""

    def test_case_insensitive(self):
        """Protected branch check should be case-insensitive."""
        protected, _ = is_protected_branch("Main")
        assert protected is True

        protected, _ = is_protected_branch("MASTER")
        assert protected is True

    def test_empty_branch(self):
        protected, error = is_protected_branch("")
        assert protected is True
        assert "required" in error.lower()

    def test_none_branch(self):
        protected, error = is_protected_branch(None)
        assert protected is True
        assert "required" in error.lower()

    def test_main_with_prefix_not_protected(self):
        """feature/main should NOT be protected."""
        protected, error = is_protected_branch("feature/main")
        assert protected is False
        assert error == ""

    def test_main_with_suffix_not_protected(self):
        """main-feature should NOT be protected."""
        protected, error = is_protected_branch("main-feature")
        assert protected is False
        assert error == ""


# =============================================================================
# validate_push_command_safety tests
# =============================================================================


class TestValidatePushCommandSafety:
    """Tests for defense-in-depth push command validation."""

    def test_normal_push_is_safe(self):
        safe, error = validate_push_command_safety(["git", "push", "origin", "feature-branch"])
        assert safe is True
        assert error == ""

    def test_force_push_blocked(self):
        safe, error = validate_push_command_safety(["git", "push", "--force", "origin", "main"])
        assert safe is False
        assert "--force" in error

    def test_force_short_flag_blocked(self):
        safe, error = validate_push_command_safety(["git", "push", "-f", "origin", "main"])
        assert safe is False
        assert "-f" in error

    def test_force_with_lease_blocked(self):
        safe, error = validate_push_command_safety(["git", "push", "--force-with-lease", "origin", "main"])
        assert safe is False
        assert "--force-with-lease" in error

    def test_delete_flag_blocked(self):
        safe, error = validate_push_command_safety(["git", "push", "--delete", "origin", "feature"])
        assert safe is False
        assert "--delete" in error

    def test_mirror_flag_blocked(self):
        safe, error = validate_push_command_safety(["git", "push", "--mirror"])
        assert safe is False
        assert "--mirror" in error

    def test_force_if_includes_blocked(self):
        safe, error = validate_push_command_safety(["git", "push", "--force-if-includes", "origin", "main"])
        assert safe is False
        assert "--force-if-includes" in error

    def test_colon_deletion_syntax_blocked(self):
        """git push origin :branch-name deletes the remote branch."""
        safe, error = validate_push_command_safety(["git", "push", "origin", ":feature-branch"])
        assert safe is False
        assert "deletion" in error.lower()

    def test_empty_colon_not_blocked(self):
        """A lone colon should not trigger the deletion check."""
        safe, error = validate_push_command_safety(["git", "push", "origin", ":"])
        # ':' has length 1, so it's not caught by len(arg) > 1
        assert safe is True

    def test_all_dangerous_flags_covered(self):
        """Verify every flag in DANGEROUS_PUSH_FLAGS is actually blocked."""
        for flag in DANGEROUS_PUSH_FLAGS:
            safe, error = validate_push_command_safety(["git", "push", flag, "origin", "branch"])
            assert safe is False, f"Flag {flag} was not blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
