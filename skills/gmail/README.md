# Gmail Skill

Access Gmail APIs through the credential proxy. Credentials are managed server-side - no tokens appear in Claude's context.

## What This Skill Does

The Gmail skill allows Claude.ai to search, read, and interact with Gmail via the credential proxy. Claude can list messages, search emails, read message content, manage drafts, and work with labels - all without ever seeing your OAuth credentials.

## Prerequisites

Before setting up the Gmail skill, you need:

1. **Google Cloud Project** - Create a project at [Google Cloud Console](https://console.cloud.google.com)
2. **Enable Gmail API** - Enable the Gmail API for your project
3. **OAuth 2.0 Credentials** - Create OAuth 2.0 credentials (Desktop app type)
4. **Client Credentials** - You'll need your `client_id` and `client_secret` from the OAuth credentials

You can manage all of this at: https://console.cloud.google.com/apis/credentials

## Account Management

Use the `google_oauth_setup.py` script to manage Gmail accounts:

### Add a New Account

Run the interactive setup script:

```bash
uv run scripts/google_oauth_setup.py
```

The script will:
1. Prompt for your Google Cloud `client_id` and `client_secret`
2. Let you select which Google services to authorize (Gmail, Calendar, Drive)
3. Ask you to choose a service name (e.g., `gmail`, `gmail_work`, `gmail_personal`)
4. Open a browser for Google consent
5. Exchange the authorization code for a refresh token
6. Save credentials to `server/credentials.json`

### Rename an Account

```bash
# Interactive mode
uv run scripts/google_oauth_setup.py --rename

# Direct mode
uv run scripts/google_oauth_setup.py --rename gmail gmail_personal
```

### Remove an Account

```bash
# Interactive mode
uv run scripts/google_oauth_setup.py --remove

# Direct mode
uv run scripts/google_oauth_setup.py --remove gmail_work
```

## Changing Scopes or Reauthorizing

If you need to change the scopes (permissions) for an account:

1. Revoke access at https://myaccount.google.com/permissions
2. Run the setup script again with the same service name
3. Select the new scopes when prompted

## Server Restart Required

After adding, renaming, or removing accounts, you must restart the credential proxy servers:

```bash
./scripts/setup-launchagents.sh
```

This restarts both the Flask proxy server and the MCP server to pick up the new credentials.

## Usage with Claude.ai

See `SKILL.md` for instructions on using this skill with Claude.ai through the MCP Custom Connector.
