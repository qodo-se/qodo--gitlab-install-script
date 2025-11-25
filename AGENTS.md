# Qodo GitLab Integration Setup Script - Technical Documentation

## Table of Contents
1. [Goal & Scope](#goal--scope)
2. [Inputs & Outputs](#inputs--outputs)
3. [Token Strategy](#token-strategy)
4. [Webhook Strategy](#webhook-strategy)
5. [API Surface](#api-surface)
6. [Algorithm](#algorithm)
7. [Edge Cases & Guardrails](#edge-cases--guardrails)
8. [Security & Secrets](#security--secrets)

---

## Goal & Scope

### What the Script Does

1. **Processes** one or more specified GitLab root groups
2. **Creates** one group access token per root group with `api` scope
3. **Configures** group-level webhooks (idempotent create/update) for merge requests and comments
4. **Leverages** GitLab's group webhook inheritance (webhooks automatically apply to all subgroups and projects)
5. **Runs safely** every time (idempotent, retryable) and reports changes made

### Background

- **Qodo Merge** requires an access token with `api` scope and webhooks for MR events
- **Qodo Aware** requires read access to repositories for indexing
- **Implementation**: A single token with `api` scope covers both products (api scope includes read permissions)

---

## Inputs & Outputs

### Configuration File (`config.yaml`)

```yaml
# GitLab instance
gitlab_base_url: "https://gitlab.company.com"

# Authentication strategy (only group_token_per_root_group is supported)
auth_mode: "group_token_per_root_group"

# Root groups to manage (paths or IDs)
root_groups:
  - "engineering"
  - "product"

# Webhook configuration
webhooks:
  merge_request_url: "https://qodo.company.com/webhooks/gitlab"
  secret_token: "optional-auto-generated-if-omitted"

# Token expiration (days)
token_expires_in_days: 365

# Execution options
dry_run: false
log_level: "info"  # info or debug
```

### Outputs

**Console Output** containing:
- Tokens created (name, scope, expiration, **value shown once**)
- Webhooks created/updated (group path, URL, events)
- Auto-generated webhook secrets (shown once)
- Any errors or groups skipped

**Optional JSON Report** (`--report` flag):
- Structured summary of all operations
- Useful for auditing and automation

---

## Token Strategy

### Group Access Token per Root Group

- **Scope**: `api` (covers both Qodo Merge and Qodo Aware requirements)
- **Role**: Maintainer (40) - sufficient for token and webhook management
- **Coverage**: Works across all projects in the group hierarchy
- **Least Privilege**: Each root group has its own isolated token
- **Name**: "Qodo AI Integration" (used for idempotent detection)

**Why this approach:**
- Group tokens are scoped to their group hierarchy only
- `api` scope includes read_api and read_repository permissions
- Minimal blast radius if a token is compromised
- No need for dedicated bot user accounts

**Token Lifecycle:**
- Script checks for existing "Qodo AI Integration" token
- If found and not expired, reuses it (value not retrievable)
- If missing or expired, creates new token
- Token value displayed **once** during creation

---

## Webhook Strategy

### Group Webhooks

- Uses **Group Webhooks** (not system or project hooks)
- Applies to **all projects in the group and subgroups automatically**
- Requires **Owner** role on the group (script validates this)

### Configured Events

Current implementation enables:
- `merge_requests_events`: true (open/update/merge/close)
- `note_events`: true (comments on MRs)
- `push_events`: false (not required by Qodo)
- `pipeline_events`: false (not required by Qodo)

### Configuration

- `url`: Qodo webhook endpoint from configuration
- `token`: Auto-generated secure random secret (or user-provided)
- `enable_ssl_verification`: true
- `name`: "Qodo AI Integration"

### Idempotent Operations

1. List existing group webhooks
2. Find webhook with matching URL
3. If not found → create new webhook
4. If found but config differs → update webhook
5. If found and matches → no action

---

## API Surface

### Authentication
- Header: `PRIVATE-TOKEN: <token>`
- Supports group tokens and PATs

### Groups Traversal
- `GET /groups/:id/subgroups?per_page=100` — recursively walk the tree with pagination

### Group Access Tokens
- `GET /groups/:id/access_tokens` — find existing "Qodo AI Integration" token
- `POST /groups/:id/access_tokens` — create if missing
  - Parameters: `name`, `scopes`, `access_level`, `expires_at`

### Group Webhooks
- `GET /groups/:id/hooks` — list existing webhooks
- `POST /groups/:id/hooks` — create new webhook
- `PUT /groups/:id/hooks/:hook_id` — update existing webhook

---

## Algorithm

### High-Level Flow (Idempotent)

1. **Load Configuration**
   - Parse YAML configuration file
   - Validate required fields (base URL, root groups, webhook URL)
   - Auto-generate webhook secret if not provided

2. **Authentication Check**
   - Verify `GITLAB_ADMIN_TOKEN` environment variable
   - Call `/user` to validate token and check scopes
   - Verify token has `api` scope

3. **Resolve Root Group IDs**
   - Convert group paths to IDs if needed
   - Verify Owner access on each root group
   - Exit if insufficient permissions

4. **For Each Root Group**:
   
   **A. Ensure Group Token**:
   - `GET /groups/:id/access_tokens`
   - Search for non-expired token named "Qodo AI Integration"
   - If not found:
     - `POST /groups/:id/access_tokens` with `scopes=["api"]`, `access_level=40`
     - Display token value (only time it's visible)
     - Store token metadata for reporting
   - If found: Skip (value not retrievable)
   
   **B. Ensure Group Webhook**:
   - `GET /groups/:id/hooks`
   - Find hook with matching URL
   - Compare configuration (events, SSL, token)
   - If missing → `POST /groups/:id/hooks`
   - If mismatched → `PUT /groups/:id/hooks/:hook_id`
   - If matched → Skip
   - **Note**: Group webhooks automatically inherit to all subgroups and projects

5. **Report Results**
   - Console: Human-readable summary
   - Optional JSON file: Structured report
   - Display auto-generated secrets

6. **Exit Codes**
   - 0 = success (all groups processed)
   - 2 = partial (some groups skipped due to permissions)
   - 3 = authentication/permission failure

### Implementation Notes

**Token Management:**
- Tokens are created with expiration date (configurable, default 365 days)
- Token value is only available during creation response
- Script prints token value to console (user must save it)
- Subsequent runs detect existing token by name

**Webhook Management:**
- Webhooks are identified by URL (must be unique per group)
- Configuration comparison checks: URL, events, SSL verification, token
- Updates preserve webhook ID, only modify configuration

**Group Webhook Inheritance:**
- GitLab group webhooks automatically apply to all subgroups and projects
- No need to explicitly traverse and configure each subgroup
- Simplifies configuration and reduces API calls
- Ensures consistent webhook configuration across entire group hierarchy

---


---

## Edge Cases & Guardrails

### Permissions
- **Group webhooks require Owner role** on each managed group
- Script validates permissions before operations
- Fails gracefully if insufficient permissions on any group

### GitLab Tiers
- **Group webhooks require Premium+**
- Free tier will fail with 404 on group hooks API
- Script detects this and reports clear error message

### Group Webhook Inheritance
- GitLab group webhooks automatically inherit to all subgroups and projects
- Script only configures root groups
- Reduces API calls and configuration complexity
- Ensures consistent configuration across entire hierarchy

### Token One-Time Visibility
- Token value returned **only** during creation
- Script prints value to console immediately
- User must save token value (cannot be retrieved later)
- Subsequent runs detect token by name, not value

### Rate Limits
- Respects `Retry-After` header from GitLab API
- Implements exponential backoff (1s, 2s, 4s, 8s, 16s)
- Maximum 5 retry attempts per request

### Idempotency
- Always checks for existing resources before creating
- Uses deterministic naming: "Qodo AI Integration"
- Compares configuration before updating
- Safe to run multiple times

---

## Security & Secrets

### Token Security

1. **Token values are printed to console during creation**
   - User must save them immediately
   - Cannot be retrieved after creation
   - Consider redirecting output to secure file

2. **Bootstrap token via environment variable**
   - `GITLAB_ADMIN_TOKEN` must have Owner permissions
   - Never commit tokens to version control
   - Use `.gitignore` for any token files

3. **Webhook secrets**
   - Auto-generated using `secrets.token_urlsafe(32)`
   - Cryptographically secure random generation
   - Printed once during creation
   - User must configure Qodo with same secret

### Best Practices

1. **Token Lifecycle**
   - Set appropriate expiration (default 365 days)
   - Monitor expiration dates
   - Rotate before expiry by deleting old token and re-running script

2. **Dry Run First**
   - Always test with `--dry-run` before production
   - Verify configuration without making changes

3. **Audit Trail**
   - Use `--report` flag to generate JSON audit log
   - Store reports for compliance and troubleshooting

4. **Least Privilege**
   - Each root group gets its own token
   - Tokens scoped to group hierarchy only
   - Limits blast radius if compromised

---


---

## References

- [GitLab Group Access Tokens API](https://docs.gitlab.com/ee/api/group_access_tokens.html)
- [GitLab Group Webhooks API](https://docs.gitlab.com/ee/api/groups.html#hooks)
- [GitLab Groups API](https://docs.gitlab.com/ee/api/groups.html)
- [Qodo Merge GitLab Integration](https://docs.qodo.ai/)
- [Qodo Aware Context Engine](https://docs.qodo.ai/)
