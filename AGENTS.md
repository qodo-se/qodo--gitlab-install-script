# Qodo GitLab Integration Setup Script - Technical Documentation

## Table of Contents
1. [Goal & Scope](#goal--scope)
2. [Inputs & Outputs](#inputs--outputs)
3. [Token Strategy](#token-strategy)
4. [Webhook Strategy](#webhook-strategy)
5. [API Surface](#api-surface)
6. [Algorithm](#algorithm)
7. [Data Model](#data-model)
8. [Edge Cases & Guardrails](#edge-cases--guardrails)
9. [Security & Secrets](#security--secrets)
10. [CLI Usage](#cli-usage)
11. [Testing](#testing)

---

## Goal & Scope

### What the Script Does

1. **Traverses** one or more top-level GitLab groups (and all nested subgroups)
2. **Ensures** a single reusable token with sufficient scopes exists for Qodo
3. **Ensures** required group-level webhooks exist (idempotent create/update) pointing to Qodo endpoints
4. **Runs safely** every time (idempotent, retryable) and reports a diff of changes

### Background

- **Qodo Merge** (single-tenant GitLab guide) requires an access token with `api` scope and webhooks on groups/projects to drive MR intelligence
- **Qodo Aware** (Context Engine → GitLab) recommends group access tokens with `read_api` and `read_repository` scopes for indexing
- **Consolidation**: A single token with `api` scope covers both (it implies read_api and grants MR actions Qodo Merge needs)

---

## Inputs & Outputs

### Configuration File (`config.yaml`)

```yaml
# GitLab instance
gitlab_base_url: "https://gitlab.company.com"

# Authentication strategy
auth_mode: "group_token_per_root_group"  # or "bot_user_pat"

# Root groups to manage (paths or IDs)
root_groups:
  - "engineering"
  - "product"

# Webhook configuration
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "your-webhook-secret-here"
  events:
    - merge_requests
    - note
    - pipeline
    - push

# Optional: Qodo context
qodo_context:
  domain: "company.com"
  group_ids: []
  token_destination: "vault"

# Execution options
dry_run: false
log_level: "info"  # info or debug
```

### Outputs

**STDOUT/JSON Report** containing:
- Tokens verified/created (type, scope, owner)
- Webhooks created/updated (group id, URL, events)
- Any errors / groups skipped

**Optional Artifact**: `state.json` (previous run cache) to detect drift

---

## Token Strategy

Two safe options—pick one at deploy time:

### Option A: Group Access Token per Root Group (Recommended)

- **Scope**: `api`
- **Role**: Developer or above (Owner/Maintainer recommended to manage webhooks)
- **Coverage**: Works across all projects in the group hierarchy
- **Least Privilege**: Each root group has its own token

**Why this works:**
- Group tokens can act within all group projects
- `api` scope satisfies both Qodo Aware + Merge requirements
- Minimal blast radius if compromised

### Option B: Single Bot User PAT

- Create a service/bot account
- Grant it **Owner** on each target root group
- Issue one **Personal Access Token** with `api` scope
- **Trade-off**: Broader blast radius vs. simpler distribution

**Implementation Note**: The script detects existing usable tokens first, else creates/rotates appropriately.

---

## Webhook Strategy

### Group Webhooks (Preferred)

- Use **Group Webhooks** (not system or project hooks)
- Apply to **all projects in the group and subgroups**
- Requires **Owner** role on the group

### Required Events

Typical for Qodo integration:
- `merge_requests` (open/update/merge/close)
- `note` (comments on MRs)
- `pipeline` (if Qodo listens for pipeline status)
- `push` (optional, if Qodo wants push events for context)

### Configuration

- `url`: Qodo Merge webhook endpoint from your single-tenant deployment
- `token`: Secret for signature verification
- `enable_ssl_verification`: true (unless using custom CA)

### API Operations

Create/update via **Group Webhooks API**:
1. List existing hooks
2. Compare with desired configuration
3. Create or patch as needed

---

## API Surface

### Authentication
- Header: `PRIVATE-TOKEN: <token>`
- Supports group tokens and PATs

### Groups Traversal
- `GET /groups/:id/subgroups` (paginate) — recursively walk the tree

### Group Access Tokens
- `GET /groups/:id/access_tokens` — find existing usable tokens
- `POST /groups/:id/access_tokens` — create if missing
  - Parameters: `name`, `scopes`, `access_level`, `expires_at` (optional)

### Group Webhooks
- `GET /groups/:id/hooks` — list existing webhooks
- `POST /groups/:id/hooks` — create new webhook
- `PUT /groups/:id/hooks/:hook_id` — update existing webhook
- `DELETE /groups/:id/hooks/:hook_id` — remove webhook (cleanup)

---

## Algorithm

### High-Level Flow (Idempotent)

1. **Load Configuration**
   - Validate base URL and credentials
   - Parse root groups and webhook settings

2. **Auth Check**
   - Call `/user` to verify token works + scopes
   - Optional self-test

3. **Resolve Root Group IDs**
   - From paths if needed (`GET /groups?search=`)
   - Verify Owner access

4. **For Each Root Group**:
   
   **A. Ensure Token**:
   - If `auth_mode=group_token_per_root_group`:
     - `GET /groups/:id/access_tokens`
     - Search for non-expired token named `Qodo-Integration`
     - If not found, `POST /groups/:id/access_tokens` with `scopes=["api"]`
     - Record token value securely (only visible once)
   - If `auth_mode=bot_user_pat`:
     - Validate the PAT once
   
   **B. Traverse Subgroups**:
   - `GET /groups/:id/subgroups` (paginate)
   - Breadth-first traversal
   - Enqueue children
   
   **C. For Each Group (Root + Subgroups)**:
   - **Webhook Ensure**:
     - `GET /groups/:id/hooks`
     - Find hook with matching URL
     - If missing → `POST /groups/:id/hooks`
     - If present but mismatched → `PUT /groups/:id/hooks/:hook_id`

5. **Report**
   - Print JSON summary of created/updated/unchanged items

6. **Exit Codes**
   - 0 = success/idempotent
   - 2 = partial (some groups skipped)
   - 3 = auth/permission failure

### Pseudocode

```python
def ensure_group_token(group_id):
    if auth_mode == "bot_user_pat":
        return None  # PAT already set in header
    
    tokens = gitlab.get(f"/groups/{group_id}/access_tokens")
    tok = find_valid_token(tokens, name="Qodo-Integration", scopes=["api"])
    
    if tok:
        return None  # already have one; value not retrievable
    
    # Create new token (value returned once)
    payload = {
        "name": "Qodo-Integration",
        "scopes": ["api"],
        "access_level": 40  # maintainer+
    }
    created = gitlab.post(f"/groups/{group_id}/access_tokens", json=payload)
    secure_store(created["token"])  # value present here only once

def ensure_group_webhook(group_id, cfg):
    hooks = gitlab.get(f"/groups/{group_id}/hooks")
    hook = next((h for h in hooks if h["url"] == cfg.url), None)
    
    desired = {
        "url": cfg.url,
        "enable_ssl_verification": True,
        "token": cfg.secret,
        "merge_requests_events": True,
        "note_events": True,
        "pipeline_events": cfg.pipeline,
        "push_events": cfg.push,
    }
    
    if not hook:
        gitlab.post(f"/groups/{group_id}/hooks", json=desired)
    else:
        if not matches(hook, desired):
            gitlab.put(f"/groups/{group_id}/hooks/{hook['id']}", json=desired)

def traverse_groups(root_id):
    q = [root_id]
    seen = set()
    
    while q:
        gid = q.pop(0)
        if gid in seen:
            continue
        seen.add(gid)
        yield gid
        
        subs = paginate(f"/groups/{gid}/subgroups")
        q.extend([s["id"] for s in subs])
```

---

## Data Model

### Token State

```python
{
    "name": "Qodo-Integration",
    "scopes": ["api"],
    "expires_at": "2025-12-31",
    "revoked": false,
    "access_level": 40,
    "created_at": "2025-01-15T10:00:00Z"
}
```

**Considerations**:
- Auto-rotation window (e.g., rotate if expires within N days)
- Track creation date for audit

### Webhook State

```python
{
    "url": "https://qodo.company.com/webhooks/gitlab",
    "enable_ssl_verification": true,
    "push_events": true,
    "merge_requests_events": true,
    "note_events": true,
    "pipeline_events": true,
    "token": "webhook-secret"
}
```

**Comparison Logic**:
- Compare booleans strictly
- If any mismatch → update

---

## Edge Cases & Guardrails

### Permissions
- **Group webhooks require Owner** on each managed group
- Script should verify permissions before attempting operations

### GitLab Tiers
- **Group webhooks are Premium+**
- If on Free tier, detect 404 on group hooks API
- Optional fallback to per-project hooks

### Subgroup Traversal
- **Do not rely on a single "include_subgroups" flag**
- Implement recursive traversal with pagination
- Handle circular references (use `seen` set)

### Token One-Time Visibility
- On creation, token value is returned **once**
- Print/store securely immediately
- Later queries only show metadata, not value

### Custom CA
- If self-managed GitLab with custom CA:
  - Ensure script's HTTP client trusts it
  - Qodo docs mention sharing CA bundle for Qodo side

### Rate Limits
- Respect `Retry-After` header
- Implement exponential backoff
- Add configurable delay between API calls

### Idempotency
- **Never create duplicates**
- Always list & compare first
- Use deterministic naming (e.g., "Qodo-Integration")

---

## Security & Secrets

### Best Practices

1. **Never log token values**
   - Mask in logs and output
   - Only show token IDs or metadata

2. **Secure Storage Options**
   - Environment variable
   - HashiCorp Vault
   - AWS Secrets Manager
   - Local encrypted file (`age`/`sops`)

3. **Token Rotation**
   - Output both old token expiry and new token ID
   - Never output token value in rotation logs

4. **CLI Guards**
   - Optional `--print-token-once` flag
   - Prevent accidental CI logs
   - Require explicit confirmation for sensitive operations

### Secrets Handling

```python
def secure_store(token_value, group_id):
    """Store token securely based on configuration"""
    backend = config.get("secrets_backend", "env")
    
    if backend == "vault":
        vault_client.write(f"secret/qodo/gitlab/{group_id}", token=token_value)
    elif backend == "aws_sm":
        sm_client.put_secret_value(SecretId=f"qodo-gitlab-{group_id}", SecretString=token_value)
    elif backend == "env":
        print(f"QODO_GITLAB_TOKEN_{group_id}={token_value}")
    else:
        raise ValueError(f"Unknown secrets backend: {backend}")
```

---

## CLI Usage

### Basic Command

```bash
qodo-gitlab-install \
  --config ./config.yaml \
  --auth-mode group_token_per_root_group \
  --dry-run=false \
  --state ./state.json \
  --report ./report.json
```

### Environment Variables

**Option 1: Bootstrap Token**
```bash
export GITLAB_ADMIN_TOKEN="glpat-xxxxxxxxxxxx"
```

**Option 2: Bot PAT**
```bash
export GITLAB_BOT_PAT="glpat-xxxxxxxxxxxx"
```

### Examples

**Dry Run (No Changes)**
```bash
python qodo_gitlab_install.py --config config.yaml --dry-run
```

**Production Run**
```bash
python qodo_gitlab_install.py --config config.yaml
```

**Debug Mode**
```bash
python qodo_gitlab_install.py --config config.yaml --log-level debug
```

**With State Tracking**
```bash
python qodo_gitlab_install.py \
  --config config.yaml \
  --state ./state.json \
  --report ./report.json
```

---

## Testing

### Unit Tests

- **Comparison Logic**: Existing vs desired hook configuration
- **Recursion**: Subgroup traversal with cycles
- **Pagination**: Handling large result sets
- **Dry-Run**: No actual API calls made

### Integration Tests (Sandbox Group)

1. **Fresh Install**
   - Create from scratch
   - Verify webhooks & token exist
   - Check correct scopes and events

2. **Idempotency**
   - Run again
   - Verify no changes made

3. **Update Scenario**
   - Change events/secret in config
   - Run script
   - Verify updates applied

4. **Permission Failure**
   - Remove Owner on a subgroup
   - Verify graceful failure
   - Verify other groups continue

### Security Tests

- Confirm tokens never appear in logs
- Verify secret masking works
- Test token rotation without leaks

### Test Environment Requirements

1. Test GitLab group hierarchy:
   - Two levels of subgroups
   - A couple of projects per group

2. Qodo single-tenant webhook URL + recommended event list

3. Decision on token strategy (Option A vs B)

4. Secrets backend (Vault/AWS SM) for token storage

5. Non-prod GitLab user with Owner on test groups

---

## Acceptance Criteria

✅ **For each configured root group (and all subgroups)**:
- Exactly **one** webhook exists with correct URL, events, SSL, and secret
- Exactly **one** token strategy in place:
  - **Option A**: One group access token (scope `api`) per root group
  - **Option B**: A single bot PAT (scope `api`) managing all target groups

✅ **Re-running the script makes no changes** (idempotent)

✅ **Free tier fallback**: Script can create project-level hooks when group hooks unavailable

✅ **JSON report** lists all actions with clear failure explanations

✅ **Security**: No token values in logs, secure storage integration works

✅ **Error Handling**: Graceful degradation, clear error messages, appropriate exit codes

---

## Implementation Checklist

- [ ] Core script structure
- [ ] Configuration parsing (YAML)
- [ ] GitLab API client with auth
- [ ] Group traversal (recursive, paginated)
- [ ] Token management (create/verify)
- [ ] Webhook management (create/update)
- [ ] Idempotency checks
- [ ] Dry-run mode
- [ ] JSON reporting
- [ ] State file support
- [ ] Secrets backend integration
- [ ] Error handling & logging
- [ ] Rate limiting & backoff
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation (README.md)
- [ ] CLI argument parsing
- [ ] Exit codes

---

## References

- [GitLab Group Access Tokens API](https://docs.gitlab.com/ee/api/group_access_tokens.html)
- [GitLab Group Webhooks API](https://docs.gitlab.com/ee/api/groups.html#hooks)
- [GitLab Groups API](https://docs.gitlab.com/ee/api/groups.html)
- [Qodo Merge GitLab Integration](https://docs.qodo.ai/)
- [Qodo Aware Context Engine](https://docs.qodo.ai/)
