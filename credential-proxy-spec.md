# Credential Proxy + Skills Architecture

**Authorship note:** This document was drafted by Claude (Opus 4.5) during a conversation with Joshua on 2024-12-27. These are design ideas we iterated on together, not battle-tested patterns. Treat this as a starting point for implementation, not a specification to follow blindly. If something seems wrong or overcomplicated when you're implementing it, it probably is.

**Source conversation:** The thinking behind these decisions is in the chat history. If the rationale for something isn't clear, ask rather than guess.

## Problem Summary

Skills in Claude.ai are powerful because Claude can write arbitrary scripts against APIs. But:
- Embedding credentials in skills blocks publishing them
- MCP tools can provide credentials but can't write to the filesystem or batch operations
- We want: publishable skills + credential security + full scripting flexibility

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude.ai Session                         │
│                                                              │
│  1. MCP call: create_session(services=['bsky','github'])    │
│     ← Returns: session_id, proxy_url                        │
│                                                              │
│  2. Skill script runs with those env vars                   │
│     - Hits proxy with session_id in header                  │
│     - Proxy validates session, injects real credentials     │
│     - Claude writes arbitrary scripts against any endpoint  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│      Unified Proxy (Joshua's Tailscale machine)             │
│                                                              │
│  MCP Interface:          HTTP Interface:                    │
│  - create_session()      - /proxy/<service>/<path>          │
│  - revoke_session()        (transparent forwarding)         │
│  - list_services()       - /git/fetch-bundle (existing)     │
│                          - /git/push-bundle (existing)      │
│                                                              │
│  Session Store:          Credential Store:                  │
│  {session_id: {          {service: {                        │
│    services: [...],        base_url: "...",                 │
│    expires: timestamp      auth_type: "bearer|header",      │
│  }}                        credential: "..."                │
│                          }}                                 │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

**Transparent forwarding, not pre-programmed endpoints.** The proxy doesn't know or care what API endpoints exist. It just:
1. Validates session_id allows access to requested service
2. Forwards request to service's base_url + path
3. Injects credentials based on service's auth_type
4. Returns response

This preserves Claude's ability to write scripts against *any* endpoint, not just ones we anticipated.

**Session-based, not credential-based.** Even for services without native short-lived tokens, we create our own session layer. Credentials never appear in Claude's context.

**Extend existing git-proxy, don't create new repo.** The git bundle endpoints (`/git/fetch-bundle`, `/git/push-bundle`) remain as-is - they're special cases that can't use transparent forwarding. Everything else goes through `/proxy/<service>/<path>`.

## Implementation Plan

### Phase 1: Extend the Server

Modify the existing Flask server in claude-credential-proxy to add:

1. **Session management**
   - In-memory dict is fine for prototype (sessions don't need to survive restarts)
   - `POST /sessions` - create session, returns session_id
   - `DELETE /sessions/<id>` - revoke session
   - Sessions expire after configurable TTL (default 30 min)

2. **Credential store**
   - JSON file or env vars, your choice
   - Structure per service: `{base_url, auth_type, auth_header?, credential}`
   - `auth_type` options: `bearer` (Authorization: Bearer X), `header` (custom header name), `query` (append to URL)

3. **Transparent proxy endpoint**
   - `ANY /proxy/<service>/<path:rest>` 
   - Validate `X-Session-Id` header
   - Check session allows this service
   - Forward request with credentials injected
   - Stream response back (don't buffer large responses)

### Phase 2: MCP Server

Minimal MCP server that wraps the session management HTTP endpoints. Can be same process or separate.

Tools:
- `create_session(services: list[str], ttl_minutes: int = 30) -> {session_id, proxy_url, expires_in_minutes}`
- `revoke_session(session_id: str) -> {status}`
- `list_services() -> {services: list[str]}`

### Phase 3: Bluesky Skill (Test Case)

Port the existing bluesky-access skill to use this pattern:
- Remove config.json with credentials
- Scripts read `SESSION_ID` and `PROXY_URL` from env
- All API calls go through proxy
- SKILL.md documents that MCP server must be connected

## File Structure (Proposed)

```
claude-credential-proxy/
├── server/
│   ├── app.py                 # Main Flask app (extend existing)
│   ├── sessions.py            # Session management
│   ├── proxy.py               # Transparent forwarding logic  
│   ├── credentials.json       # Local credential store (gitignored)
│   └── credentials.example.json
├── mcp/
│   ├── server.py              # MCP server implementation
│   └── README.md              # MCP setup instructions
├── skills/
│   ├── bluesky-access/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── search_bluesky.py
│   │       └── get_post.py
│   └── git-proxy/             # Existing, maybe rename
│       ├── SKILL.md
│       └── git_client.py
└── README.md
```

## What This Document Doesn't Cover

- OAuth token refresh flows (handle when we need a service that requires it)
- Rate limiting on proxy side (add if it becomes a problem)
- Multi-user support (this is Joshua's personal infra)
- Production hardening (prototype first)

## Reference Materials

For Claude Code implementing this:
- Current git-proxy implementation: see the .zip file in context
- Current bluesky-access skill: see the .skill file in context
- Transparent proxy pattern: standard HTTP forwarding, nothing exotic
- MCP server creation: https://modelcontextprotocol.io/quickstart/server

## Open Questions

1. Should git operations also go through session auth, or keep the separate `X-Auth-Key` for backward compatibility during transition?
2. Where should the MCP server run - same process as Flask, or separate? Same machine?
3. ~~Naming: "claude-git-bridge" no longer describes what this is. Rename to "claude-credential-proxy" or similar?~~ **Done - renamed to claude-credential-proxy**

---

*End of spec. Implementation should start with the server changes, verify with curl, then add MCP, then port a skill.*
