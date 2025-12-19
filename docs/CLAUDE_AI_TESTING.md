# Testing Git Proxy from Claude.ai

Proof of concept tests to verify the git proxy works from Claude.ai Projects.

## Prerequisites

1. `.env` file added to Claude.ai Project with:
   ```
   GIT_PROXY_URL=https://your-machine.tail-abc123.ts.net
   GIT_PROXY_KEY=<your-secret-key>
   ```

2. `client/git_client.py` uploaded to Project files

3. Flask server running locally (`./scripts/start_server.sh`)

4. Tailscale Funnel active (`tailscale funnel --bg 8443`)

## Test 1: Environment Variables

**Prompt for Claude.ai:**
```
Can you find and read the .env file in this project?
Show me what environment variables are available (without revealing the full secret key value).
```

**Expected result:**
- Claude should locate the .env file
- Should show `GIT_PROXY_URL` and `GIT_PROXY_KEY` are present
- Should NOT display the actual secret key value

## Test 2: Health Check

**Prompt for Claude.ai:**
```
I've uploaded git_client.py to this project. Can you:
1. Import it
2. Create a GitProxyClient instance (it should read from the .env file)
3. Call the health_check() method to verify the proxy is reachable

Show me the response.
```

**Expected result:**
```python
{
    'status': 'healthy',
    'workspace': '~/git-proxy-workspace',
    'timestamp': '...'
}
```

## Test 3: List Workspace

**Prompt for Claude.ai:**
```
Using the git_client, can you call list_workspace() to see what repositories
are currently in the proxy workspace?
```

**Expected result:**
- Should return empty list (or any repos in your workspace)
- No authentication errors

## Test 4: Clone a Repository

**Prompt for Claude.ai:**
```
Can you clone a test repository using the git proxy?

Try cloning this public repo:
https://github.com/octocat/Hello-World.git

Use the git_client.clone() method.
```

**Expected result:**
- Repository clones successfully
- Returns the local path
- No errors

## Test 5: Check Status

**Prompt for Claude.ai:**
```
Can you check the git status of the repository you just cloned?
Use git_client.status(repo_path) where repo_path is the path from the clone.
```

**Expected result:**
- Shows clean working directory
- No errors

## Troubleshooting

### "Can't find .env file"
- Verify the file is uploaded in Project Files
- Try asking Claude to list all files: `os.listdir('.')`

### "Connection refused" or timeout
- Check Flask server is running: `curl http://127.0.0.1:8443/health`
- Check Tailscale Funnel is active: `tailscale funnel status`
- Verify your Mac is awake and online

### "401 Unauthorized"
- Secret key mismatch between local `.env` and Claude.ai Project `.env`
- Run `grep PROXY_SECRET_KEY .env` locally to verify key

### "403 Forbidden"
- Command validation failed (only git commands allowed)
- Check logs in Flask server terminal

## Success Criteria

All 5 tests pass = Full proof of concept working!

This means Claude.ai can:
- ✅ Read environment variables from Project
- ✅ Reach your local machine through Tailscale Funnel
- ✅ Execute authenticated git operations
- ✅ Clone repositories
- ✅ Check git status

## Next Steps After Success

1. Create a dedicated GitHub repo for your Google Sheets Formula project
2. Have Claude.ai clone it
3. Make changes to project knowledge
4. Commit and push changes
5. Claude.ai is now managing its own context!
