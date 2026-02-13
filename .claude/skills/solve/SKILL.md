---
name: solve
description: >
  Turn GitHub issues into reviewed pull requests. Explores the codebase,
  collaboratively scopes design decisions with the user, plans the
  implementation, builds it, and runs code review before presenting the PR.
argument-hint: <issue> [<issue> ...]
allowed-tools: Bash(gh issue view:*), Bash(gh issue list:*), Bash(gh search:*), Bash(gh pr create:*), Bash(gh pr view:*), Bash(gh pr diff:*), Bash(gh pr list:*), Bash(gh pr comment:*), Bash(gh api:*), Bash(git *), Bash(uv *)
---

# Solve

Turn one or more GitHub issues into a reviewed pull request. Work through
these phases in order. Do not skip phases unless explicitly noted.

## Arguments

`$ARGUMENTS` contains issue references separated by spaces. Each may be a
number (`42`), prefixed (`#42`), or a full URL. Parse all references and
normalize to issue numbers.

## Phase 1: Intake

Fetch every issue:

    gh issue view <number> --json title,body,labels,comments,assignees,milestone

For each issue, extract:
- What is being requested (bug fix, feature, refactor, docs, etc.)
- Acceptance criteria or constraints mentioned
- Relevant context from comments

If multiple issues were provided, note how they relate to each other.

## Phase 2: Explore

Build a deep understanding of the codebase as it relates to the issues.
Use subagents (Task tool, subagent_type=Explore) to:

1. Read CLAUDE.md and any project documentation
2. Find code directly relevant to the issue(s) -- modules, files, patterns,
   interfaces
3. Identify conventions, test patterns, and architectural norms the solution
   must follow
4. Search for related PRs or issues that provide additional context

**Do not ask the user anything yet.** Your questions in Phase 3 must be
informed by what you learn here. Generic questions waste the user's time
and signal that you haven't done the work.

## Phase 3: Scope

Triage the issue(s) into one of three categories:

**Trivial** -- The fix is obvious, mechanical, and low-risk (typo, config
change, single-line fix). Skip directly to Phase 4 without user
interaction.

**Well-scoped** -- The issue clearly describes what to build and the
implementation path is clear from your exploration. Briefly present your
understanding and planned approach. Ask the user to confirm, then proceed
to Phase 4.

**Needs design decisions** -- There are open questions about approach,
trade-offs, or how the solution fits into the existing architecture. Enter
the structured decision-making flow below.

### Structured decision-making

Compile every open question, then work through them with the user:

1. State each question clearly, with context on why it matters for *this*
   codebase.
2. Present 3-4 curated options using AskUserQuestion. Each option needs:
   - A concise label (1-5 words)
   - A description covering trade-offs and how the option fits the existing
     code
3. **Your options must demonstrate understanding of the repository.** The
   user should be able to tell whether you "get it" based on the options
   you present. Every option must be tailored to this specific codebase --
   never present generic choices. If your options feel generic, you have
   not explored enough; go back to Phase 2.
4. Only present options you are confident you can implement.

Group related questions (up to 4) into a single AskUserQuestion call.
Progress from high-level architectural decisions down to implementation
details.

## Phase 4: Plan

Write a concrete implementation plan:

1. Create a todo list (TodoWrite) covering every discrete task
2. For each task, specify which files will be created or modified and what
   changes will be made
3. Include test additions or updates where appropriate
4. Note any migration, compatibility, or ordering considerations

Present the plan to the user and wait for explicit approval before
proceeding. Revise if requested.

## Phase 5: Implement

Execute the approved plan:

1. Create a feature branch from the default branch
2. Work through each todo item, marking progress as you go
3. Follow the conventions and patterns discovered in Phase 2
4. Write tests where the project's norms call for them
5. Commit with clear, descriptive messages
6. Push and create a PR that:
   - Has a clear title (under 72 characters)
   - Summarizes the changes in the body
   - Includes `Closes #N` for each issue being resolved

## Phase 6: Verify

Run the project's CI checks locally before requesting review. This catches
lint errors, formatting issues, and test failures before the PR is
presented.

1. Read CI workflow files in `.github/workflows/` to discover what checks
   the project runs (linting, formatting, tests, etc.)
2. Install dependencies if needed (`uv sync`)
3. Run each check locally, matching what CI does. For this project:
   - `uv run ruff check .` (lint)
   - `uv run ruff format --check .` (formatting)
   - `uv run pytest -v` (tests)
4. If any check fails, fix the issue, commit the fix, push to the remote
   branch, and re-run the failing check to confirm it passes
5. Repeat until all checks pass before proceeding

**Important:** Always derive the checks from the workflow files rather than
hardcoding assumptions. Projects change their CI over time.

## Phase 7: Review

Before presenting the PR to the user:

1. Invoke `/code-review` using the Skill tool to run a thorough review of
   the PR
2. If the review surfaces real issues, fix them and commit
3. If fixes were non-trivial, re-run `/code-review`

## Phase 8: Present

Give the user:

- Link to the PR
- Concise summary of what was implemented and why
- Key decisions made during scoping and their rationale
- Review results (clean, or notes on what was flagged and addressed)
- Any known limitations or suggested follow-up work

## Guidelines

- **Delegate aggressively.** Only interactive work (AskUserQuestion,
  presenting plans for approval) needs the main context. Push exploration,
  implementation, and review to subagents (Task tool) to keep the main
  context lean. Phase 2 exploration, Phase 5 implementation of individual
  tasks, Phase 6 verification, and Phase 7 review are all good candidates
  for delegation.
- **Explore before you ask.** Never ask the user a question you could
  answer by reading the code. Uninformed questions erode trust.
- **Options reveal understanding.** The quality of your scoping options is
  the primary signal of whether you understand the problem. Invest effort
  in curating them. If the options are generic, you have not explored
  enough.
- **Don't over-engineer.** Implement what the issues ask for. No
  unrequested features, refactoring, or "improvements."
- **Track progress.** Use TodoWrite throughout so the user has visibility
  into what you're doing and what remains.
- **Be honest about scope.** If the issue is too large for a single PR,
  say so and suggest how to split it.
