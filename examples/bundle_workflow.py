#!/usr/bin/env python3
"""
Bundle Workflow Example for Claude.ai

This demonstrates the recommended approach for Claude.ai Projects:
1. Fetch repository as bundle from proxy
2. Clone bundle locally in Claude's environment
3. Edit files using normal file operations
4. Create feature branch and bundle changes
5. Push bundle back through proxy with PR creation
"""

import subprocess
import os
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.git_client import GitProxyClient


def run_git(command, cwd='.'):
    """Helper to run git commands"""
    result = subprocess.run(
        command.split(),
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.returncode == 0, result.stdout


def main():
    """Complete bundle workflow example"""

    # Configuration
    repo_url = 'https://github.com/user/example-repo.git'
    bundle_file = 'repo.bundle'
    local_dir = 'repo'
    branch_name = 'feature/claude-improvements'

    # Initialize proxy client
    print("Initializing proxy client...")
    client = GitProxyClient()

    # Step 1: Fetch repository as bundle
    print(f"\n1. Fetching {repo_url} as bundle...")
    client.fetch_bundle(repo_url, bundle_file)
    print(f"   ✓ Bundle saved to {bundle_file}")

    # Step 2: Clone bundle locally
    print(f"\n2. Cloning bundle into {local_dir}/...")
    run_git(f'git clone {bundle_file} {local_dir}')
    run_git(f'git remote set-url origin {repo_url}', cwd=local_dir)
    print(f"   ✓ Repository cloned")

    # Step 3: Edit files (example)
    print("\n3. Making improvements...")
    readme_path = Path(local_dir) / 'README.md'

    if readme_path.exists():
        with open(readme_path, 'a') as f:
            f.write('\n## Improvements from Claude\n\n')
            f.write('Added automated documentation updates.\n')
        print("   ✓ Updated README.md")
    else:
        # Create new file as example
        with open(Path(local_dir) / 'IMPROVEMENTS.md', 'w') as f:
            f.write('# Claude Improvements\n\n')
            f.write('This file documents improvements made by Claude.\n')
        print("   ✓ Created IMPROVEMENTS.md")

    # Step 4: Commit changes
    print("\n4. Committing changes...")
    run_git('git add .', cwd=local_dir)
    run_git('git commit -m "Add improvements from Claude"', cwd=local_dir)
    print("   ✓ Changes committed")

    # Step 5: Create feature branch
    print(f"\n5. Creating branch {branch_name}...")
    run_git(f'git checkout -b {branch_name}', cwd=local_dir)
    print("   ✓ Branch created")

    # Step 6: Create bundle of changes
    print("\n6. Creating bundle of changes...")
    success, _ = run_git(
        f'git bundle create ../changes.bundle main..{branch_name}',
        cwd=local_dir
    )
    if success:
        print("   ✓ Bundle created: changes.bundle")

    # Step 7: Push bundle and create PR
    print("\n7. Pushing bundle and creating PR...")
    result = client.push_bundle(
        'changes.bundle',
        repo_url,
        branch_name,
        create_pr=True,
        pr_title='Improvements from Claude',
        pr_body='Automated improvements including documentation updates.'
    )

    print(f"   ✓ Branch {result['branch']} pushed")

    if result.get('pr_created'):
        print(f"   ✓ PR created: {result['pr_url']}")
    else:
        print(f"   ! PR creation failed: {result.get('pr_error', 'Unknown error')}")

    # Cleanup
    print("\n8. Cleaning up...")
    os.remove(bundle_file)
    os.remove('changes.bundle')
    print("   ✓ Temporary files removed")

    print("\n✅ Complete! Repository cloned, changes made, and PR created.")
    print(f"   Files remain in {local_dir}/ for further work.")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
