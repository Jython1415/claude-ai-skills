---
name: git-proxy
description: Execute git operations through a secure proxy server. Use when you need to clone, commit, push, pull, or manage git repositories from Claude.ai Projects.
---

# Git Proxy Skill

Execute git operations (clone, commit, push, pull, branch management) through a secure HTTPS proxy server.

## Prerequisites

This skill requires a `.env` file in your project with:

```
GIT_PROXY_URL=https://your-machine.your-tailnet.ts.net
GIT_PROXY_KEY=your-secret-authentication-key
```

## Quick Start

### Bundle Workflow (Recommended for Claude.ai)

Clone repos into Claude's environment using git bundles:

```python
from git_client import GitProxyClient
import subprocess

# Initialize client
client = GitProxyClient()

# 1. Fetch repository as bundle
client.fetch_bundle('https://github.com/user/repo.git', 'repo.bundle')

# 2. Clone bundle locally in Claude's environment
subprocess.run(['git', 'clone', 'repo.bundle', 'repo/'])
subprocess.run(['git', 'remote', 'set-url', 'origin', 'https://github.com/user/repo.git'], cwd='repo/')

# 3. Edit files using normal file operations
with open('repo/README.md', 'a') as f:
    f.write('\nImprovement from Claude\n')

# 4. Commit changes
subprocess.run(['git', 'add', '.'], cwd='repo/')
subprocess.run(['git', 'commit', '-m', 'Improvements from Claude'], cwd='repo/')

# 5. Create feature branch and bundle changes
subprocess.run(['git', 'checkout', '-b', 'feature/claude-improvements'], cwd='repo/')
subprocess.run(['git', 'bundle', 'create', 'changes.bundle', 'main..HEAD'], cwd='repo/')

# 6. Push bundle and create PR
result = client.push_bundle(
    'changes.bundle',
    'https://github.com/user/repo.git',
    'feature/claude-improvements',
    create_pr=True,
    pr_title='Improvements from Claude',
    pr_body='Automated improvements'
)
print(f"PR created: {result.get('pr_url')}")
```

### Direct Proxy Workflow (Legacy)

Execute git commands on proxy server (files stay on your Mac):

```python
from git_client import GitProxyClient

# Initialize client (reads from .env automatically)
client = GitProxyClient()

# Clone a repository (on proxy server)
repo_path = client.clone('https://github.com/username/repo.git')

# Check status
status = client.status(repo_path)
print(status)

# Make changes, then commit
client.commit(repo_path, "Your commit message here")

# Push to remote
client.push(repo_path, branch='main')
```

## Common Operations

### Clone Repository
```python
repo = client.clone('https://github.com/user/repo.git')
```

### Check Status
```python
status = client.status(repo)
```

### Create Branch
```python
client.branch(repo, 'feature-branch', checkout=True)
```

### Commit Changes
```python
client.commit(repo, "Describe your changes")
```

### Push to Remote
```python
client.push(repo, branch='main')
```

### Pull Latest
```python
client.pull(repo)
```

### View History
```python
log = client.log(repo, n=10)
```

## API Reference

### GitProxyClient Methods

#### Bundle Operations (Recommended)
- `fetch_bundle(repo_url, output_path, branch='main')` - Fetch repository as bundle for local cloning
- `push_bundle(bundle_path, repo_url, branch, create_pr=False, pr_title='', pr_body='')` - Push bundled changes and optionally create PR

#### Direct Proxy Operations (Legacy)
- `health_check()` - Verify proxy server is reachable
- `clone(repo_url, local_path=None)` - Clone a repository on proxy server
- `status(repo_path, short=True)` - Get repository status
- `add(repo_path, files="-A")` - Stage files
- `commit(repo_path, message, files=None)` - Commit changes
- `push(repo_path, branch='main', remote='origin')` - Push to remote
- `pull(repo_path, branch='main', remote='origin')` - Pull from remote
- `log(repo_path, n=10, oneline=True)` - View commit history
- `branch(repo_path, branch_name=None, checkout=False)` - Manage branches
- `checkout(repo_path, branch)` - Switch branches
- `list_workspace()` - List all repositories in workspace
- `gh(command, repo_path=None)` - Execute GitHub CLI commands

## Troubleshooting

### Connection Errors
- Verify `.env` file exists in project
- Check `GIT_PROXY_URL` and `GIT_PROXY_KEY` are set correctly
- Ensure proxy server is running on your local machine
- Confirm domain is in Claude.ai allowed domains list

### Authentication Failures
- Verify `GIT_PROXY_KEY` matches the secret key on your proxy server
- Check server logs for authentication attempts

### Command Failures
- All commands must start with `git ` (enforced by proxy for security)
- Ensure you're in a valid git repository path
- Check server logs: `tail -f ~/Library/Logs/gitproxy.log`

## Security Notes

- All git commands are executed through an authenticated proxy
- The proxy server validates all commands before execution
- Commands are restricted to workspace directory only
- Full audit trail maintained in server logs
