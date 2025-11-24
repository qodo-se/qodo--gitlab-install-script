# Qodo GitLab Integration Setup

Automated script to configure GitLab groups for Qodo Merge and Qodo Aware integration.

## Quick Start

1. **Install dependencies**:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Create config file** (`config.yaml`):

```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"

root_groups:
  - "engineering"

webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "your-webhook-secret"
```

3. **Set environment variable**:

```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
```

4. **Run the script**:

```bash
python qodo_gitlab_install.py --config config.yaml
```

## What It Does

- ✅ Creates/verifies access tokens with `api` scope
- ✅ Configures webhooks on all groups and subgroups
- ✅ Idempotent (safe to run multiple times)
- ✅ Reports all changes in JSON format

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `gitlab_base_url` | Yes | Your GitLab instance URL |
| `auth_mode` | Yes | `group_token_per_root_group` or `bot_user_pat` |
| `root_groups` | Yes | List of root group paths/IDs to manage |
| `webhooks.merge_request_url` | Yes | Qodo webhook endpoint |
| `webhooks.secret_token` | Yes | Webhook signature secret |

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

- [INSTALL.md](INSTALL.md) - Step-by-step installation guide
- [EXAMPLES.md](EXAMPLES.md) - Usage examples and common patterns
- [AGENTS.md](AGENTS.md) - Complete technical documentation

## Exit Codes

- `0` - Success (idempotent, no errors)
- `2` - Partial success (some groups skipped)
- `3` - Authentication/permission failure
