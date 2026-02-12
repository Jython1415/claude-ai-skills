---
name: code-review
description: >
  Multi-agent code review for pull requests. Use when reviewing a PR,
  after creating or updating a pull request, when asked to check code
  quality before merging, or when doing a final review of changes.
  Checks for bugs, logic errors, and CLAUDE.md compliance.
allowed-tools: Bash(gh issue view:*), Bash(gh search:*), Bash(gh issue list:*), Bash(gh pr comment:*), Bash(gh pr diff:*), Bash(gh pr view:*), Bash(gh pr list:*), Bash(gh api:*)
---

# Code Review

You have been asked to review a pull request (or have determined that a
review is warranted). Perform a thorough, high-signal review using
parallel agents.

**Agent assumptions (communicate to all agents and subagents):**
- All tools are functional. Do not test tools or make exploratory calls.
- Only call a tool if required. Every tool call should have a clear purpose.

Follow these steps precisely:

## Step 1: Gather context (2 parallel agents)

**Agent A (haiku):** Return a list of file paths for all relevant CLAUDE.md
files:
- The root CLAUDE.md, if it exists
- Any CLAUDE.md files in directories containing modified files, and all
  parent directories up to the repo root

Use `gh pr diff` and `find` to identify these.

**Agent B (sonnet):** View the PR with `gh pr view` and `gh pr diff`. Return:
- PR number, title, description
- List of changed files
- Plain-language summary of what the changes do

## Step 2: Review (4 parallel agents)

Give each agent the PR title, description, and summary from Step 1. Each
agent returns a list of issues. Each issue includes: description, file path,
line range, and reason (e.g. "CLAUDE.md adherence", "bug").

**Agents 1 + 2: CLAUDE.md compliance (sonnet)**
Audit changes for CLAUDE.md compliance in parallel. When evaluating
compliance for a file, only consider CLAUDE.md files that share a file path
with the file or its parent directories. Each agent reviews independently
for redundancy.

**Agent 3: Bug detection -- diff only (opus)**
Scan for obvious bugs. Focus only on the diff without reading extra context.
Flag only significant bugs; ignore nitpicks and likely false positives. Do
not flag issues that cannot be validated without context outside the diff.

**Agent 4: Bug detection -- with context (opus)**
Look for problems in the introduced code: security issues, incorrect logic,
missing error handling. Read surrounding code as needed, but only flag issues
within the changed code.

**CRITICAL: HIGH SIGNAL ONLY.** Flag issues where:
- Code will fail to compile or parse (syntax errors, type errors, missing
  imports, unresolved references)
- Code will definitely produce wrong results regardless of inputs (clear
  logic errors)
- Clear, unambiguous CLAUDE.md violations where you can quote the exact rule

Do NOT flag:
- Code style or quality concerns
- Potential issues that depend on specific inputs or state
- Subjective suggestions or improvements
- Pre-existing issues not introduced by this PR
- Pedantic nitpicks a senior engineer would ignore
- Issues a linter would catch (do not run the linter)
- General code quality concerns (e.g. test coverage) unless CLAUDE.md
  explicitly requires it
- Issues mentioned in CLAUDE.md but silenced in code (e.g. lint ignore
  comments)
- Something that appears to be a bug but is actually correct

**If you are not certain an issue is real, do not flag it. False positives
erode trust and waste reviewer time.**

## Step 3: Validate (parallel agents per issue)

For each issue found by Agents 3 and 4 in Step 2, launch a parallel
subagent to validate it. Each validation agent receives:
- The PR title and description
- The issue description and location
- Access to read the relevant source files

The agent's job: verify the issue is real with high confidence. Examples:
- If "variable is not defined" was flagged, confirm it is actually undefined
  in scope.
- For CLAUDE.md violations, confirm the rule is scoped to that file and is
  actually violated.

Use opus subagents for bugs and logic issues. Use sonnet for CLAUDE.md
violations.

Filter out any issues not validated. This produces the final issue list.

## Step 4: Output

Print a summary of findings to the terminal.

If issues were found, list each with:
- File path and line range
- Brief description
- Category (bug, CLAUDE.md violation, etc.)

If no issues were found:

    No issues found. Checked for bugs and CLAUDE.md compliance.

If `--comment` was NOT passed as an argument, **stop here. Do not post any
GitHub comments.**

## Step 5: Post comments (only if --comment was passed)

If NO issues were found, post a single summary comment and stop:

    gh pr comment <PR_NUMBER> --body "## Code review

    No issues found. Checked for bugs and CLAUDE.md compliance."

If issues WERE found, post inline review comments using `gh api`.

First get the latest commit SHA:

    COMMIT_SHA=$(gh pr view <PR_NUMBER> --json headRefOid -q '.headRefOid')

For each issue, post an inline comment:

    gh api \
      repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments \
      -f body="<comment body>" \
      -f path="<file path>" \
      -f commit_id="$COMMIT_SHA" \
      -F line=<line_number> \
      -f side="RIGHT"

For issues spanning multiple lines, add `start_line` and `start_side`:

    gh api \
      repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments \
      -f body="<comment body>" \
      -f path="<file path>" \
      -f commit_id="$COMMIT_SHA" \
      -F start_line=<start_line_number> \
      -f start_side="RIGHT" \
      -F line=<end_line_number> \
      -f side="RIGHT"

Comment formatting rules:
- Provide a brief description of the issue
- For small, self-contained fixes (< 6 lines), include a GitHub suggestion
  block using triple-backtick `suggestion` fencing
- For larger fixes (6+ lines, structural changes, changes spanning multiple
  locations), describe the issue and suggested approach without a suggestion
  block
- Never post a suggestion unless committing it fully resolves the issue
- When citing a CLAUDE.md violation, link to the relevant file using full
  SHA:
  `https://github.com/{owner}/{repo}/blob/{full_sha}/{path}#L{start}-L{end}`
- You must use the full 40-character SHA in links. Do not use shell
  interpolation like `$(git rev-parse HEAD)` inside comment bodies -- the
  body is rendered as Markdown, not executed.
- For comment bodies containing backticks or newlines, write the body to a
  temp file and pass it via `-F body=@/tmp/review-comment.md` to avoid
  shell escaping issues.

**Post only ONE comment per unique issue. No duplicates.**

## Notes

- Use `gh` CLI for all GitHub interactions. Do not use web fetch.
- Create a todo list before starting.
- `{owner}/{repo}` can be obtained from
  `gh repo view --json nameWithOwner -q '.nameWithOwner'`.
