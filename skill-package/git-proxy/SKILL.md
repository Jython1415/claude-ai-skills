---
name: git-proxy
description: Clone GitHub repositories into Claude.ai Projects using git bundles via proxy server. Use when you need to work with git repositories from Claude.ai.
---

# Git Proxy Skill

Clone and push to GitHub repositories from Claude.ai Projects using git bundles and a proxy server.

## IMPORTANT: Available Methods

The `GitProxyClient` class has **only 3 methods**:
- ✅ `health_check()` - Test connection
- ✅ `fetch_bundle(repo_url, output_path, branch='main')` - Download repo as bundle
- ✅ `push_bundle(bundle_path, repo_url, branch, ...)` - Upload and push changes

**Methods that DO NOT exist:**
- ❌ NO `clone()` method - use `fetch_bundle()` then `git clone`
- ❌ NO `push()` method - use `push_bundle()` with a bundle file
- ❌ NO `pull()` method - use `fetch_bundle()` to get updates

## Prerequisites

**Environment file location in Claude.ai Projects:** `/mnt/project/_env`

The file should contain:
```
GIT_PROXY_URL=https://your-machine.your-tailnet.ts.net
GIT_PROXY_KEY=your-secret-authentication-key
```

**Load environment variables before using the client:**
```python
import os

# REQUIRED: Load environment variables from _env file
with open('/mnt/project/_env', 'r') as f:
    for line in f:
        if '=' in line:
            key, value = line.strip().split('=', 1)
            os.environ[key] = value
```

**PR Creation:**
- Automatic PR creation (`create_pr=True`) uses GitHub CLI (`gh`) on your proxy server
- Server auto-detects `gh` at startup (checks `/opt/homebrew/bin/gh` and `/usr/local/bin/gh`)
- If `gh` is available, PRs are created automatically
- If `gh` not found, server provides manual PR URL in response
- Check server logs on startup to verify `gh` was detected

## Quick Start (Easy Mode)

**Using convenience functions for simplest workflow:**

```python
import sys
sys.path.insert(0, '/mnt/project')
from git_client import load_env_from_file, clone_repo, GitProxyClient
import subprocess

# Load environment variables automatically
load_env_from_file()  # Loads from /mnt/project/_env

# Clone repo in one step
clone_repo('https://github.com/user/repo.git', '/tmp/repo')

# Make changes and commit
with open('/tmp/repo/README.md', 'a') as f:
    f.write('\nImprovement from Claude\n')

subprocess.run(['git', 'add', '.'], cwd='/tmp/repo', check=True)
subprocess.run(['git', 'commit', '-m', 'Improvements'], cwd='/tmp/repo', check=True)

# Create feature branch and bundle (use explicit branch name!)
subprocess.run(['git', 'checkout', '-b', 'feature/claude-improvements'], cwd='/tmp/repo', check=True)
subprocess.run([
    'git', 'bundle', 'create', '/tmp/changes.bundle',
    'origin/main..feature/claude-improvements'  # Not HEAD!
], cwd='/tmp/repo', check=True)

# Push and create PR
client = GitProxyClient()
result = client.push_bundle(
    '/tmp/changes.bundle',
    'https://github.com/user/repo.git',
    'feature/claude-improvements',
    create_pr=True,
    pr_title='Improvements from Claude'
)
print(f"✓ PR created: {result['pr_url']}")
```

## Complete Workflow Example (Manual Steps)

**Step-by-step workflow showing all operations explicitly:**

```python
import sys
import subprocess

# STEP 1: Add git_client to Python path
sys.path.insert(0, '/mnt/project')
from git_client import load_env_from_file, GitProxyClient

# STEP 2: Load environment variables (REQUIRED!)
load_env_from_file()  # Loads from /mnt/project/_env

# STEP 3: Initialize client (uses env vars)
client = GitProxyClient()

# STEP 4: Verify connection
health = client.health_check()
print(f"Proxy status: {health['status']}")

# STEP 5: Fetch repository as bundle
# NOTE: There is NO clone() method on GitProxyClient - use fetch_bundle() instead!
client.fetch_bundle(
    'https://github.com/user/repo.git',
    '/tmp/repo.bundle'
)

# STEP 6: Clone bundle to create working directory
subprocess.run(['git', 'clone', '/tmp/repo.bundle', '/tmp/repo'], check=True)

# STEP 7: Set remote URL (bundles don't have remotes)
subprocess.run([
    'git', 'remote', 'set-url', 'origin',
    'https://github.com/user/repo.git'
], cwd='/tmp/repo', check=True)

# STEP 8: Make changes and commit
with open('/tmp/repo/README.md', 'a') as f:
    f.write('\nImprovement from Claude\n')

subprocess.run(['git', 'add', '.'], cwd='/tmp/repo', check=True)
subprocess.run(['git', 'commit', '-m', 'Improvements'], cwd='/tmp/repo', check=True)

# STEP 9: Create feature branch
subprocess.run([
    'git', 'checkout', '-b', 'feature/claude-improvements'
], cwd='/tmp/repo', check=True)

# STEP 10: Create bundle of changes (use explicit branch name, not HEAD)
subprocess.run([
    'git', 'bundle', 'create', '/tmp/changes.bundle',
    'origin/main..feature/claude-improvements'  # Use branch name, not HEAD!
], cwd='/tmp/repo', check=True)

# STEP 11: Push bundle and create PR
result = client.push_bundle(
    '/tmp/changes.bundle',
    'https://github.com/user/repo.git',
    'feature/claude-improvements',
    create_pr=True,
    pr_title='Improvements from Claude',
    pr_body='Automated improvements from Claude.ai'
)

print(f"✓ PR created: {result['pr_url']}")
```

