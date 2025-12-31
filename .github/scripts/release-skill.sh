#!/bin/bash
set -e

# Release script for skills - auto-detects which skill's VERSION changed
# Triggers on VERSION file changes or manual workflow dispatch

# Detect which skill's VERSION changed (only for push events)
if [ "$EVENT_NAME" = "push" ]; then
    CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD)
    VERSION_FILE=$(echo "$CHANGED_FILES" | grep 'skills/.*/VERSION' | head -n 1)

    if [ -z "$VERSION_FILE" ]; then
        echo "No VERSION file changed in skills/, skipping release"
        exit 0
    fi

    # Extract skill name from path: skills/git-proxy/VERSION → git-proxy
    SKILL_NAME=$(echo "$VERSION_FILE" | sed 's|skills/\([^/]*\)/VERSION|\1|')
    echo "Detected skill from VERSION change: $SKILL_NAME"
elif [ "$EVENT_NAME" = "workflow_dispatch" ]; then
    # For manual triggers, require skill name as input
    # TODO: Add skill_name input to workflow
    echo "Error: Manual workflow dispatch not yet supported for multi-skill"
    echo "Please specify which skill to release"
    exit 1
else
    echo "Error: Unsupported event type: $EVENT_NAME"
    exit 1
fi

SKILL_DIR="skills/$SKILL_NAME"
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

# Copy skill files
echo "Building skill package..."
cd "$SKILL_DIR"
zip -r "$BUILD_DIR/$ZIP_NAME" . -x "*.zip"
cd - > /dev/null

# Verify ZIP was created
if [ ! -f "$BUILD_DIR/$ZIP_NAME" ]; then
    echo "Error: Failed to create ZIP file"
    exit 1
fi

echo "ZIP contents:"
unzip -l "$BUILD_DIR/$ZIP_NAME"

# Extract skill display name and description from SKILL.md frontmatter
SKILL_DISPLAY_NAME=$(grep "^name:" "$SKILL_MD" | sed 's/name: *//' | tr -d '\r')
SKILL_DESCRIPTION=$(grep "^description:" "$SKILL_MD" | sed 's/description: *//' | tr -d '\r')

if [ -z "$SKILL_DISPLAY_NAME" ]; then
    SKILL_DISPLAY_NAME="$SKILL_NAME"
fi

# Generate release notes
REPO_URL="https://github.com/$REPOSITORY"
SKILL_URL="$REPO_URL/tree/main/$SKILL_DIR"
DOWNLOAD_URL="$REPO_URL/releases/download/$TAG/$ZIP_NAME"
CHANGELOG_FILE="$SKILL_DIR/CHANGELOG.md"

# Extract version-specific changelog
if [ -f "$CHANGELOG_FILE" ]; then
    # Extract the section for this version from CHANGELOG.md
    # Find lines between ## [$VERSION] and the next ## [version] or end of file
    CHANGELOG_CONTENT=$(awk "/## \[$VERSION\]/{flag=1; next} /## \[/{flag=0} flag" "$CHANGELOG_FILE")
    if [ -z "$CHANGELOG_CONTENT" ]; then
        CHANGELOG_CONTENT="See full documentation in SKILL.md"
    fi
else
    CHANGELOG_CONTENT="No changelog available - see full documentation in SKILL.md"
fi

RELEASE_NOTES=$(cat <<EOF
# $SKILL_DISPLAY_NAME v$VERSION

$SKILL_DESCRIPTION

## What's Changed

$CHANGELOG_CONTENT

## Installation

1. Download [\`$ZIP_NAME\`]($DOWNLOAD_URL)
2. Go to [claude.ai](https://claude.ai) → Settings → Skills
3. Click "Upload Skill" and select the downloaded ZIP file

## Links

- [Full Documentation (SKILL.md)]($SKILL_URL/SKILL.md)
- [Skill Source Code]($SKILL_URL)
- [Repository]($REPO_URL)
EOF
)

# Create GitHub release
echo "Creating GitHub release..."
gh release create "$TAG" \
    "$BUILD_DIR/$ZIP_NAME" \
    --title "$SKILL_DISPLAY_NAME v$VERSION" \
    --notes "$RELEASE_NOTES" \
    --repo "$REPOSITORY"

echo "✓ Release $TAG created successfully"
echo "Download URL: $DOWNLOAD_URL"
