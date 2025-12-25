# Git Bundle Proxy Examples

## Bundle Workflow

**`bundle_workflow.py`** - Complete example of the bundle-based workflow for Claude.ai Projects.

This demonstrates:
- Fetching repositories as bundles
- Cloning into Claude's environment
- Making changes with file operations
- Creating feature branches
- Pushing bundles and creating PRs

The proxy server acts as a pure pass-through - no files are stored permanently on your Mac. All operations use temporary directories with automatic cleanup.