## API Reference

### Convenience Functions (Recommended)

- `load_env_from_file(env_file='/mnt/project/_env')` - Load environment variables from file
- `clone_repo(repo_url, target_dir, branch='main', setup_user=True)` - One-step clone: fetch bundle + git clone + set remote + configure git user
- `setup_git_user(repo_dir, email='claude@anthropic.com', name='Claude')` - Configure git user identity for commits

### GitProxyClient Methods

- `health_check()` - Verify proxy server is reachable
- `fetch_bundle(repo_url, output_path, branch='main')` - Fetch repository as bundle for local cloning
- `push_bundle(bundle_path, repo_url, branch, create_pr=False, pr_title='', pr_body='')` - Push bundled changes and optionally create PR

## Common Mistakes to Avoid

### ❌ Wrong: Trying to call clone() on GitProxyClient
```python
client = GitProxyClient()
client.clone('https://github.com/user/repo.git')  # ❌ NO clone() method on GitProxyClient!
```

### ✅ Correct Option 1: Use convenience function
```python
from git_client import load_env_from_file, clone_repo
load_env_from_file()
clone_repo('https://github.com/user/repo.git', '/tmp/repo')  # ✅ One-step clone
```

### ✅ Correct Option 2: Use fetch_bundle() then git clone
```python
client = GitProxyClient()
client.fetch_bundle('https://github.com/user/repo.git', '/tmp/repo.bundle')
subprocess.run(['git', 'clone', '/tmp/repo.bundle', '/tmp/repo'], check=True)
subprocess.run(['git', 'remote', 'set-url', 'origin', 'https://github.com/user/repo.git'], cwd='/tmp/repo', check=True)
```

### ❌ Wrong: Forgetting to load environment variables
```python
from git_client import GitProxyClient
client = GitProxyClient()  # ❌ Raises ValueError - env vars not loaded!
```

### ✅ Correct: Load env vars using helper function
```python
from git_client import load_env_from_file, GitProxyClient
load_env_from_file()  # ✅ Loads from /mnt/project/_env
client = GitProxyClient()  # ✅ Works - env vars loaded
```

## Troubleshooting

### Connection Errors
- Verify `/mnt/project/_env` file exists (use `ls /mnt/project/_env`)
- Check `GIT_PROXY_URL` and `GIT_PROXY_KEY` are set correctly in _env file
- Test with `client.health_check()` - should return `{"status": "healthy"}`
- Ensure proxy server is running on your local machine
- Confirm domain is in Claude.ai allowed domains list

### Authentication Failures (401 errors)
- Verify `GIT_PROXY_KEY` in `/mnt/project/_env` matches server's `PROXY_SECRET_KEY`
- Ensure you loaded env vars before creating client
- Check server logs for authentication attempts

### 404 Errors
- Only 3 endpoints exist: `/health`, `/git/fetch-bundle`, `/git/push-bundle`
- DO NOT try `/clone`, `/git-exec`, `/bundle` - these don't exist
- Use `fetch_bundle()` and `push_bundle()` methods, not custom API calls

### Bundle Failures
- **CRITICAL**: Always use explicit branch refs when creating bundles for push:
  - ❌ Wrong: `git bundle create bundle.file origin/main..HEAD`
  - ✅ Correct: `git bundle create bundle.file origin/main..feature-branch`
- If you get "Couldn't find remote ref" error, recreate bundle with explicit branch name
- Verify bundle with: `git bundle verify bundle.file`
- When creating bundles for local use only, `origin/main..HEAD` is fine

### Git Configuration
- Set git user identity before committing:
  ```bash
  git config user.email "claude@anthropic.com"
  git config user.name "Claude"
  ```
- Or use global config if available

### Import Errors
If `from git_client import ...` fails, ensure git_client.py is accessible:
```python
# Option 1: Copy to project directory
import subprocess
subprocess.run(['cp', '/mnt/skills/user/git-proxy/git_client.py', '/mnt/project/'])

# Option 2: Add to Python path
import sys
sys.path.insert(0, '/mnt/skills/user/git-proxy')
```

## Security Notes

- All operations require authentication via secret key
- Files are processed in temporary directories with automatic cleanup
- No persistent storage on proxy server (pure pass-through)
- Full audit trail maintained in server logs
- PR creation uses your local git credentials and gh CLI configuration
