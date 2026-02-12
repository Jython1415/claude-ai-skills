---
name: gmail
description: Search and interact with Gmail via credential proxy
---

# Gmail Access Skill

Access Gmail APIs through the credential proxy. Credentials are managed server-side - no tokens appear in Claude's context.

## Prerequisites

1. **MCP Custom Connector**: Add the credential proxy MCP server as a custom connector in Claude.ai
2. **Gmail Credentials**: Configured on the proxy server in `credentials.json` with OAuth2 setup

## Setup

Before using this skill, create a session using the MCP tools:

```
Use create_session with services: ["gmail"]
```

This returns `session_id` and `proxy_url` (a public HTTPS URL via Cloudflare Tunnel, e.g., `https://proxy.joshuashew.com`) - set these as environment variables for scripts.

## Environment Variables

Scripts expect these environment variables (provided by MCP session):

| Variable | Description |
|----------|-------------|
| `SESSION_ID` | Session ID from create_session |
| `PROXY_URL` | Public proxy URL from create_session (Cloudflare Tunnel URL) |
| `GMAIL_SERVICE` | Service name for Gmail account (default: `gmail`) |

## Multi-Account Support

Multiple Gmail accounts can be configured with custom service names (e.g., `gmail_personal`, `gmail_work`).

### Using a Specific Account

Set the `GMAIL_SERVICE` environment variable to target a non-default account:

```bash
GMAIL_SERVICE=gmail_work SESSION_ID=abc123 PROXY_URL=https://proxy.example.com python list_messages.py
```

When creating a session, include the specific service name:

```
Use create_session with services: ["gmail_work"]
```

## Common Tasks

**Always check scripts/ first** before writing inline API code. The scripts handle authentication, error handling, and response formatting.

