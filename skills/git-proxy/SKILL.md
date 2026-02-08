---
name: git-proxy
description: Clone and push to GitHub repositories from Claude.ai using git bundles via credential proxy. Use when you need to work with git repositories from Claude.ai.
---

# Git Proxy Skill

Clone and push to GitHub repositories from Claude.ai using git bundles and the credential proxy server.

## Architecture

```
Claude.ai script
    |
    +-- MCP create_session(["git"]) -> session_id + proxy_url
    |
    +-- HTTPS requests to proxy_url (Cloudflare Tunnel)
            +-- POST /git/fetch-bundle  -> download repo as bundle
            +-- POST /git/push-bundle   -> upload bundle and push to GitHub
```

## Setup

### 1. Create a Session (MCP Tool)

Before using git operations, create a session via the MCP custom connector:

```
Use create_session with services: ["git"]
```

This returns:
- `session_id` -- use in `X-Session-Id` header for all requests
- `proxy_url` -- public HTTPS URL for the proxy (e.g., `https://proxy.joshuashew.com`)

### 2. Set Environment Variables

Scripts expect these environment variables (provided by MCP session):

| Variable | Description |
|----------|-------------|
| `SESSION_ID` | Session ID from create_session |
| `PROXY_URL` | Proxy URL from create_session (public Cloudflare Tunnel URL) |

## Usage

### Clone a Repository

```python
import os
import requests
import subprocess

SESSION_ID = os.environ["SESSION_ID"]
PROXY_URL = os.environ["PROXY_URL"]

# Fetch bundle from proxy
response = requests.post(
    f"{PROXY_URL}/git/fetch-bundle",
    json={"repo_url": "https://github.com/user/repo.git", "branch": "main"},
    headers={"X-Session-Id": SESSION_ID}
)

# Save and clone from bundle
with open("/tmp/repo.bundle", "wb") as f:
    f.write(response.content)

subprocess.run(["git", "clone", "/tmp/repo.bundle", "/tmp/repo"], check=True)
subprocess.run(["git", "remote", "set-url", "origin",
                "https://github.com/user/repo.git"], cwd="/tmp/repo", check=True)
```

### Push Changes

```python
import os
import requests
import subprocess

SESSION_ID = os.environ["SESSION_ID"]
PROXY_URL = os.environ["PROXY_URL"]

# Create bundle with changes (use explicit branch name, NOT HEAD)
subprocess.run([
    "git", "bundle", "create", "/tmp/changes.bundle",
    "origin/main..feature/my-branch"
], cwd="/tmp/repo", check=True)

# Push bundle via proxy
with open("/tmp/changes.bundle", "rb") as f:
    response = requests.post(
        f"{PROXY_URL}/git/push-bundle",
        files={"bundle": f},
        data={
            "repo_url": "https://github.com/user/repo.git",
            "branch": "feature/my-branch",
            "create_pr": "true",
            "pr_title": "My changes",
            "pr_body": "Description of changes"
        },
        headers={"X-Session-Id": SESSION_ID}
    )

result = response.json()
print(f"PR: {result.get("pr_url", result.get("manual_pr_url"))}")
```

### Using git_client.py (Convenience Library)

The `git_client.py` library provides helper functions:

```python
from git_client import GitProxyClient, clone_repo

# Session-based auth (recommended)
client = GitProxyClient(
    proxy_url=os.environ["PROXY_URL"],
    session_id=os.environ["SESSION_ID"]
)

# Or legacy key-based auth (still supported)
client = GitProxyClient(
    proxy_url=os.environ["PROXY_URL"],
    auth_key=os.environ["GIT_PROXY_KEY"]
)

# Clone (one-step: fetch bundle + clone + configure git user)
clone_repo("https://github.com/user/repo.git", "/tmp/repo")

# Push bundle
result = client.push_bundle(
    "/tmp/changes.bundle",
    "https://github.com/user/repo.git",
    "feature/my-branch",
    create_pr=True,
    pr_title="My changes"
)
```

## API Reference

### POST /git/fetch-bundle

Clone a repository and return it as a git bundle.

**Request:**
```json
{"repo_url": "https://github.com/user/repo.git", "branch": "main"}
```

**Response:** Binary git bundle file

**Auth:** `X-Session-Id` header (recommended) or `X-Auth-Key` header (legacy)

### POST /git/push-bundle

Apply a git bundle and push to GitHub. Optionally create a PR.

**Request:** `multipart/form-data` with:
- `bundle` -- git bundle file
- `repo_url` -- target repository URL
- `branch` -- branch name to push
- `create_pr` -- `"true"` or `"false"` (optional)
- `pr_title` -- PR title (optional)
- `pr_body` -- PR description (optional)

**Response:**
```json
{
  "status": "success",
  "branch": "feature/my-branch",
  "pr_created": true,
  "pr_url": "https://github.com/user/repo/pull/1"
}
```

**Auth:** `X-Session-Id` header (recommended) or `X-Auth-Key` header (legacy)

## Critical: Bundle Creation

**ALWAYS use explicit branch refs when creating bundles for push:**

- WRONG: `git bundle create file.bundle origin/main..HEAD`
- CORRECT: `git bundle create file.bundle origin/main..feature/branch-name`

Using `HEAD` causes "Couldn't find remote ref" errors on the server side.

## Common Issues

| Problem | Solution |
|---------|----------|
| 401 Unauthorized | Verify session is active (not expired). Create a new session. |
| Timeout on large repos | Increase timeout. Default clone timeout is 300s. |
| Bundle push "remote ref" error | Use explicit branch name, not HEAD, in bundle create |
| PR not created | Server needs `gh` CLI installed and authenticated |

## Security

- All operations require session-based auth (or legacy key auth)
- Git credentials (SSH keys) stay on the proxy server
- Files are processed in temporary directories with automatic cleanup
- No persistent storage on proxy server
- Sessions expire automatically (default 30 minutes)
