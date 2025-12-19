#!/usr/bin/env python3
"""
Test script for Claude.ai to verify git proxy connectivity.
Upload this along with client/git_client.py to your Claude.ai Project.
"""

import os
import sys

# Add parent directory to path so we can import git_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_client import GitProxyClient


def test_environment_variables():
    """Test 1: Verify environment variables are set"""
    print("=" * 60)
    print("Test 1: Environment Variables")
    print("=" * 60)

    url = os.environ.get('GIT_PROXY_URL')
    key = os.environ.get('GIT_PROXY_KEY')

    if not url:
        print("❌ GIT_PROXY_URL not found in environment")
        return False

    if not key:
        print("❌ GIT_PROXY_KEY not found in environment")
        return False

    print(f"✓ GIT_PROXY_URL: {url}")
    print(f"✓ GIT_PROXY_KEY: {'*' * 20} (hidden)")
    print()
    return True


def test_health_check():
    """Test 2: Check proxy server health"""
    print("=" * 60)
    print("Test 2: Health Check")
    print("=" * 60)

    try:
        client = GitProxyClient()
        health = client.health_check()

        print(f"✓ Status: {health['status']}")
        print(f"✓ Workspace: {health['workspace']}")
        print(f"✓ Timestamp: {health['timestamp']}")
        print()
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        print()
        return False


def test_list_workspace():
    """Test 3: List repositories in workspace"""
    print("=" * 60)
    print("Test 3: List Workspace")
    print("=" * 60)

    try:
        client = GitProxyClient()
        repos = client.list_workspace()

        print(f"✓ Found {len(repos)} repositories")
        if repos:
            for repo in repos:
                print(f"  - {repo['name']}: {repo['path']}")
        else:
            print("  (workspace is empty)")
        print()
        return True
    except Exception as e:
        print(f"❌ List workspace failed: {e}")
        print()
        return False


def test_clone_repository():
    """Test 4: Clone a test repository"""
    print("=" * 60)
    print("Test 4: Clone Repository")
    print("=" * 60)

    try:
        client = GitProxyClient()

        # Clone a small public repo for testing
        repo_url = 'https://github.com/octocat/Hello-World.git'
        print(f"Cloning {repo_url}...")

        repo_path = client.clone(repo_url)

        print(f"✓ Cloned to: {repo_path}")
        print()
        return repo_path
    except Exception as e:
        print(f"❌ Clone failed: {e}")
        print()
        return None


def test_git_status(repo_path):
    """Test 5: Check git status"""
    print("=" * 60)
    print("Test 5: Git Status")
    print("=" * 60)

    if not repo_path:
        print("❌ No repository to check (clone failed)")
        print()
        return False

    try:
        client = GitProxyClient()
        status = client.status(repo_path, short=False)

        print("✓ Git status:")
        print(status)
        print()
        return True
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        print()
        return False


def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "=" * 60)
    print("GIT PROXY PROOF OF CONCEPT TESTS")
    print("=" * 60 + "\n")

    results = {
        'Environment Variables': test_environment_variables(),
        'Health Check': test_health_check(),
        'List Workspace': test_list_workspace(),
    }

    # Clone test (returns repo_path for next test)
    repo_path = test_clone_repository()
    results['Clone Repository'] = repo_path is not None

    # Status test (uses repo_path from clone)
    results['Git Status'] = test_git_status(repo_path)

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(results.values())

    print()
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Git proxy is working perfectly!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
