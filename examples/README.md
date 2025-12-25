# Git Proxy Examples

## Recommended: Bundle Workflow

**`bundle_workflow.py`** - Complete example of the bundle-based workflow for Claude.ai Projects.

This demonstrates:
- Fetching repositories as bundles
- Cloning into Claude's environment
- Making changes with file operations
- Creating feature branches
- Pushing bundles and creating PRs

**Use this workflow when files need to be in Claude's environment for editing.**

## Legacy: Direct Proxy Workflow

These examples use the direct proxy approach where git commands execute on your Mac and files stay there:

- **`basic_usage.py`** - Basic clone, commit, push operations
- **`claude_self_improvement.py`** - Claude managing project knowledge repos
- **`test_from_claude_ai.py`** - Testing connectivity from Claude.ai

**Use this workflow for simple git operations where you don't need to edit files in Claude's environment.**
