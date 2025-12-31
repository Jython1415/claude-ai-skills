#!/bin/bash
set -e

# Build the skill ZIP file for distribution
# Usage: ./scripts/build_skill.sh <skill-name>

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -z "$1" ]; then
    echo "Usage: $0 <skill-name>"
    echo ""
    echo "Available skills:"
    ls -1 "$REPO_ROOT/skills"
    exit 1
fi

SKILL_NAME="$1"
SKILL_DIR="$REPO_ROOT/skills/$SKILL_NAME"

if [ ! -d "$SKILL_DIR" ]; then
    echo "Error: Skill directory not found: $SKILL_DIR"
    echo ""
    echo "Available skills:"
    ls -1 "$REPO_ROOT/skills"
    exit 1
fi

cd "$REPO_ROOT/skills"

# Remove old ZIP if exists
rm -f "$SKILL_NAME-skill.zip"

# Create ZIP (include VERSION so users know which version they have)
zip -r "$SKILL_NAME-skill.zip" "$SKILL_NAME" -x "$SKILL_NAME/*.zip"

echo "✓ Created $SKILL_NAME-skill.zip"
echo "ZIP contents:"
unzip -l "$SKILL_NAME-skill.zip"
