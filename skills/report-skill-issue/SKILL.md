---
name: report-skill-issue
description: >
  Guidelines for reporting bugs and enhancement ideas using the
  report_skill_issue MCP tool. Read this before calling the tool to
  understand writing style, parameter expectations, and how to produce
  useful issue reports.
---

# Report Skill Issue

Use the `report_skill_issue` MCP tool to document what you encountered
while using a skill -- a script that returned unexpected output,
documentation that led you down an inefficient path, or a pattern you
discovered that could be made easier.

**Read this file before calling the tool.** It covers writing style,
parameter expectations, and examples.

## Writing Style

Frame your report as a factual record of what you tried and what happened,
not as a directive about what should change.

### Title

Describe what you observed, not what should change.

- Good: `searchPosts routes to public endpoint, returns 403`
- Avoid: `searchPosts needs to be reclassified as auth_required`

### Description

Lead with context -- what you were trying to accomplish and which parts of
the skill you interacted with.

### Observations vs. Verdicts

Present findings as observations, not verdicts.

- Use: "appeared to", "seemed to", "returned"
- Avoid: "is broken", "fails", "is dead code"

### Suggestions

Frame as proposals rather than directives.

- Use: "One approach might be...", "It could help to..."
- Avoid: "The fix is...", "This needs to..."

## Parameters

### `skill_name` (required)

Name of the skill: `"bluesky"`, `"git-proxy"`, `"gmail"`, `"sift"`.

### `title` (required)

Brief, observational issue title. Maximum 200 characters. See Writing
Style above for guidance.

### `description` (required)

Context for the observation -- what you were trying to accomplish and which
parts of the skill system you interacted with.

### `issue_type`

`"bug"` (unexpected behavior observed) or `"enhancement"` (idea for
improvement). Default: `"bug"`.

### `skill_version`

Version from the skill's `CHANGELOG.md` -- the version number in the most
recent entry (e.g., `"2.0.4"`). **Always check the CHANGELOG.md file
packaged with the skill and include this** so the maintainer knows which
version you were working with.

Example CHANGELOG entry:

```
## [2.0.4] - 2026-02-13
```

The version here is `2.0.4`.

### `interaction_log`

Step-by-step record of what you did. This is the most useful part of a
bug report -- it lets the maintainer reproduce the problem.

Include:

- Which skill files you read
- Scripts you executed (with commands in code blocks)
- Tool calls you made
- How you troubleshot

Mark each step as succeeded or failed **without explaining why**. Let the
facts speak for themselves.

Example:

```
1. Read bsky_client.py, noted searchPosts in _PUBLIC_ONLY set
2. Ran: `api.get('app.bsky.feed.searchPosts', {'q': 'claude', 'limit': 3})` -- returned 403
3. Tested direct curl to public endpoint -- also 403
4. Tested via proxy path -- returned 200 with results
```

### `observed_behavior`

Numbered factual statements of what occurred. Present comparative data
neutrally -- show before/after states, different error messages, or
alternate approaches as observations rather than conclusions about which
is better.

Example:

```
1. Public endpoint (public.api.bsky.app) returned 403 from BunnyCDN
2. Authenticated endpoint (bsky.social) returned 401 AuthMissing
3. Proxy-routed request returned 200 with expected data
```

### `suggestions`

Proposed improvements or ideas, framed as proposals rather than
directives.

Example: `"searchPosts could be moved from _PUBLIC_ONLY to the default
auth-required path, which appeared to resolve the 403 in testing."`

## Examples

### Bug report

```python
report_skill_issue(
    skill_name="bluesky",
    title="searchPosts routes to public endpoint, returns 403",
    description="While searching for posts by a specific user, "
        "the client routed searchPosts to the public API.",
    issue_type="bug",
    skill_version="2.0.1",
    interaction_log="1. Read bsky_client.py, noted searchPosts "
        "in _PUBLIC_ONLY set\n"
        "2. Ran: `api.get('app.bsky.feed.searchPosts', "
        "{'q': 'claude', 'limit': 3})` — returned 403\n"
        "3. Tested direct curl to public endpoint — also 403\n"
        "4. Tested via proxy path — returned 200 with results",
    observed_behavior="1. Public endpoint "
        "(public.api.bsky.app) returned 403 from BunnyCDN\n"
        "2. Authenticated endpoint (bsky.social) returned 401 "
        "AuthMissing\n"
        "3. Proxy-routed request returned 200 with expected data",
    suggestions="searchPosts could be moved from _PUBLIC_ONLY to "
        "the default auth-required path, which appeared to "
        "resolve the 403 in testing."
)
```

### Enhancement idea

```python
report_skill_issue(
    skill_name="git-proxy",
    title="push-bundle response omits PR diff stats",
    description="After pushing a bundle that created a PR, the "
        "response included the PR URL but not the diff stats "
        "(files changed, insertions, deletions).",
    issue_type="enhancement",
    skill_version="1.2.0",
    interaction_log="1. Called push-bundle with a 3-commit bundle\n"
        "2. Response contained pr_url and pr_number\n"
        "3. Had to make a separate GitHub API call to get diff stats",
    observed_behavior="1. push-bundle response: "
        "{'pr_url': '...', 'pr_number': 42}\n"
        "2. GitHub API /pulls/42 response included "
        "additions, deletions, changed_files fields",
    suggestions="It could help to include diff stats in the "
        "push-bundle response so callers don't need an extra "
        "API round-trip."
)
```

## What Makes a Good Report

1. **Reproducible** -- Someone reading your interaction log can follow the
   same steps and see the same result.
2. **Factual** -- Observations are stated as facts, not judgments.
3. **Versioned** -- The skill version is included so the maintainer can
   check whether the issue still exists.
4. **Scoped** -- One issue per report. If you found two unrelated
   problems, file two reports.
5. **Contextual** -- The description explains what you were trying to do,
   not just what went wrong.
