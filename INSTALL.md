# Installation Guide

## Prerequisites

- Python 3.8+
- GitLab Owner permissions on target groups (for group webhooks)
- GitLab Maintainer+ permissions on target projects (for project tokens)
- GitLab Premium+ for group webhooks (project webhooks work on all tiers)
- Qodo webhook endpoint URL

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

Or using a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Create Configuration

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your GitLab URL, groups and/or projects, and Qodo webhook endpoint
```

**Note**: Webhook secret is auto-generated if omitted (recommended).

You can target groups, individual projects, or both. At least one of `root_groups` or `projects` must be specified.

## Step 3: Set Environment Variable

Set your GitLab access token:

```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
```

**Important**: This token needs Owner permissions on target groups and Maintainer+ permissions on target projects.

## Step 4: Test Connection (Optional)

```bash
python test_connection.py
```

## Step 5: Validate Configuration (Optional)

```bash
python qodo_gitlab_install.py --config config.yaml --check
```

This checks that all groups/projects exist, permissions are sufficient, and reports current token/webhook state without making any changes.

## Step 6: Dry Run

```bash
python qodo_gitlab_install.py --config config.yaml --dry-run
```

## Step 7: Run Installation

```bash
python qodo_gitlab_install.py --config config.yaml
```

**Important**: Save the output immediately. Token values and auto-generated webhook secrets are displayed only once and cannot be retrieved later.

## Troubleshooting

### "Group webhooks not available"
GitLab Free tier detected. Use `projects` in your config to target individual projects instead (project webhooks work on all tiers), or upgrade to Premium+ for group webhooks.

### "Cannot manage group access tokens"
Token lacks Owner permissions. Request Owner access or use a token from an Owner.

### "Authentication failed"
Token invalid or expired. Generate new token with `api` scope.

### Rate Limiting
Script auto-retries with exponential backoff. Wait for completion or run during off-peak hours.

## Verification

1. Check output for token values (save them)
2. Verify webhooks: Group → Settings → Webhooks
3. Test: Create MR and confirm Qodo receives event

## Re-running

Script is idempotent. Re-run to update configuration:

```bash
python qodo_gitlab_install.py --config config.yaml
```

## Cleanup

Delete webhooks via GitLab UI: Group → Settings → Webhooks
