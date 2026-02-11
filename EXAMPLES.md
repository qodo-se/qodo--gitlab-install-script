# Usage Examples

## Single Root Group

```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"
root_groups:
  - "engineering"
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
```

Creates token for "engineering" group and configures webhook (automatically applies to all subgroups).

## Multiple Root Groups

```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"
root_groups:
  - "engineering"
  - "product"
  - "design"
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
```

Creates one token per root group and configures webhooks (automatically apply to all subgroups).

## Using Group IDs Instead of Paths

```yaml
root_groups:
  - "12345"
  - "67890"
```

Useful when group paths are ambiguous or contain special characters.

## Individual Projects

```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"
projects:
  - "engineering/backend/auth-service"
  - "standalone/external-tool"
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
```

Creates a project access token and project webhook for each specified project. Useful for GitLab Free tier (no group webhooks) or targeting specific projects.

## Mixed Groups and Projects

```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"
root_groups:
  - "engineering"
projects:
  - "standalone/external-tool"
  - "12345"
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
```

Processes groups first (with group-level tokens and webhooks), then individual projects. If a project is already covered by a group webhook, a warning is logged but the project token and webhook are still created.

## Using Project IDs

```yaml
projects:
  - "12345"
  - "67890"
```

Useful when project paths are long or contain special characters.

## Custom Token Expiration

```yaml
token_expires_in_days: 180
```

Tokens expire after 180 days instead of default 365.

## Custom Webhook Secret

```yaml
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "your-secure-secret-here"
```

If omitted, a secure random secret is auto-generated.

## Workflow Examples

### Test Connection First

```bash
python test_connection.py
```

Verifies authentication and permissions before running the installer.

### Validate Configuration

```bash
python qodo_gitlab_install.py --config config.yaml --check
```

Checks that all groups/projects exist, verifies permissions, and reports token/webhook state without making any changes. Returns exit code 0 if all checks pass, 1 if any fail.

### Dry Run Before Execution

```bash
python qodo_gitlab_install.py --config config.yaml --dry-run
python qodo_gitlab_install.py --config config.yaml
```

Preview changes without modifying GitLab.

### Debug Mode

```bash
python qodo_gitlab_install.py --config config.yaml --log-level debug
```

Shows detailed API calls and responses.

### Generate JSON Report

```bash
python qodo_gitlab_install.py --config config.yaml --report report.json
```

Saves structured output for auditing or automation.

### Full Logging to File

```bash
python qodo_gitlab_install.py --config config.yaml --log-level debug 2>&1 | tee install.log
```

## Troubleshooting

### "Group not found"

Verify the group exists and your token has access:

```bash
curl -H "PRIVATE-TOKEN: $GITLAB_ADMIN_TOKEN" \
  "https://gitlab.company.com/api/v4/groups?search=engineering"
```

### "Cannot manage webhooks"

Check for Owner permissions:

```bash
python test_connection.py
```

Look for warnings about insufficient permissions.

### Rate Limiting

Script automatically retries with exponential backoff. If issues persist, run during off-peak hours.

### Token Already Exists

Script detects existing "Qodo AI Integration" tokens and reuses them. To force recreation, manually delete the old token first.
