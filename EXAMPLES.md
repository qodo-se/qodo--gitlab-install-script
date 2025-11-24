# Usage Examples

## Example 1: Single Root Group with Subgroups

**Scenario**: You have an "engineering" group with multiple subgroups (frontend, backend, devops).

**config.yaml**:
```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"

root_groups:
  - "engineering"

webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
  events:
    - merge_requests
    - note
    - pipeline
```

**Run**:
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml
```

**Result**: 
- Creates one group access token for "engineering" group
- Creates webhooks on "engineering" and all subgroups (frontend, backend, devops)

---

## Example 2: Multiple Root Groups

**Scenario**: You manage multiple top-level groups (engineering, product, design).

**config.yaml**:
```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"

root_groups:
  - "engineering"
  - "product"
  - "design"

webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
```

**Run**:
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml
```

**Result**:
- Creates three group access tokens (one per root group)
- Creates webhooks on all three groups and their subgroups

---

## Example 3: Using Bot User PAT

**Scenario**: You want to use a single bot user token across all groups.

**config.yaml**:
```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "bot_user_pat"

root_groups:
  - "engineering"
  - "product"

webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
```

**Run**:
```bash
export GITLAB_BOT_PAT="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml
```

**Result**:
- Uses the provided bot PAT for all operations
- No new tokens created
- Creates webhooks on all groups

---

## Example 4: Dry Run First

**Scenario**: You want to preview changes before applying them.

**Run**:
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"

# First, test connection
python test_connection.py

# Then, dry run
python qodo_gitlab_install.py --config config.yaml --dry-run

# Review output, then run for real
python qodo_gitlab_install.py --config config.yaml
```

---

## Example 5: Debug Mode

**Scenario**: Something isn't working and you need detailed logs.

**Run**:
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml --log-level debug
```

**Output**: Detailed API calls, responses, and decision logic.

---

## Example 6: Generate Report

**Scenario**: You need a JSON report for audit/compliance.

**Run**:
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py \
  --config config.yaml \
  --report report.json
```

**report.json**:
```json
{
  "tokens_created": [
    {
      "group_id": 123,
      "token_id": 456,
      "token_name": "Qodo-Integration",
      "token_value": "glpat-xxxxxxxxxxxx"
    }
  ],
  "webhooks_created": [
    {
      "group_id": 123,
      "hook_id": 789,
      "url": "https://qodo.company.com/webhooks/gitlab"
    }
  ],
  "groups_processed": 5,
  "errors": []
}
```

---

## Example 7: Update Webhook Configuration

**Scenario**: You need to add the "push" event to existing webhooks.

**Original config.yaml**:
```yaml
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
  events:
    - merge_requests
    - note
```

**Updated config.yaml**:
```yaml
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
  events:
    - merge_requests
    - note
    - push  # Added
```

**Run**:
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml
```

**Result**: All existing webhooks are updated to include push events.

---

## Example 8: Using Group IDs Instead of Paths

**Scenario**: You know the group IDs and want to use them directly.

**config.yaml**:
```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"

root_groups:
  - "12345"  # Group ID
  - "67890"  # Group ID

webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
```

---

## Example 9: Minimal Events (MR Only)

**Scenario**: You only want merge request events, nothing else.

**config.yaml**:
```yaml
gitlab_base_url: "https://gitlab.company.com"
auth_mode: "group_token_per_root_group"

root_groups:
  - "engineering"

webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "abc123secret"
  events:
    - merge_requests  # Only MR events
```

---

## Example 10: CI/CD Integration

**Scenario**: Run the script in GitLab CI/CD pipeline.

**.gitlab-ci.yml**:
```yaml
qodo_setup:
  stage: deploy
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python qodo_gitlab_install.py --config config.yaml --report report.json
  artifacts:
    paths:
      - report.json
    expire_in: 30 days
  only:
    - main
  variables:
    GITLAB_ADMIN_TOKEN: $QODO_GITLAB_TOKEN  # Set in CI/CD variables
```

---

## Common Patterns

### Pattern 1: Test → Dry Run → Execute

```bash
# 1. Test connection and permissions
python test_connection.py

# 2. Preview changes
python qodo_gitlab_install.py --config config.yaml --dry-run

# 3. Execute
python qodo_gitlab_install.py --config config.yaml
```

### Pattern 2: Execute with Full Logging

```bash
python qodo_gitlab_install.py \
  --config config.yaml \
  --log-level debug \
  --report report.json \
  2>&1 | tee install.log
```

### Pattern 3: Idempotent Cron Job

```bash
#!/bin/bash
# Run daily to ensure configuration stays in sync

export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"

python qodo_gitlab_install.py \
  --config /path/to/config.yaml \
  --report /var/log/qodo/report-$(date +%Y%m%d).json
```

---

## Troubleshooting Examples

### Issue: "Group not found"

**Check**:
```bash
# Verify group path
curl -H "PRIVATE-TOKEN: $GITLAB_ADMIN_TOKEN" \
  "https://gitlab.company.com/api/v4/groups?search=engineering"
```

### Issue: "Cannot manage webhooks"

**Check permissions**:
```bash
python test_connection.py
```

Look for: "⚠️ Cannot manage group webhooks (need Owner access)"

**Solution**: Grant Owner access to your user on the group.

### Issue: Rate limiting

**Solution**: The script handles this automatically with exponential backoff. Just wait.

Or run during off-peak hours:
```bash
# Run at 2 AM
0 2 * * * /path/to/qodo_gitlab_install.py --config /path/to/config.yaml
```
