#!/usr/bin/env python3
"""
Simple test script to verify GitLab connection and permissions.
Run this before the main installation script to validate your setup.
"""

import os
import sys
import requests
import yaml


def test_gitlab_connection(base_url: str, token: str):
    """Test basic GitLab API connection"""
    print("Testing GitLab connection...")
    
    try:
        response = requests.get(
            f"{base_url}/api/v4/user",
            headers={'PRIVATE-TOKEN': token}
        )
        response.raise_for_status()
        user = response.json()
        
        print(f"✅ Connected successfully!")
        print(f"   User: {user.get('username')} ({user.get('name')})")
        print(f"   Email: {user.get('email')}")
        print(f"   Admin: {user.get('is_admin', False)}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_group_access(base_url: str, token: str, group_path: str):
    """Test access to a specific group"""
    print(f"\nTesting access to group '{group_path}'...")
    
    try:
        # Search for group
        response = requests.get(
            f"{base_url}/api/v4/groups",
            headers={'PRIVATE-TOKEN': token},
            params={'search': group_path}
        )
        response.raise_for_status()
        groups = response.json()
        
        group = None
        for g in groups:
            if g['full_path'] == group_path or g['path'] == group_path:
                group = g
                break
        
        if not group:
            print(f"❌ Group not found: {group_path}")
            return False
        
        print(f"✅ Group found!")
        print(f"   ID: {group['id']}")
        print(f"   Name: {group['name']}")
        print(f"   Path: {group['full_path']}")
        
        # Check permissions
        # Access level: 50 = Owner, 40 = Maintainer, 30 = Developer
        # We need at least Maintainer (40) to manage webhooks
        # We need Owner (50) for group webhooks
        
        # Try to get group details (requires at least Guest access)
        response = requests.get(
            f"{base_url}/api/v4/groups/{group['id']}",
            headers={'PRIVATE-TOKEN': token}
        )
        response.raise_for_status()
        group_details = response.json()
        
        # Check if we can list access tokens (requires Owner)
        try:
            response = requests.get(
                f"{base_url}/api/v4/groups/{group['id']}/access_tokens",
                headers={'PRIVATE-TOKEN': token}
            )
            response.raise_for_status()
            print(f"✅ Can manage group access tokens (Owner access)")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"⚠️  Cannot manage group access tokens (need Owner access)")
            else:
                print(f"⚠️  Token management check failed: {e}")
        
        # Check if we can list webhooks (requires Owner)
        try:
            response = requests.get(
                f"{base_url}/api/v4/groups/{group['id']}/hooks",
                headers={'PRIVATE-TOKEN': token}
            )
            response.raise_for_status()
            print(f"✅ Can manage group webhooks (Owner access)")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"⚠️  Cannot manage group webhooks (need Owner access)")
            elif e.response.status_code == 404:
                print(f"⚠️  Group webhooks not available (requires GitLab Premium+)")
            else:
                print(f"⚠️  Webhook check failed: {e}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to access group: {e}")
        return False


def test_project_access(base_url: str, token: str, project_path_or_id: str):
    """Test access to a specific project"""
    print(f"\nTesting access to project '{project_path_or_id}'...")

    try:
        # Resolve project: try by ID first, then by path
        if project_path_or_id.isdigit():
            url = f"{base_url}/api/v4/projects/{project_path_or_id}"
        else:
            from urllib.parse import quote
            encoded = quote(project_path_or_id, safe='')
            url = f"{base_url}/api/v4/projects/{encoded}"

        response = requests.get(url, headers={'PRIVATE-TOKEN': token})
        response.raise_for_status()
        project = response.json()

        print(f"✅ Project found!")
        print(f"   ID: {project['id']}")
        print(f"   Name: {project['name']}")
        print(f"   Path: {project.get('path_with_namespace', '')}")

        # Check if we can list access tokens (requires Maintainer+)
        try:
            response = requests.get(
                f"{base_url}/api/v4/projects/{project['id']}/access_tokens",
                headers={'PRIVATE-TOKEN': token}
            )
            response.raise_for_status()
            print(f"✅ Can manage project access tokens (Maintainer+ access)")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"⚠️  Cannot manage project access tokens (need Maintainer+ access)")
            else:
                print(f"⚠️  Token management check failed: {e}")

        # Check if we can list webhooks (requires Maintainer+)
        try:
            response = requests.get(
                f"{base_url}/api/v4/projects/{project['id']}/hooks",
                headers={'PRIVATE-TOKEN': token}
            )
            response.raise_for_status()
            print(f"✅ Can manage project webhooks (Maintainer+ access)")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"⚠️  Cannot manage project webhooks (need Maintainer+ access)")
            else:
                print(f"⚠️  Webhook check failed: {e}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to access project: {e}")
        return False


def main():
    """Main test function"""
    print("=" * 80)
    print("Qodo GitLab Integration - Connection Test")
    print("=" * 80)
    
    # Get token from environment
    token = os.environ.get('GITLAB_ADMIN_TOKEN') or os.environ.get('GITLAB_BOT_PAT')
    if not token:
        print("❌ GitLab token not found!")
        print("   Set GITLAB_ADMIN_TOKEN or GITLAB_BOT_PAT environment variable.")
        return 1
    
    print(f"✅ Token found (length: {len(token)})")
    
    # Try to load config
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        config_path = 'config.example.yaml'
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        base_url = config['gitlab_base_url'].rstrip('/')
        root_groups = config.get('root_groups') or []
        projects = config.get('projects') or []

        print(f"✅ Configuration loaded from {config_path}")
        print(f"   GitLab URL: {base_url}")
        if root_groups:
            print(f"   Root groups: {', '.join(str(g) for g in root_groups)}")
        if projects:
            print(f"   Projects: {', '.join(str(p) for p in projects)}")
        if not root_groups and not projects:
            print("   ⚠️  No root_groups or projects configured")

    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        print("   Using manual input...")
        base_url = input("Enter GitLab URL (e.g., https://gitlab.company.com): ").rstrip('/')
        root_groups = [input("Enter a group path to test (e.g., engineering): ")]
        projects = []

    print("\n" + "=" * 80)

    # Test connection
    if not test_gitlab_connection(base_url, token):
        return 1

    # Test group access
    for group_path in root_groups:
        if not test_group_access(base_url, token, str(group_path)):
            print(f"\n⚠️  Warning: Issues accessing group '{group_path}'")

    # Test project access
    for project_entry in projects:
        if not test_project_access(base_url, token, str(project_entry)):
            print(f"\n⚠️  Warning: Issues accessing project '{project_entry}'")
    
    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
