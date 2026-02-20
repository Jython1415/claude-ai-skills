---
name: gmail
description: Search and interact with Gmail via credential proxy. Use this skill when the user references their inbox, asks to find or read an email, mentions a specific sender or subject, or asks to draft a reply.
---

# Gmail Skill

Access Gmail APIs through the credential proxy via one Python library:

- **`gmail_client`** -- API client with session-based auth, MIME decoding, and high-level helpers for common workflows

All operations require authentication through the credential proxy. Credentials stay on the proxy server; Claude only gets time-limited session tokens.

## Setup

Add the skill directory to `sys.path`:

```python
import sys
sys.path.insert(0, "/path/to/skills/gmail")
```

Create a session using the `create_session` MCP tool:

```
create_session(services=["gmail"], ttl_minutes=30)
```

Then set the returned values as environment variables:

```python
import os
os.environ["SESSION_ID"] = "<session_id from create_session>"
os.environ["PROXY_URL"] = "<proxy_url from create_session>"
```

Once set, `api.get()`, `api.post()`, `api.delete()`, `api.patch()`, and `api.put()` automatically route through the credential proxy. No additional configuration is needed.

Sessions are service-agnostic -- one session can grant access to multiple services (e.g., `["gmail", "bsky"]`). Sessions expire after the specified TTL (default 30 minutes).

### Multi-account support

Multiple Gmail accounts can be configured with custom service names (e.g., `gmail_personal`, `gmail_work`). Set the `GMAIL_SERVICE` environment variable to target a non-default account:

```python
os.environ["GMAIL_SERVICE"] = "gmail_work"
```

When creating a session, include the specific service name:

```
create_session(services=["gmail_work"], ttl_minutes=30)
```

## Examples

### Search messages

```python
from gmail_client import search

# Search with Gmail query operators
results = search("from:alice@example.com is:unread", max_results=10)
for msg in results:
    h = msg["headers"]
    print(f"From: {h.get('From')}  Subject: {h.get('Subject')}")
    print(f"  Preview: {msg['snippet'][:80]}")
    print(f"  ID: {msg['id']}  Thread: {msg['threadId']}")
```

### Read a full message

```python
from gmail_client import get_message

msg = get_message("18d1a2b3c4d5e6f7")
print(f"From: {msg['headers'].get('From')}")
print(f"Subject: {msg['headers'].get('Subject')}")
print(f"Labels: {msg['labelIds']}")
print()
print(msg["body"])
```

### Read an email thread

```python
from gmail_client import get_thread

thread = get_thread("18d1a2b3c4d5e6f7")
print(f"Thread {thread['id']} — {len(thread['messages'])} messages\n")
for i, msg in enumerate(thread["messages"], 1):
    h = msg["headers"]
    print(f"--- Message {i} ---")
    print(f"From: {h.get('From')}  Date: {h.get('Date')}")
    print(msg["body"])
    print()
```

### Create a draft

```python
from gmail_client import create_draft

draft = create_draft("bob@example.com", "Meeting notes", "Here are the notes from today...")
print(f"Draft created: {draft['id']}")
```

### Reply to a thread

Creates a draft with correct threading headers (`In-Reply-To`, `References`, `threadId`) so it appears as a reply in the conversation:

```python
from gmail_client import create_draft, get_thread

# Get the thread to find the message to reply to
thread = get_thread("18d1a2b3c4d5e6f7")
last_msg = thread["messages"][-1]

draft = create_draft(
    last_msg["headers"]["From"],      # Reply to sender
    f"Re: {last_msg['headers'].get('Subject', '')}",
    "Thanks for the update!",
    thread_id=thread["id"],           # Attach to thread
    reply_to_msg_id=last_msg["id"],   # Sets In-Reply-To and References
)
print(f"Reply draft created: {draft['id']}")
```

### Search and read a conversation

```python
from gmail_client import search, get_thread

# Find a thread by searching for a message in it
results = search("subject:weekly sync from:manager", max_results=1)
if results:
    thread = get_thread(results[0]["threadId"])
    print(f"Thread: {thread['messages'][0]['headers'].get('Subject')}")
    print(f"Messages: {len(thread['messages'])}")
    for msg in thread["messages"]:
        print(f"\n  {msg['headers'].get('From')} — {msg['headers'].get('Date')}")
        print(f"  {msg['body'][:200]}")
```

### Manage labels

```python
from gmail_client import api

# List all labels
labels = api.get("labels")
for label in labels.get("labels", []):
    print(f"{label['id']}: {label['name']}")

# Create a label
new_label = api.post("labels", {"name": "Project/Alpha"})
print(f"Created label: {new_label['id']}")

# Add a label to a message
api.post("messages/msg123/modify", {"addLabelIds": [new_label["id"]]})

# Remove a label from a message
api.post("messages/msg123/modify", {"removeLabelIds": [new_label["id"]]})
```

### Paginate through results

```python
from gmail_client import paginate

# Fetch all messages matching a query (handles pagination automatically)
all_messages = paginate("messages", {"q": "label:important"}, "messages", max_items=500)
print(f"Fetched {len(all_messages)} messages")

# Paginate threads
all_threads = paginate("threads", {"q": "is:unread"}, "threads", page_size=50)
```

### Direct API calls

For operations not covered by helpers, use `api` directly:

```python
from gmail_client import api

# Get user profile
profile = api.get("profile")
print(f"{profile['emailAddress']} — {profile['messagesTotal']} messages")

# Trash a message
api.post("messages/msg123/trash")

# Delete a draft
api.delete("drafts/draft456")

# Update a label
api.put("labels/Label_123", {"name": "Renamed Label"})
```

