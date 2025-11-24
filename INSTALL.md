# Installation Guide

## Prerequisites

- Python 3.8+
- GitLab Owner permissions on target groups
- GitLab Premium+ (for group webhooks)
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
# Edit config.yaml with your GitLab URL, groups, and Qodo webhook endpoint
```

**Note**: Webhook secret is auto-generated if omitted (recommended).

## Step 3: Set Environment Variable

Set your GitLab access token:

```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
```

**Important**: This token needs Owner permissions on all target groups.

## Step 4: Test Connection (Optional)

```bash
python test_connection.py
```

## Step 5: Dry Run

```bash
python qodo_gitlab_install.py --config config.yaml --dry-run
```

## Step 6: Run Installation

```bash
python qodo_gitlab_install.py --config config.yaml
```

**Save the output**: Token values and auto-generated webhook secrets are shown only once.

## Step 7: Generate Report (Optional)

```bash
python qodo_gitlab_install.py --config config.yaml --report report.json
```

## Troubleshooting

### "Group webhooks not available"
GitLab Free tier detected. Upgrade to Premium+ or modify script for project-level webhooks.

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
