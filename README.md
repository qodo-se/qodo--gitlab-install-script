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
# Edit: gitlab_base_url, root_groups and/or projects, webhooks.merge_request_url

# 4. Run
python qodo_gitlab_install.py --config config.yaml
```

## What It Does

- Creates group or project access tokens with `api` and `read_repository` scope (covers both Qodo Merge and Qodo Aware)
- Auto-generates secure webhook secrets
- Configures webhooks for merge requests and comments (push/pipeline events disabled)
- Processes specified root groups (webhooks apply to all subgroups automatically via GitLab's group webhook inheritance)
- Supports individual project targeting (useful for GitLab Free tier or cherry-picking specific projects)
- Detects group coverage overlap when both groups and projects are configured
- Validates configuration with `--check` mode before making changes
- Idempotent (safe to re-run)

## Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `gitlab_base_url` | Yes | GitLab instance URL |
| `auth_mode` | Yes | Must be `group_token_per_root_group` |
| `root_groups` | No* | Group paths or IDs to configure |
| `projects` | No* | Individual project paths or IDs |
| `webhooks.merge_request_url` | Yes | Qodo webhook endpoint |
| `webhooks.secret_token` | No | Auto-generated if omitted |
| `token_expires_in_days` | No | Default: 365 |
| `dry_run` | No | Default: false |
| `log_level` | No | Default: info |

*At least one of `root_groups` or `projects` must be specified.

## CLI Options

```bash
# Dry run
python qodo_gitlab_install.py --config config.yaml --dry-run

# Validate configuration without making changes
python qodo_gitlab_install.py --config config.yaml --check

# Debug logging
python qodo_gitlab_install.py --config config.yaml --log-level debug
```

## Requirements

- Python 3.8+
- GitLab Owner role on target groups (for group webhooks)
- GitLab Maintainer+ role on target projects (for project tokens)
- GitLab Premium+ (for group webhooks; project webhooks work on all tiers)

## Exit Codes

- `0` - Success (or all checks passed in `--check` mode)
- `1` - Check mode: one or more checks failed
- `2` - Partial success (some groups/projects skipped)
- `3` - Authentication/permission failure

## Documentation

- [INSTALL.md](INSTALL.md) - Installation guide
- [EXAMPLES.md](EXAMPLES.md) - Usage examples
- [AGENTS.md](AGENTS.md) - Architecture and design decisions
