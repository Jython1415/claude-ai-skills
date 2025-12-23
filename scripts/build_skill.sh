#!/bin/bash
set -e

# Build the skill ZIP file for distribution
# Usage: ./scripts/build_skill.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SKILL_DIR="$REPO_ROOT/skill-package/git-proxy"

cd "$REPO_ROOT/skill-package"

# Remove old ZIP if exists
rm -f git-proxy-skill.zip

# Create ZIP (exclude VERSION - it's workflow metadata, not part of the skill)
zip -r git-proxy-skill.zip git-proxy/ -x "git-proxy/VERSION"

echo "✓ Created git-proxy-skill.zip"
echo "ZIP contents:"
unzip -l git-proxy-skill.zip
