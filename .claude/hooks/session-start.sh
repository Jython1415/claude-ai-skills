#!/usr/bin/env bash
# SessionStart hook — runs at the beginning of every Claude Code session.
#
# Outputs the appropriate setup file (LOCAL-SETUP.md or REMOTE-SETUP.md)
# as context for Claude. The files live in the repo root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ───────────────────────────────────────────────────────────────
# Claude Code Web environment
# ───────────────────────────────────────────────────────────────
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then

    # Install gh CLI if not present (idempotent, fast from apt cache)
    if ! command -v gh &>/dev/null; then
        apt-get install -y gh &>/dev/null 2>&1
    fi

    cat "$REPO_ROOT/REMOTE-SETUP.md"

# ───────────────────────────────────────────────────────────────
# Local (CLI) environment
# ───────────────────────────────────────────────────────────────
else
    cat "$REPO_ROOT/LOCAL-SETUP.md"
fi
