"""
Unit tests for credential redaction.

Tests the CredentialRedactor class for use in HTTP responses and
client-facing messages. NOTE: The redactor should NOT be used for
local server logs, which should keep full details for debugging.

Verifies exact string matching, runtime credential tracking, and
no false positives.
"""

import pytest
from server.error_redaction import CredentialRedactor


def test_exact_credential_redaction():
    """Verify exact credential strings are redacted."""
    redactor = CredentialRedactor()

    # Manually add test credentials
    redactor.credentials_to_redact.add("ghp_test123secret")
    redactor.credentials_to_redact.add("abcd-efgh-ijkl-mnop")

    # Test exact match
    result = redactor.redact("Clone failed: ghp_test123secret")
    assert result == "Clone failed: [REDACTED]"
    assert "ghp_test123secret" not in result

    # Test credential embedded in URL
    result = redactor.redact("Error in https://user:ghp_test123secret@github.com")
    assert "ghp_test123secret" not in result
    assert "[REDACTED]" in result

    # Test ATProto password
    result = redactor.redact("Failed: abcd-efgh-ijkl-mnop authentication")
    assert result == "Failed: [REDACTED] authentication"


def test_runtime_credential_tracking():
    """Verify runtime credentials can be tracked and redacted."""
    redactor = CredentialRedactor()

    # Simulate ATProto JWT
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"

    # Track at runtime
    redactor.track_runtime_credential(jwt)

    # Verify it's tracked
    assert jwt in redactor.credentials_to_redact

    # Verify it's redacted
    result = redactor.redact(f"Bearer {jwt}")
    assert jwt not in result
    assert result == "Bearer [REDACTED]"


def test_multiple_credentials_in_same_string():
    """Verify multiple credentials in one string are all redacted."""
    redactor = CredentialRedactor()
    redactor.credentials_to_redact.add("secret1")
    redactor.credentials_to_redact.add("secret2")

    result = redactor.redact("Error: secret1 and secret2 failed")
    assert result == "Error: [REDACTED] and [REDACTED] failed"
    assert "secret1" not in result
    assert "secret2" not in result


def test_no_false_positives():
    """Verify non-credential strings are not redacted."""
    redactor = CredentialRedactor()
    redactor.credentials_to_redact.add("ghp_realtoken123")

    # Similar pattern but not actual credential
    result = redactor.redact("Testing ghp_different_string here")
    assert result == "Testing ghp_different_string here"  # Not redacted

    # Empty string
    result = redactor.redact("")
    assert result == ""

    # None handling
    result = redactor.redact(None)
    assert result is None


def test_empty_credential_ignored():
    """Verify empty credentials are not tracked."""
    redactor = CredentialRedactor()

    # Track empty credential
    redactor.track_runtime_credential("")
    redactor.track_runtime_credential(None)

    # Empty string should not be in the set
    assert "" not in redactor.credentials_to_redact
    assert None not in redactor.credentials_to_redact


def test_redaction_in_subprocess_stderr():
    """Verify credentials are redacted from git subprocess output."""
    redactor = CredentialRedactor()
    redactor.credentials_to_redact.add("ghp_mysecret123")

    # Simulate git clone error with embedded credential
    stderr = """fatal: could not read Username for 'https://github.com': terminal prompts disabled
remote: Invalid username or password.
fatal: Authentication failed for 'https://ghp_mysecret123@github.com/user/repo.git'"""

    result = redactor.redact(stderr)
    assert "ghp_mysecret123" not in result
    assert "[REDACTED]" in result
    assert "Authentication failed" in result  # Error message preserved


def test_redaction_performance():
    """Verify redaction performance is acceptable."""
    import time

    redactor = CredentialRedactor()
    # Add many credentials
    for i in range(100):
        redactor.credentials_to_redact.add(f"secret_{i}")

    text = "Error message with secret_50 in it"

    start = time.time()
    result = redactor.redact(text)
    elapsed = time.time() - start

    assert "secret_50" not in result
    assert elapsed < 0.001  # Should be < 1ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
