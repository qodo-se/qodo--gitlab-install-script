# Installation Guide

## Prerequisites

- Python 3.8 or higher
- GitLab Owner permissions on target groups
- GitLab Premium+ (for group webhooks)
- Qodo webhook endpoint URL and secret token

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

Copy the example configuration and customize it:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and set:

- `gitlab_base_url`: Your GitLab instance URL
- `root_groups`: List of root group paths to manage
- `webhooks.merge_request_url`: Your Qodo webhook endpoint
- `webhooks.secret_token`: Your webhook secret token

## Step 3: Set Environment Variable

Set your GitLab access token:

```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
```

**Important**: This token needs Owner permissions on all target groups.

## Step 4: Test Connection (Optional but Recommended)

Verify your setup before running the main script:

```bash
python test_connection.py
```

This will check:
- ✅ GitLab API connection
- ✅ Authentication
- ✅ Group access permissions
- ✅ Token management capabilities
- ✅ Webhook management capabilities

## Step 5: Dry Run

Preview what changes will be made without actually making them:

```bash
python qodo_gitlab_install.py --config config.yaml --dry-run
```

Review the output to ensure everything looks correct.

## Step 6: Run Installation

Execute the actual installation:

```bash
python qodo_gitlab_install.py --config config.yaml
```

**Important**: If using `group_token_per_root_group` mode, the script will output token values that are only shown once. Save these immediately!

## Step 7: Save Report (Optional)

Generate a JSON report of all actions:

```bash
python qodo_gitlab_install.py --config config.yaml --report report.json
```

## Troubleshooting

### "Group webhooks not available"

This means your GitLab instance is on the Free tier. Group webhooks require Premium+.

**Solution**: Either upgrade to Premium+ or modify the script to use project-level webhooks.

### "Cannot manage group access tokens (need Owner access)"

Your token doesn't have Owner permissions on the group.

**Solution**: 
1. Ask a group Owner to grant you Owner access, or
2. Use a token from a user who already has Owner access

### "Authentication failed"

Your token is invalid or expired.

**Solution**: Generate a new token with `api` scope and update the environment variable.

### Rate Limiting

If you see "Rate limited" messages, the script will automatically retry with exponential backoff.

**Solution**: Wait for the script to complete. For large installations, consider running during off-peak hours.

## Verification

After installation, verify:

1. **Tokens Created**: Check the output for token values (save them!)
2. **Webhooks Active**: Go to each group → Settings → Webhooks to verify
3. **Test Webhook**: Trigger a test event (e.g., create an MR) and check Qodo receives it

## Re-running

The script is idempotent and safe to run multiple times:

```bash
python qodo_gitlab_install.py --config config.yaml
```

It will:
- ✅ Skip creating tokens that already exist
- ✅ Skip creating webhooks that already exist
- ✅ Update webhooks if configuration changed
- ✅ Report what changed vs. what stayed the same

## Updating Configuration

To update webhook settings (e.g., change events or secret):

1. Edit `config.yaml`
2. Run the script again
3. It will update existing webhooks to match the new configuration

## Cleanup (Optional)

To remove all webhooks created by this script, you can manually delete them from GitLab UI:

1. Go to each group → Settings → Webhooks
2. Find webhooks pointing to your Qodo endpoint
3. Delete them

Or create a cleanup script if needed.