| Task | Script | Example |
|------|--------|---------|
| List or search messages | `list_messages.py` | `python list_messages.py "from:alice is:unread" 10` |
| Read a single message | `read_message.py` | `python read_message.py <message_id>` |
| Read an email thread | `read_thread.py` | `python read_thread.py <thread_id>` |
| Find and read a thread | `read_thread.py` | `python read_thread.py --search "subject:meeting"` |
| Custom query / write ops | Direct API call | See [Direct API Usage](#direct-api-usage) below |

## Scripts

### list_messages.py - Search and list messages

```bash
python list_messages.py [query] [max_results]
```

Returns message metadata (From, To, Subject, Date) and preview snippet for each match.

**Examples:**

```bash
# List 10 most recent messages
python list_messages.py

# Search with Gmail query operators
python list_messages.py "from:example@gmail.com is:unread" 25

# All starred messages
python list_messages.py "is:starred"
```

### read_message.py - Read a single message body

```bash
python read_message.py <message_id>
```

Fetches the full message and decodes the MIME body (prefers text/plain, falls back to text/html). Outputs headers (From, To, Cc, Subject, Date) followed by the message body.

**Example:**

```bash
# Get message ID from list_messages.py, then read it
python read_message.py 18d1a2b3c4d5e6f7
```

### read_thread.py - Read an entire email thread

```bash
python read_thread.py <thread_id>
python read_thread.py --search "query"
```

Fetches all messages in a thread and displays them in chronological order with decoded bodies. Accepts a thread ID directly, or use `--search` to find a thread by Gmail query.

**Examples:**

```bash
# Read thread by ID
python read_thread.py 18d1a2b3c4d5e6f7

# Search for a thread and read it
python read_thread.py --search "subject:weekly sync from:manager"
```

## Direct API Usage

For operations not covered by scripts (drafts, labels, custom queries), use the Gmail API directly via the credential proxy.

### List Recent Messages

```python
import os
import requests

SESSION_ID = os.environ['SESSION_ID']
PROXY_URL = os.environ['PROXY_URL']

response = requests.get(
    f"{PROXY_URL}/proxy/gmail/gmail/v1/users/me/messages",
    params={"maxResults": 10},
    headers={"X-Session-Id": SESSION_ID}
)

for msg in response.json().get("messages", []):
    msg_id = msg["id"]
    # Fetch full message details
    msg_response = requests.get(
        f"{PROXY_URL}/proxy/gmail/gmail/v1/users/me/messages/{msg_id}",
        params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
        headers={"X-Session-Id": SESSION_ID}
    )
    print(msg_response.json())
```

### Search Messages

```python
response = requests.get(
    f"{PROXY_URL}/proxy/gmail/gmail/v1/users/me/messages",
    params={"q": "from:example@gmail.com is:unread", "maxResults": 25},
    headers={"X-Session-Id": SESSION_ID}
)
```

### Get a Specific Message

```python
msg_id = "1234567890abcdef"
response = requests.get(
    f"{PROXY_URL}/proxy/gmail/gmail/v1/users/me/messages/{msg_id}",
    params={"format": "full"},
    headers={"X-Session-Id": SESSION_ID}
)
print(response.json())
```

### Create a Draft

```python
import base64
from email.mime.text import MIMEText

# Create MIME message
message = MIMEText("Hello from the credential proxy!")
message["To"] = "recipient@example.com"
message["Subject"] = "Test Email"

# Encode message
raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

# Create draft via API
response = requests.post(
    f"{PROXY_URL}/proxy/gmail/gmail/v1/users/me/drafts",
    json={"message": {"raw": raw}},
    headers={"X-Session-Id": SESSION_ID}
)
print(response.json())
```

## Available Endpoints

All Gmail API v1 endpoints are available via `/proxy/gmail/gmail/v1/users/me/...`. Common ones:

> **Note:** For non-default accounts, substitute the service name in the proxy path (e.g., `/proxy/gmail_work/gmail/v1/users/me/...` instead of `/proxy/gmail/gmail/v1/users/me/...`).

### Message Operations
- `gmail/v1/users/me/messages` - List/search messages (GET with `q` and `maxResults` params)
- `gmail/v1/users/me/messages/{id}` - Get message by ID (GET with `format` and `metadataHeaders` params)
- `gmail/v1/users/me/messages/{id}/modify` - Modify message labels (POST)
- `gmail/v1/users/me/messages/{id}/trash` - Move message to trash (POST)
- `gmail/v1/users/me/messages/{id}/untrash` - Remove message from trash (POST)

> **Note:** `messages/send` is blocked by the proxy - use drafts instead.

### Label Operations
- `gmail/v1/users/me/labels` - List all labels (GET)
- `gmail/v1/users/me/labels/{id}` - Get label by ID (GET)
- `gmail/v1/users/me/labels` - Create label (POST)
- `gmail/v1/users/me/labels/{id}` - Update label (PUT)
- `gmail/v1/users/me/labels/{id}` - Delete label (DELETE)

### Thread Operations
- `gmail/v1/users/me/threads` - List threads (GET)
- `gmail/v1/users/me/threads/{id}` - Get thread by ID (GET)
- `gmail/v1/users/me/threads/{id}/modify` - Modify thread labels (POST)
- `gmail/v1/users/me/threads/{id}/trash` - Move thread to trash (POST)
- `gmail/v1/users/me/threads/{id}/untrash` - Remove thread from trash (POST)

### Draft Operations
- `gmail/v1/users/me/drafts` - List/create drafts (GET/POST)
- `gmail/v1/users/me/drafts/{id}` - Get/update/delete draft (GET/PUT/DELETE)

> **Note:** `drafts/send` is blocked by the proxy.

### Profile Operations
- `gmail/v1/users/me/profile` - Get user profile (email, total messages, threads count)

### Search Query Operators

Gmail supports powerful search operators in the `q` parameter:
- `from:user@example.com` - From specific sender
- `to:user@example.com` - To specific recipient
- `subject:meeting` - Subject contains text
- `is:unread` - Unread messages
- `is:starred` - Starred messages
- `has:attachment` - Has attachments
- `label:important` - Has label
- `after:2024/01/01` - After date
- `before:2024/12/31` - Before date
- `newer_than:7d` - Newer than 7 days
- `older_than:1m` - Older than 1 month

## Security

- Gmail OAuth2 credentials stay on the proxy server
- Sessions expire automatically (default 30 minutes)
- Sessions can be revoked early via `revoke_session` MCP tool
- Only Gmail API endpoints are accessible (not arbitrary URLs)
- All requests use HTTPS with session ID authentication

### Restricted Operations

The proxy enforces endpoint-level filtering for defense-in-depth, independent of OAuth scopes:

**Blocked:**
- **Send** (`messages/send`, `drafts/send`) - Email cannot be sent through the proxy; use drafts instead
- **Permanent delete** (`DELETE messages/{id}`, `DELETE threads/{id}`, `batchDelete`) - Use trash instead
- **Insert/Import** (`POST messages`, `messages/import`) - Direct message insertion is blocked
- **Settings** (all `settings/*` endpoints) - Forwarding, delegates, filters, and other settings are blocked

**Allowed:**
- Read messages, threads, drafts, labels, profile, history
- Draft CRUD (create, read, update, delete)
- Label CRUD (create, read, update, delete)
- Modify labels on messages/threads (`modify`, `batchModify`)
- Trash/untrash messages and threads

## Reporting Issues

Encountered a problem or have a suggestion? Use the `report_skill_issue` MCP tool to submit a bug report or enhancement request.
