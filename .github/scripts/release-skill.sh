#!/bin/bash
set -e

# Release script for git-proxy skill
# Triggers on VERSION file changes or manual workflow dispatch

SKILL_NAME="git-proxy"
SKILL_DIR="skill-package/$SKILL_NAME"
VERSION_FILE="$SKILL_DIR/VERSION"
SKILL_MD="$SKILL_DIR/SKILL.md"

# Validate skill directory exists
if [ ! -d "$SKILL_DIR" ]; then
    echo "Error: Skill directory $SKILL_DIR not found"
    exit 1
fi

if [ ! -f "$SKILL_MD" ]; then
    echo "Error: SKILL.md not found in $SKILL_DIR"
    exit 1
fi

# Determine version
if [ -n "$VERSION_OVERRIDE" ]; then
    VERSION="$VERSION_OVERRIDE"
    echo "Using version from workflow input: $VERSION"
else
    if [ ! -f "$VERSION_FILE" ]; then
        echo "Error: VERSION file not found at $VERSION_FILE"
        exit 1
    fi
    VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')
    echo "Using version from VERSION file: $VERSION"
fi

# Validate semantic versioning format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in semantic versioning format (e.g., 1.0.0)"
    exit 1
fi

TAG="$SKILL_NAME-v$VERSION"
ZIP_NAME="$SKILL_NAME-skill.zip"

echo "Preparing release: $TAG"

# Check if release already exists
if gh release view "$TAG" >/dev/null 2>&1; then
    echo "Release $TAG already exists, skipping"
    exit 0
fi

# Create temporary directory for building
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy skill files (exclude VERSION metadata)
echo "Building skill package..."
cd "$SKILL_DIR"
zip -r "$BUILD_DIR/$ZIP_NAME" . -x "VERSION" "*.zip"
cd - > /dev/null

# Verify ZIP was created
if [ ! -f "$BUILD_DIR/$ZIP_NAME" ]; then
    echo "Error: Failed to create ZIP file"
    exit 1
fi

echo "ZIP contents:"
unzip -l "$BUILD_DIR/$ZIP_NAME"

# Generate release notes
SKILL_README_CONTENT=$(cat "$SKILL_MD" | tail -n +5)  # Skip frontmatter
REPO_URL="https://github.com/$REPOSITORY"
SKILL_URL="$REPO_URL/tree/main/$SKILL_DIR"
DOWNLOAD_URL="$REPO_URL/releases/download/$TAG/$ZIP_NAME"

RELEASE_NOTES=$(cat <<EOF
# Git Proxy Skill v$VERSION

$SKILL_README_CONTENT

---

## Installation

1. Download [\`$ZIP_NAME\`]($DOWNLOAD_URL)
2. Go to [claude.ai](https://claude.ai) → Settings → Skills
3. Click "Upload Skill" and select the downloaded ZIP file

## Links

- [Skill Source Code]($SKILL_URL)
- [Repository]($REPO_URL)

## Changelog

$(git log --pretty=format:"- %s" $(git describe --tags --abbrev=0 2>/dev/null || echo "")..HEAD 2>/dev/null || echo "Initial release")
EOF
)

# Create GitHub release
echo "Creating GitHub release..."
gh release create "$TAG" \
    "$BUILD_DIR/$ZIP_NAME" \
    --title "Git Proxy Skill v$VERSION" \
    --notes "$RELEASE_NOTES" \
    --repo "$REPOSITORY"

echo "✓ Release $TAG created successfully"
echo "Download URL: $DOWNLOAD_URL"
