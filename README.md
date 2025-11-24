# Qodo GitLab Integration Setup

Automated setup for Qodo Merge and Qodo Aware integration with GitLab.

## Quick Start

```bash
# 1. Install
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your GitLab URL and groups

# 3. Run
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml
```

## What It Does

- Creates access tokens with `api` scope (covers Qodo Merge + Aware)
- Auto-generates secure webhook secrets
- Configures webhooks on all groups and subgroups
- Idempotent and safe to re-run

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `gitlab_base_url` | Yes | Your GitLab instance URL |
| `auth_mode` | Yes | `group_token_per_root_group` or `bot_user_pat` |
| `root_groups` | Yes | List of root group paths/IDs to manage |
| `webhooks.merge_request_url` | Yes | Qodo webhook endpoint |
| `webhooks.secret_token` | No | Webhook signature secret (auto-generated if omitted) |

## Options

```bash
# Dry run (no changes)
python qodo_gitlab_install.py --config config.yaml --dry-run

# Debug mode
python qodo_gitlab_install.py --config config.yaml --log-level debug

# Save state and report
python qodo_gitlab_install.py --config config.yaml --state state.json --report report.json
```

## Requirements

- Python 3.8+
- GitLab Owner permissions on target groups
- GitLab Premium+ (for group webhooks)

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Documentation

- [INSTALL.md](INSTALL.md) - Detailed installation guide
- [EXAMPLES.md](EXAMPLES.md) - Usage examples
- [AGENTS.md](AGENTS.md) - Technical documentation

## Exit Codes

- `0` - Success (idempotent, no errors)
- `2` - Partial success (some groups skipped)
- `3` - Authentication/permission failure
