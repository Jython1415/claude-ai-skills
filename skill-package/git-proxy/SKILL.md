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

## API Reference

### GitProxyClient Methods

- `health_check()` - Verify proxy server is reachable
- `fetch_bundle(repo_url, output_path, branch='main')` - Fetch repository as bundle for local cloning
- `push_bundle(bundle_path, repo_url, branch, create_pr=False, pr_title='', pr_body='')` - Push bundled changes and optionally create PR

## Troubleshooting

### Connection Errors
- Verify `.env` file exists in project
- Check `GIT_PROXY_URL` and `GIT_PROXY_KEY` are set correctly
- Ensure proxy server is running on your local machine
- Confirm domain is in Claude.ai allowed domains list

### Authentication Failures
- Verify `GIT_PROXY_KEY` matches the secret key on your proxy server
- Check server logs for authentication attempts

### Bundle Failures
- Ensure bundle files are valid git bundles
- Check bundle with: `git bundle verify bundle.file`
- Check server logs: `tail -f ~/Library/Logs/gitproxy.log`

## Security Notes

- All operations require authentication via secret key
- Files are processed in temporary directories with automatic cleanup
- No persistent storage on proxy server (pure pass-through)
- Full audit trail maintained in server logs
- PR creation uses your local git credentials and gh CLI configuration