**Header casing note:** When fetching message metadata with `format=metadata`,
Gmail may return header names in a different case than requested (e.g.,
`Message-Id` instead of `Message-ID`). The `extract_headers` helper handles
this automatically with case-insensitive matching. If you parse headers
manually, compare names case-insensitively.

## API Reference

### `gmail_client` -- API client and helpers

**Core API** (all require `SESSION_ID` and `PROXY_URL`):

| Function | Description |
|----------|-------------|
| `api.get(path, params)` | GET request to `gmail/v1/users/me/{path}` |
| `api.post(path, json)` | POST request |
| `api.delete(path)` | DELETE request |
| `api.patch(path, json)` | PATCH request |
| `api.put(path, json)` | PUT request |

**Message helpers:**

| Function | Description |
|----------|-------------|
| `decode_body(data)` | Decode a base64url-encoded body part |
| `extract_body(payload)` | Walk MIME tree, return text (prefers plain over HTML) |
| `extract_headers(payload, names)` | Extract named headers from a message payload |

**High-level operations:**

| Function | Description |
|----------|-------------|
| `search(query, max_results=10)` | Search messages, return dicts with decoded headers and snippet |
| `get_message(message_id)` | Full message with decoded body, headers, and labels |
| `get_thread(thread_id)` | Full thread with all messages decoded |
| `create_draft(to, subject, body, *, thread_id, reply_to_msg_id)` | Create draft with optional reply threading |
| `paginate(path, params, result_key, *, max_items, page_size)` | Fetch all pages from a paginated endpoint |

### Path construction

All `api.*()` methods build the full URL automatically:

```
{PROXY_URL}/proxy/{GMAIL_SERVICE}/gmail/v1/users/me/{path}
```

Where `GMAIL_SERVICE` defaults to `"gmail"`. You only provide the `path` argument (e.g., `"messages"`, `"threads/abc123"`, `"drafts"`).

## Available Endpoints

Common Gmail API v1 endpoints (pass the path after `users/me/` to `api.*()` methods):

> **Note:** For non-default accounts, set the `GMAIL_SERVICE` environment variable. The client handles the proxy path automatically.

### Message Operations
- `messages` -- List/search messages (GET with `q` and `maxResults` params)
- `messages/{id}` -- Get message by ID (GET with `format` and `metadataHeaders` params)
- `messages/{id}/modify` -- Modify message labels (POST)
- `messages/{id}/trash` -- Move message to trash (POST)
- `messages/{id}/untrash` -- Remove message from trash (POST)

> **Note:** `messages/send` is blocked by the proxy -- use drafts instead.

### Thread Operations
- `threads` -- List threads (GET)
- `threads/{id}` -- Get thread by ID (GET)
- `threads/{id}/modify` -- Modify thread labels (POST)
- `threads/{id}/trash` -- Move thread to trash (POST)
- `threads/{id}/untrash` -- Remove thread from trash (POST)

### Draft Operations
- `drafts` -- List/create drafts (GET/POST)
- `drafts/{id}` -- Get/update/delete draft (GET/PUT/DELETE)

> **Note:** `drafts/send` is blocked by the proxy.

### Label Operations
- `labels` -- List/create labels (GET/POST)
- `labels/{id}` -- Get/update/delete label (GET/PUT/DELETE)

### Profile
- `profile` -- Get user profile (email, total messages, threads count)

## Search Query Operators

Gmail supports powerful search operators in the `q` parameter:

- `from:user@example.com` -- From specific sender
- `to:user@example.com` -- To specific recipient
- `subject:meeting` -- Subject contains text
- `is:unread` -- Unread messages
- `is:starred` -- Starred messages
- `has:attachment` -- Has attachments
- `label:important` -- Has label
- `after:2024/01/01` -- After date
- `before:2024/12/31` -- Before date
- `newer_than:7d` -- Newer than 7 days
- `older_than:1m` -- Older than 1 month

## Security

- Gmail OAuth2 credentials stay on the proxy server
- Sessions expire automatically (default 30 minutes)
- Sessions can be revoked early via `revoke_session` MCP tool
- Only Gmail API endpoints are accessible (not arbitrary URLs)
- All requests use HTTPS with session ID authentication

### Restricted Operations

The proxy enforces endpoint-level filtering for defense-in-depth, independent of OAuth scopes:

**Blocked:**
- **Send** (`messages/send`, `drafts/send`) -- Email cannot be sent through the proxy; use drafts instead
- **Permanent delete** (`DELETE messages/{id}`, `DELETE threads/{id}`, `batchDelete`) -- Use trash instead
- **Insert/Import** (`POST messages`, `messages/import`) -- Direct message insertion is blocked
- **Settings** (all `settings/*` endpoints) -- Forwarding, delegates, filters, and other settings are blocked

**Allowed:**
- Read messages, threads, drafts, labels, profile, history
- Draft CRUD (create, read, update, delete)
- Label CRUD (create, read, update, delete)
- Modify labels on messages/threads (`modify`, `batchModify`)
- Trash/untrash messages and threads

## Rate Limits

**Credential proxy:** 300 requests/minute per session.

**Gmail API quotas:** Gmail API has per-user and per-project quotas. Most read operations cost 5 quota units; batch operations cost more. See [Gmail API usage limits](https://developers.google.com/gmail/api/reference/quota) for details.

## Reporting Issues

Encountered a problem or have a suggestion? Use the `report_skill_issue` MCP tool to submit a bug report or enhancement request.
