# Qodo GitLab Integration Setup

Automated setup for Qodo Merge and Qodo Aware integration with GitLab.

This script automates the manual setup steps described in the official Qodo documentation:
- **[Qodo Merge - GitLab Single-Tenant Setup](https://docs.qodo.ai/qodo-documentation/qodo-merge/getting-started/setup-and-installation/gitlab/qodo-single-tenant-gitlab)**
- **[Qodo Aware - Index Your GitLab Codebase](https://docs.qodo.ai/qodo-documentation/qodo-aware/getting-started/enterprise-self-hosted/3.-index-your-codebase/gitlab)**

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Create Personal Access Token
# Go to GitLab → Preferences → Access Tokens
# Create token with 'api' scope and Owner role on target groups
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"

# 3. Configure
cp config.example.yaml config.yaml
# Edit: gitlab_base_url, root_groups, webhooks.merge_request_url

# 4. Run
python qodo_gitlab_install.py --config config.yaml
```

## What It Does

- Creates group access tokens with `api` and `read_repository` scope (covers both Qodo Merge and Qodo Aware)
- Auto-generates secure webhook secrets
- Configures webhooks for merge requests and comments (push/pipeline events disabled)
- Processes specified root groups only (webhooks apply to all subgroups automatically via GitLab's group webhook inheritance)
- Idempotent (safe to re-run)

## Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `gitlab_base_url` | Yes | GitLab instance URL |
| `auth_mode` | Yes | Must be `group_token_per_root_group` |
| `root_groups` | Yes | Group paths or IDs to configure |
| `webhooks.merge_request_url` | Yes | Qodo webhook endpoint |
| `webhooks.secret_token` | No | Auto-generated if omitted |
| `token_expires_in_days` | No | Default: 365 |
| `dry_run` | No | Default: false |
| `log_level` | No | Default: info |

## CLI Options

```bash
# Dry run
python qodo_gitlab_install.py --config config.yaml --dry-run

# Debug logging
python qodo_gitlab_install.py --config config.yaml --log-level debug
```

## Requirements

- Python 3.8+
- GitLab Owner role on target groups
- GitLab Premium+ (for group webhooks)

## Exit Codes

- `0` - Success
- `2` - Partial success (some groups skipped)
- `3` - Authentication/permission failure

## Documentation

- [INSTALL.md](INSTALL.md) - Installation guide
- [EXAMPLES.md](EXAMPLES.md) - Usage examples
- [AGENTS.md](AGENTS.md) - Architecture and design decisions
