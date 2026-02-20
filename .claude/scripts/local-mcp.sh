#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

export PATH="${HOME}/.local/bin:${HOME}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

exec "${HOME}/.local/bin/uv" run --directory "${PROJECT_DIR}" python "${PROJECT_DIR}/mcp/local_server.py"
