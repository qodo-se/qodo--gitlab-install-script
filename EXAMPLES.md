# Usage Examples

## Single Root Group

```yaml
root_groups:
  - "engineering"
```

Creates token for "engineering" and webhooks on all subgroups.

## Multiple Root Groups

```yaml
root_groups:
  - "engineering"
  - "product"
  - "design"
```

Creates token per group and webhooks on all subgroups.

## Bot User PAT Mode

```yaml
auth_mode: "bot_user_pat"
root_groups:
  - "engineering"
```

```bash
export GITLAB_BOT_PAT="glpat-xxxxxxxxxxxx"
python qodo_gitlab_install.py --config config.yaml
```

Uses single bot PAT, no new tokens created.

## Dry Run

```bash
python test_connection.py
python qodo_gitlab_install.py --config config.yaml --dry-run
python qodo_gitlab_install.py --config config.yaml
```

## Debug Mode

```bash
python qodo_gitlab_install.py --config config.yaml --log-level debug
```

## Generate Report

```bash
python qodo_gitlab_install.py --config config.yaml --report report.json
```

## Update Webhook Events

Edit `config.yaml` to add/remove events, then re-run. Script updates existing webhooks.

## Using Group IDs

```yaml
root_groups:
  - "12345"
  - "67890"
```

## CI/CD Integration

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
  only:
    - main
  variables:
    GITLAB_ADMIN_TOKEN: $QODO_GITLAB_TOKEN
```

## Common Patterns

**Test → Dry Run → Execute**
```bash
python test_connection.py
python qodo_gitlab_install.py --config config.yaml --dry-run
python qodo_gitlab_install.py --config config.yaml
```

**Full Logging**
```bash
python qodo_gitlab_install.py --config config.yaml --log-level debug --report report.json 2>&1 | tee install.log
```

**Cron Job**
```bash
0 2 * * * python qodo_gitlab_install.py --config /path/to/config.yaml --report /var/log/qodo/report-$(date +%Y%m%d).json
```

## Troubleshooting

**"Group not found"**
```bash
curl -H "PRIVATE-TOKEN: $GITLAB_ADMIN_TOKEN" "https://gitlab.company.com/api/v4/groups?search=engineering"
```

**"Cannot manage webhooks"**
```bash
python test_connection.py  # Check for Owner access warning
```

**Rate limiting**: Script auto-retries. Run during off-peak hours if needed.
