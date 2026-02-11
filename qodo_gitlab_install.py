#!/usr/bin/env python3
"""
Qodo GitLab Integration Setup Script

Automates the configuration of GitLab groups for Qodo Merge and Qodo Aware integration.
See AGENTS.md for complete technical documentation.
"""

import argparse
import json
import logging
import os
import secrets
import sys
import time
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, quote

import requests
import yaml


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Webhook configuration"""
    merge_request_url: str
    secret_token: Optional[str]  # Auto-generated if not provided


@dataclass
class Config:
    """Main configuration"""
    gitlab_base_url: str
    auth_mode: str
    webhooks: WebhookConfig
    root_groups: List[str] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)
    dry_run: bool = False
    log_level: str = "info"
    token_expires_in_days: int = 365  # Default: 1 year


@dataclass
class ConfigurationSummary:
    """Summary of configuration values needed for Qodo setup"""
    group_id: int
    group_path: str
    group_access_token: Optional[str]  # Only available when newly created
    personal_access_token_used: bool
    webhook_secret: str
    webhook_secret_auto_generated: bool
    webhook_url: str


@dataclass
class ProjectConfigurationSummary:
    """Summary of configuration for an individual project"""
    project_id: int
    project_path: str
    project_access_token: Optional[str]
    webhook_secret: str
    webhook_url: str
    covered_by_group_webhook: bool


@dataclass
class CheckResult:
    """Result of a single validation check"""
    target: str           # e.g., "group:engineering" or "project:eng/backend/auth"
    target_type: str      # "group" or "project"
    check_name: str       # "exists", "permissions", "token_state", "webhook_state"
    status: str           # "pass", "warn", "fail"
    message: str


@dataclass
class ActionReport:
    """Report of actions taken"""
    tokens_created: List[Dict[str, Any]]
    tokens_verified: List[Dict[str, Any]]
    webhooks_created: List[Dict[str, Any]]
    webhooks_updated: List[Dict[str, Any]]
    webhooks_unchanged: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    groups_processed: int
    groups_skipped: int
    projects_processed: int
    projects_skipped: int
    configuration_summary: List[ConfigurationSummary]
    project_configuration_summary: List[ProjectConfigurationSummary]
    check_results: List[CheckResult]


class GitLabClient:
    """GitLab API client with rate limiting and error handling"""
    
    def __init__(self, base_url: str, token: str, dry_run: bool = False):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'PRIVATE-TOKEN': token,
            'Content-Type': 'application/json'
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make API request with retry logic"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', retry_delay))
                    logger.warning(f"Rate limited. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    # Log response body for debugging on final failure
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            logger.error(f"API Error Details: {json.dumps(error_detail, indent=2)}")
                        except:
                            logger.error(f"API Error Response: {e.response.text}")
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay * (2 ** attempt))
        
        raise Exception("Max retries exceeded")
    
    def get(self, endpoint: str, **kwargs) -> Any:
        """GET request"""
        response = self._request('GET', endpoint, **kwargs)
        return response.json() if response.content else None
    
    def post(self, endpoint: str, **kwargs) -> Any:
        """POST request"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would POST to {endpoint}")
            return {"dry_run": True}
        response = self._request('POST', endpoint, **kwargs)
        return response.json() if response.content else None
    
    def put(self, endpoint: str, **kwargs) -> Any:
        """PUT request"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would PUT to {endpoint}")
            return {"dry_run": True}
        response = self._request('PUT', endpoint, **kwargs)
        return response.json() if response.content else None
    
    def delete(self, endpoint: str, **kwargs) -> Any:
        """DELETE request"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would DELETE {endpoint}")
            return {"dry_run": True}
        response = self._request('DELETE', endpoint, **kwargs)
        return response.json() if response.content else None
    
    def paginate(self, endpoint: str, **kwargs) -> List[Any]:
        """Paginate through all results"""
        results = []
        page = 1
        per_page = 100
        
        while True:
            params = kwargs.get('params', {})
            params.update({'page': page, 'per_page': per_page})
            kwargs['params'] = params
            
            response = self._request('GET', endpoint, **kwargs)
            data = response.json()
            
            if not data:
                break
            
            results.extend(data)
            
            # Check if there are more pages
            if len(data) < per_page:
                break
            
            page += 1
        
        return results


class QodoGitLabInstaller:
    """Main installer class"""
    
    def __init__(self, config: Config, gitlab_token: str):
        self.config = config
        self.client = GitLabClient(config.gitlab_base_url, gitlab_token, config.dry_run)
        self.gitlab_token = gitlab_token  # Store for configuration summary
        
        # Auto-generate webhook secret if not provided
        self.webhook_secret_auto_generated = False
        if not self.config.webhooks.secret_token:
            self.config.webhooks.secret_token = self._generate_webhook_secret()
            self.webhook_secret_auto_generated = True
            logger.info("Auto-generated webhook secret (cryptographically secure)")
        
        self.report = ActionReport(
            tokens_created=[],
            tokens_verified=[],
            webhooks_created=[],
            webhooks_updated=[],
            webhooks_unchanged=[],
            errors=[],
            groups_processed=0,
            groups_skipped=0,
            projects_processed=0,
            projects_skipped=0,
            configuration_summary=[],
            project_configuration_summary=[],
            check_results=[]
        )
    
    def _generate_webhook_secret(self) -> str:
        """Generate a cryptographically secure webhook secret"""
        # Generate 32 bytes (256 bits) of random data, encoded as hex
        # This provides a strong secret for HMAC signature verification
        return secrets.token_hex(32)
    
    def verify_auth(self) -> bool:
        """Verify authentication and permissions"""
        try:
            user = self.client.get('/api/v4/user')
            logger.info(f"Authenticated as: {user.get('username')} ({user.get('name')})")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def resolve_group_id(self, group_path_or_id: str) -> Optional[int]:
        """Resolve group path to ID"""
        # If it's already an ID, return it
        if group_path_or_id.isdigit():
            return int(group_path_or_id)
        
        # Search for group by path
        try:
            groups = self.client.get('/api/v4/groups', params={'search': group_path_or_id})
            for group in groups:
                if group['full_path'] == group_path_or_id or group['path'] == group_path_or_id:
                    return group['id']
            
            logger.error(f"Group not found: {group_path_or_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to resolve group {group_path_or_id}: {e}")
            return None
    
    def traverse_groups(self, root_id: int) -> List[int]:
        """Recursively traverse all subgroups"""
        groups = []
        queue = [root_id]
        seen = set()
        
        while queue:
            gid = queue.pop(0)
            
            if gid in seen:
                continue
            
            seen.add(gid)
            groups.append(gid)
            
            try:
                subgroups = self.client.paginate(f'/api/v4/groups/{gid}/subgroups')
                queue.extend([sg['id'] for sg in subgroups])
            except Exception as e:
                logger.warning(f"Failed to get subgroups for {gid}: {e}")
        
        return groups
    
    def find_valid_token(self, tokens: List[Dict], name: str = "Qodo AI Integration") -> Optional[Dict]:
        """Find a valid, non-expired token"""
        for token in tokens:
            if token.get('name') == name and not token.get('revoked', False):
                # Check if expired
                expires_at = token.get('expires_at')
                if expires_at:
                    # Simple check - in production, parse and compare dates
                    logger.debug(f"Found token: {token.get('name')} (expires: {expires_at})")
                return token
        return None
    
    def ensure_group_token(self, group_id: int) -> Optional[str]:
        """Ensure group access token exists"""
        if self.config.auth_mode == "bot_user_pat":
            logger.debug(f"Using bot PAT for group {group_id}")
            return None
        
        try:
            # Get existing tokens
            tokens = self.client.get(f'/api/v4/groups/{group_id}/access_tokens')
            existing = self.find_valid_token(tokens)
            
            if existing:
                logger.info(f"Group {group_id}: Token already exists (ID: {existing['id']})")
                self.report.tokens_verified.append({
                    'group_id': group_id,
                    'token_id': existing['id'],
                    'token_name': existing['name']
                })
                return None
            
            # Create new token
            logger.info(f"Group {group_id}: Creating new token (expires in {self.config.token_expires_in_days} days)")
            
            # Calculate expiration date based on configured days
            from datetime import datetime, timedelta
            expires_at = (datetime.now() + timedelta(days=self.config.token_expires_in_days)).strftime('%Y-%m-%d')
            
            payload = {
                'name': 'Qodo AI Integration',
                'description': 'Qodo provides AI-powered code intelligence for merge requests and context-aware code indexing. This token enables Qodo Merge for MR reviews and Qodo Aware for repository analysis.',
                'scopes': ['api', 'read_repository'],
                'access_level': 40,  # Maintainer
                'expires_at': expires_at
            }
            
            created = self.client.post(f'/api/v4/groups/{group_id}/access_tokens', json=payload)
            
            if not self.config.dry_run:
                token_value = created.get('token')
                logger.warning(f"Group {group_id}: Token created - SAVE THIS VALUE (shown once only)")
                logger.warning(f"QODO_GITLAB_TOKEN_{group_id}={token_value}")
                
                self.report.tokens_created.append({
                    'group_id': group_id,
                    'token_id': created.get('id'),
                    'token_name': created.get('name'),
                    'token_value': token_value  # Only in report, not logs
                })
                
                return token_value
            
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                error_msg = e.response.json().get('message', str(e))
                if 'permission' in error_msg.lower():
                    logger.error(f"Group {group_id}: Insufficient permissions to create group access token")
                    logger.error(f"Group {group_id}: The authenticated user needs Owner role on this group")
                    logger.error(f"Group {group_id}: Please create the token manually or use a user with Owner permissions")
                    self.report.errors.append({
                        'group_id': group_id,
                        'operation': 'ensure_token',
                        'error': 'Insufficient permissions - Owner role required to create group access tokens',
                        'manual_action_required': True
                    })
                else:
                    logger.error(f"Group {group_id}: Failed to create token: {error_msg}")
                    self.report.errors.append({
                        'group_id': group_id,
                        'operation': 'ensure_token',
                        'error': error_msg
                    })
            else:
                logger.error(f"Group {group_id}: Failed to ensure token: {e}")
                self.report.errors.append({
                    'group_id': group_id,
                    'operation': 'ensure_token',
                    'error': str(e)
                })
            return None
        except Exception as e:
            logger.error(f"Group {group_id}: Failed to ensure token: {e}")
            self.report.errors.append({
                'group_id': group_id,
                'operation': 'ensure_token',
                'error': str(e)
            })
            return None
    
    def webhook_matches(self, existing: Dict, desired: Dict) -> bool:
        """Check if webhook matches desired configuration"""
        fields_to_check = [
            'url',
            'enable_ssl_verification',
            'push_events',
            'merge_requests_events',
            'note_events',
            'pipeline_events',
            'token'
        ]
        
        for field in fields_to_check:
            if existing.get(field) != desired.get(field):
                logger.debug(f"Webhook mismatch on {field}: {existing.get(field)} != {desired.get(field)}")
                return False
        
        return True
    
    def ensure_group_webhook(self, group_id: int) -> bool:
        """Ensure group webhook exists with correct configuration"""
        try:
            # Get existing hooks
            hooks = self.client.get(f'/api/v4/groups/{group_id}/hooks')
            
            # Build desired configuration with only merge_requests and note events enabled
            # Qodo Merge requires merge request and comment events for AI-powered code reviews
            desired = {
                'url': self.config.webhooks.merge_request_url,
                'enable_ssl_verification': True,
                'token': self.config.webhooks.secret_token,
                'push_events': False,
                'merge_requests_events': True,
                'note_events': True,
                'pipeline_events': False,
                'name': 'Qodo AI Integration',
                'description': 'Qodo provides AI-powered code intelligence for merge requests and context-aware code indexing. This webhook enables Qodo Merge for MR reviews and Qodo Aware for repository analysis.',
            }
            
            # Find existing hook with matching URL
            existing_hook = None
            for hook in hooks:
                if hook['url'] == desired['url']:
                    existing_hook = hook
                    break
            
            if not existing_hook:
                # Create new webhook
                logger.info(f"Group {group_id}: Creating webhook")
                created = self.client.post(f'/api/v4/groups/{group_id}/hooks', json=desired)
                
                self.report.webhooks_created.append({
                    'group_id': group_id,
                    'hook_id': created.get('id') if not self.config.dry_run else 'dry_run',
                    'url': desired['url']
                })
                return True
            
            # Check if update needed
            if not self.webhook_matches(existing_hook, desired):
                logger.info(f"Group {group_id}: Updating webhook {existing_hook['id']}")
                self.client.put(f'/api/v4/groups/{group_id}/hooks/{existing_hook["id"]}', json=desired)
                
                self.report.webhooks_updated.append({
                    'group_id': group_id,
                    'hook_id': existing_hook['id'],
                    'url': desired['url']
                })
                return True
            
            # No changes needed
            logger.debug(f"Group {group_id}: Webhook already configured correctly")
            self.report.webhooks_unchanged.append({
                'group_id': group_id,
                'hook_id': existing_hook['id'],
                'url': desired['url']
            })
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Group {group_id}: Group webhooks not available (Premium+ feature)")
                self.report.errors.append({
                    'group_id': group_id,
                    'operation': 'ensure_webhook',
                    'error': 'Group webhooks require GitLab Premium+'
                })
            else:
                logger.error(f"Group {group_id}: Failed to ensure webhook: {e}")
                self.report.errors.append({
                    'group_id': group_id,
                    'operation': 'ensure_webhook',
                    'error': str(e)
                })
            return False
        except Exception as e:
            logger.error(f"Group {group_id}: Failed to ensure webhook: {e}")
            self.report.errors.append({
                'group_id': group_id,
                'operation': 'ensure_webhook',
                'error': str(e)
            })
            return False
    
    def get_group_details(self, group_id: int) -> Optional[Dict]:
        """Get group details including path"""
        try:
            return self.client.get(f'/api/v4/groups/{group_id}')
        except Exception as e:
            logger.warning(f"Failed to get details for group {group_id}: {e}")
            return None
    
    def build_configuration_summary(self, group_id: int, group_token: Optional[str] = None):
        """Build configuration summary for a root group"""
        group_details = self.get_group_details(group_id)
        if not group_details:
            return
        
        # Determine which token to report
        using_pat = self.config.auth_mode == "bot_user_pat"
        
        summary = ConfigurationSummary(
            group_id=group_id,
            group_path=group_details.get('full_path', str(group_id)),
            group_access_token=group_token if not using_pat else None,
            personal_access_token_used=using_pat,
            webhook_secret=self.config.webhooks.secret_token,
            webhook_secret_auto_generated=self.webhook_secret_auto_generated,
            webhook_url=self.config.webhooks.merge_request_url
        )
        
        self.report.configuration_summary.append(summary)
    
    def resolve_project_id(self, project_path_or_id: str) -> Optional[int]:
        """Resolve project path or ID to numeric project ID"""
        if project_path_or_id.isdigit():
            return int(project_path_or_id)

        try:
            encoded_path = quote(project_path_or_id, safe='')
            project = self.client.get(f'/api/v4/projects/{encoded_path}')
            return project['id']
        except Exception as e:
            logger.error(f"Project not found: {project_path_or_id}: {e}")
            return None

    def find_covering_group(self, project_id: int, configured_group_ids: Set[int]) -> Optional[int]:
        """Check if a project is already covered by a configured group webhook"""
        try:
            project = self.client.get(f'/api/v4/projects/{project_id}')
            namespace = project.get('namespace', {})
            namespace_id = namespace.get('id')

            if namespace_id and namespace_id in configured_group_ids:
                return namespace_id

            # Walk up parent groups
            full_path = namespace.get('full_path', '')
            parts = full_path.split('/')
            for i in range(len(parts) - 1, 0, -1):
                parent_path = '/'.join(parts[:i])
                try:
                    encoded = quote(parent_path, safe='')
                    group = self.client.get(f'/api/v4/groups/{encoded}')
                    if group['id'] in configured_group_ids:
                        return group['id']
                except Exception:
                    continue

            return None
        except Exception as e:
            logger.warning(f"Failed to check group coverage for project {project_id}: {e}")
            return None

    def ensure_project_token(self, project_id: int) -> Optional[str]:
        """Ensure project access token exists"""
        if self.config.auth_mode == "bot_user_pat":
            logger.debug(f"Using bot PAT for project {project_id}")
            return None

        try:
            tokens = self.client.get(f'/api/v4/projects/{project_id}/access_tokens')
            existing = self.find_valid_token(tokens)

            if existing:
                logger.info(f"Project {project_id}: Token already exists (ID: {existing['id']})")
                self.report.tokens_verified.append({
                    'project_id': project_id,
                    'token_id': existing['id'],
                    'token_name': existing['name']
                })
                return None

            logger.info(f"Project {project_id}: Creating new token (expires in {self.config.token_expires_in_days} days)")

            from datetime import datetime, timedelta
            expires_at = (datetime.now() + timedelta(days=self.config.token_expires_in_days)).strftime('%Y-%m-%d')

            payload = {
                'name': 'Qodo AI Integration',
                'description': 'Qodo provides AI-powered code intelligence for merge requests and context-aware code indexing.',
                'scopes': ['api', 'read_repository'],
                'access_level': 40,  # Maintainer
                'expires_at': expires_at
            }

            created = self.client.post(f'/api/v4/projects/{project_id}/access_tokens', json=payload)

            if not self.config.dry_run:
                token_value = created.get('token')
                logger.warning(f"Project {project_id}: Token created - SAVE THIS VALUE (shown once only)")
                logger.warning(f"QODO_GITLAB_TOKEN_PROJECT_{project_id}={token_value}")

                self.report.tokens_created.append({
                    'project_id': project_id,
                    'token_id': created.get('id'),
                    'token_name': created.get('name'),
                    'token_value': token_value
                })

                return token_value

            return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                error_msg = e.response.json().get('message', str(e))
                if 'permission' in error_msg.lower():
                    logger.error(f"Project {project_id}: Insufficient permissions to create project access token")
                    logger.error(f"Project {project_id}: The authenticated user needs Maintainer+ role on this project")
                    self.report.errors.append({
                        'project_id': project_id,
                        'operation': 'ensure_project_token',
                        'error': 'Insufficient permissions - Maintainer+ role required',
                        'manual_action_required': True
                    })
                else:
                    logger.error(f"Project {project_id}: Failed to create token: {error_msg}")
                    self.report.errors.append({
                        'project_id': project_id,
                        'operation': 'ensure_project_token',
                        'error': error_msg
                    })
            else:
                logger.error(f"Project {project_id}: Failed to ensure token: {e}")
                self.report.errors.append({
                    'project_id': project_id,
                    'operation': 'ensure_project_token',
                    'error': str(e)
                })
            return None
        except Exception as e:
            logger.error(f"Project {project_id}: Failed to ensure token: {e}")
            self.report.errors.append({
                'project_id': project_id,
                'operation': 'ensure_project_token',
                'error': str(e)
            })
            return None

    def ensure_project_webhook(self, project_id: int) -> bool:
        """Ensure project webhook exists with correct configuration"""
        try:
            hooks = self.client.get(f'/api/v4/projects/{project_id}/hooks')

            desired = {
                'url': self.config.webhooks.merge_request_url,
                'enable_ssl_verification': True,
                'token': self.config.webhooks.secret_token,
                'push_events': False,
                'merge_requests_events': True,
                'note_events': True,
                'pipeline_events': False,
                'name': 'Qodo AI Integration',
            }

            existing_hook = None
            for hook in hooks:
                if hook['url'] == desired['url']:
                    existing_hook = hook
                    break

            if not existing_hook:
                logger.info(f"Project {project_id}: Creating webhook")
                created = self.client.post(f'/api/v4/projects/{project_id}/hooks', json=desired)

                self.report.webhooks_created.append({
                    'project_id': project_id,
                    'hook_id': created.get('id') if not self.config.dry_run else 'dry_run',
                    'url': desired['url']
                })
                return True

            if not self.webhook_matches(existing_hook, desired):
                logger.info(f"Project {project_id}: Updating webhook {existing_hook['id']}")
                self.client.put(f'/api/v4/projects/{project_id}/hooks/{existing_hook["id"]}', json=desired)

                self.report.webhooks_updated.append({
                    'project_id': project_id,
                    'hook_id': existing_hook['id'],
                    'url': desired['url']
                })
                return True

            logger.debug(f"Project {project_id}: Webhook already configured correctly")
            self.report.webhooks_unchanged.append({
                'project_id': project_id,
                'hook_id': existing_hook['id'],
                'url': desired['url']
            })
            return True

        except Exception as e:
            logger.error(f"Project {project_id}: Failed to ensure webhook: {e}")
            self.report.errors.append({
                'project_id': project_id,
                'operation': 'ensure_project_webhook',
                'error': str(e)
            })
            return False

    def get_project_details(self, project_id: int) -> Optional[Dict]:
        """Get project details including path"""
        try:
            return self.client.get(f'/api/v4/projects/{project_id}')
        except Exception as e:
            logger.warning(f"Failed to get details for project {project_id}: {e}")
            return None

    def build_project_configuration_summary(self, project_id: int, project_token: Optional[str] = None, covered_by_group: bool = False):
        """Build configuration summary for a project"""
        project_details = self.get_project_details(project_id)
        if not project_details:
            return

        summary = ProjectConfigurationSummary(
            project_id=project_id,
            project_path=project_details.get('path_with_namespace', str(project_id)),
            project_access_token=project_token,
            webhook_secret=self.config.webhooks.secret_token,
            webhook_url=self.config.webhooks.merge_request_url,
            covered_by_group_webhook=covered_by_group
        )

        self.report.project_configuration_summary.append(summary)

    def process_project(self, project_path_or_id: str, configured_group_ids: Set[int]):
        """Process a single project: resolve, check coverage, create token + webhook"""
        logger.info(f"Processing project: {project_path_or_id}")

        project_id = self.resolve_project_id(project_path_or_id)
        if not project_id:
            self.report.projects_skipped += 1
            self.report.errors.append({
                'project': project_path_or_id,
                'operation': 'resolve_project',
                'error': f'Could not resolve project: {project_path_or_id}'
            })
            return

        # Check if already covered by a group webhook
        covered_by_group = False
        covering_group = self.find_covering_group(project_id, configured_group_ids)
        if covering_group:
            covered_by_group = True
            logger.warning(
                f"Project {project_path_or_id}: Already covered by group webhook (group ID: {covering_group}). "
                "Project-level token and webhook will still be created."
            )

        try:
            # Create project token
            created_token = self.ensure_project_token(project_id)

            # Create project webhook
            webhook_ok = self.ensure_project_webhook(project_id)

            if webhook_ok:
                self.build_project_configuration_summary(project_id, created_token, covered_by_group)
                self.report.projects_processed += 1
            else:
                self.report.projects_skipped += 1

        except Exception as e:
            logger.error(f"Project {project_path_or_id}: Processing failed: {e}")
            self.report.projects_skipped += 1
            self.report.errors.append({
                'project': project_path_or_id,
                'operation': 'process_project',
                'error': str(e)
            })

    def process_group(self, group_id: int, is_root: bool = False) -> bool:
        """Process a single group (webhooks only, tokens handled separately for root groups)"""
        logger.info(f"Processing group {group_id}")
        
        try:
            # Ensure webhook
            webhook_ok = self.ensure_group_webhook(group_id)
            
            self.report.groups_processed += 1
            return webhook_ok
            
        except Exception as e:
            logger.error(f"Group {group_id}: Processing failed: {e}")
            self.report.groups_skipped += 1
            self.report.errors.append({
                'group_id': group_id,
                'operation': 'process_group',
                'error': str(e)
            })
            return False
    
    def run_checks(self) -> List[CheckResult]:
        """Validate configuration without making changes"""
        results: List[CheckResult] = []

        # Verify auth
        try:
            user = self.client.get('/api/v4/user')
            results.append(CheckResult(
                target="auth",
                target_type="auth",
                check_name="authentication",
                status="pass",
                message=f"Authenticated as {user.get('username')}"
            ))
        except Exception as e:
            results.append(CheckResult(
                target="auth",
                target_type="auth",
                check_name="authentication",
                status="fail",
                message=f"Authentication failed: {e}"
            ))
            return results

        # Check groups
        for group_entry in self.config.root_groups:
            target = f"group:{group_entry}"

            group_id = self.resolve_group_id(group_entry)
            if not group_id:
                results.append(CheckResult(
                    target=target, target_type="group",
                    check_name="exists", status="fail",
                    message=f"Group not found: {group_entry}"
                ))
                continue

            results.append(CheckResult(
                target=target, target_type="group",
                check_name="exists", status="pass",
                message=f"Group ID: {group_id}"
            ))

            # Check permissions (can we list tokens?)
            try:
                self.client.get(f'/api/v4/groups/{group_id}/access_tokens')
                results.append(CheckResult(
                    target=target, target_type="group",
                    check_name="permissions", status="pass",
                    message="Can list access tokens"
                ))
            except Exception:
                results.append(CheckResult(
                    target=target, target_type="group",
                    check_name="permissions", status="fail",
                    message="Cannot list access tokens (Owner role required)"
                ))

            # Check token state
            try:
                tokens = self.client.get(f'/api/v4/groups/{group_id}/access_tokens')
                existing = self.find_valid_token(tokens)
                if existing:
                    results.append(CheckResult(
                        target=target, target_type="group",
                        check_name="token_state", status="pass",
                        message=f"Token exists (ID: {existing['id']}, expires: {existing.get('expires_at', 'unknown')})"
                    ))
                else:
                    results.append(CheckResult(
                        target=target, target_type="group",
                        check_name="token_state", status="warn",
                        message="No token found (will be created on run)"
                    ))
            except Exception:
                pass  # Already covered by permissions check

            # Check webhook state
            try:
                hooks = self.client.get(f'/api/v4/groups/{group_id}/hooks')
                matching = [h for h in hooks if h['url'] == self.config.webhooks.merge_request_url]
                if matching:
                    results.append(CheckResult(
                        target=target, target_type="group",
                        check_name="webhook_state", status="pass",
                        message=f"Webhook exists (ID: {matching[0]['id']})"
                    ))
                else:
                    results.append(CheckResult(
                        target=target, target_type="group",
                        check_name="webhook_state", status="warn",
                        message="No webhook found (will be created on run)"
                    ))
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    results.append(CheckResult(
                        target=target, target_type="group",
                        check_name="webhook_state", status="fail",
                        message="Group webhooks not available (Premium+ required)"
                    ))
                else:
                    results.append(CheckResult(
                        target=target, target_type="group",
                        check_name="webhook_state", status="fail",
                        message=f"Failed to check webhooks: {e}"
                    ))
            except Exception as e:
                results.append(CheckResult(
                    target=target, target_type="group",
                    check_name="webhook_state", status="fail",
                    message=f"Failed to check webhooks: {e}"
                ))

        # Collect configured group IDs for coverage check
        configured_group_ids: Set[int] = set()
        for group_entry in self.config.root_groups:
            gid = self.resolve_group_id(group_entry)
            if gid:
                configured_group_ids.add(gid)

        # Check projects
        for project_entry in self.config.projects:
            target = f"project:{project_entry}"

            project_id = self.resolve_project_id(project_entry)
            if not project_id:
                results.append(CheckResult(
                    target=target, target_type="project",
                    check_name="exists", status="fail",
                    message=f"Project not found: {project_entry}"
                ))
                continue

            results.append(CheckResult(
                target=target, target_type="project",
                check_name="exists", status="pass",
                message=f"Project ID: {project_id}"
            ))

            # Check group coverage
            covering_group = self.find_covering_group(project_id, configured_group_ids)
            if covering_group:
                results.append(CheckResult(
                    target=target, target_type="project",
                    check_name="coverage", status="warn",
                    message=f"Covered by group webhook (group ID: {covering_group})"
                ))

            # Check permissions
            try:
                self.client.get(f'/api/v4/projects/{project_id}/access_tokens')
                results.append(CheckResult(
                    target=target, target_type="project",
                    check_name="permissions", status="pass",
                    message="Can list access tokens"
                ))
            except Exception:
                results.append(CheckResult(
                    target=target, target_type="project",
                    check_name="permissions", status="fail",
                    message="Cannot list access tokens (Maintainer+ role required)"
                ))

            # Check token state
            try:
                tokens = self.client.get(f'/api/v4/projects/{project_id}/access_tokens')
                existing = self.find_valid_token(tokens)
                if existing:
                    results.append(CheckResult(
                        target=target, target_type="project",
                        check_name="token_state", status="pass",
                        message=f"Token exists (ID: {existing['id']}, expires: {existing.get('expires_at', 'unknown')})"
                    ))
                else:
                    results.append(CheckResult(
                        target=target, target_type="project",
                        check_name="token_state", status="warn",
                        message="No token found (will be created on run)"
                    ))
            except Exception:
                pass

            # Check webhook state
            try:
                hooks = self.client.get(f'/api/v4/projects/{project_id}/hooks')
                matching = [h for h in hooks if h['url'] == self.config.webhooks.merge_request_url]
                if matching:
                    results.append(CheckResult(
                        target=target, target_type="project",
                        check_name="webhook_state", status="pass",
                        message=f"Webhook exists (ID: {matching[0]['id']})"
                    ))
                else:
                    results.append(CheckResult(
                        target=target, target_type="project",
                        check_name="webhook_state", status="warn",
                        message="No webhook found (will be created on run)"
                    ))
            except Exception as e:
                results.append(CheckResult(
                    target=target, target_type="project",
                    check_name="webhook_state", status="fail",
                    message=f"Failed to check webhooks: {e}"
                ))

        return results

    def print_check_report(self, results: List[CheckResult]):
        """Print formatted check results table"""
        print("\n")
        print("=" * 80)
        print("CONFIGURATION CHECK RESULTS")
        print("=" * 80)
        print()
        print(f"{'Status':<8}{'Target':<35}{'Check':<18}{'Details'}")
        print(f"{'------':<8}{'------':<35}{'-----':<18}{'-------'}")

        for r in results:
            status_display = r.status.upper()
            print(f"{status_display:<8}{r.target:<35}{r.check_name:<18}{r.message}")

        print()
        passes = sum(1 for r in results if r.status == "pass")
        warns = sum(1 for r in results if r.status == "warn")
        fails = sum(1 for r in results if r.status == "fail")
        print(f"Total: {passes} passed, {warns} warnings, {fails} failed")
        print("=" * 80)

    def run(self) -> int:
        """Main execution flow"""
        logger.info("Starting Qodo GitLab integration setup")

        # Verify authentication
        if not self.verify_auth():
            return 3

        # Phase 1: Process each root group (ONLY the specified groups, no subgroups)
        configured_group_ids: Set[int] = set()
        for root_group in self.config.root_groups:
            logger.info(f"Processing root group: {root_group}")

            # Resolve group ID
            group_id = self.resolve_group_id(root_group)
            if not group_id:
                self.report.groups_skipped += 1
                continue

            configured_group_ids.add(group_id)

            # Ensure token for root group and capture the token value
            created_token = None
            if self.config.auth_mode == "group_token_per_root_group":
                created_token = self.ensure_group_token(group_id)

            # Build configuration summary for this root group
            self.build_configuration_summary(group_id, created_token)

            # Process ONLY this root group (no subgroup traversal)
            self.process_group(group_id, is_root=True)

        # Phase 2: Process individual projects
        if self.config.projects:
            logger.info("Processing individual projects")
            for project_entry in self.config.projects:
                self.process_project(project_entry, configured_group_ids)

        # Print report
        self.print_report()

        # Determine exit code
        total_processed = self.report.groups_processed + self.report.projects_processed
        if self.report.errors:
            if total_processed > 0:
                return 2  # Partial success
            else:
                return 3  # Complete failure

        return 0  # Success
    
    def print_report(self):
        """Print final report"""
        print("\n")
        print("=" * 80)
        print("QODO CONFIGURATION SUMMARY")
        print("=" * 80)
        print("\nProvide the following information to complete your Qodo setup:\n")
        
        # Print configuration summary for each root group
        for idx, summary in enumerate(self.report.configuration_summary, 1):
            print(f"--- Root Group {idx}: {summary.group_path} ---")
            print(f"  Group ID:          {summary.group_id}")
            
            if summary.personal_access_token_used:
                print(f"  Access Token:      Using Personal Access Token (from environment)")
                print(f"                     Value: {self.gitlab_token[:8]}...{self.gitlab_token[-4:]}")
                print(f"                     Scopes: api, read_repository")
            elif summary.group_access_token:
                print(f"  Group Access Token: {summary.group_access_token}")
                print(f"                     ⚠️  SAVE THIS - shown only once!")
                print(f"                     Scopes: api, read_repository")
            else:
                print(f"  Group Access Token: Already exists (not shown)")
                print(f"                     Scopes: api, read_repository")
            
            print(f"  Webhook URL:       {summary.webhook_url}")
            print(f"  Webhook Secret:    {summary.webhook_secret}")
            if summary.webhook_secret_auto_generated:
                print(f"                     ⚠️  AUTO-GENERATED - SAVE THIS!")
            print()
        
        # Print project configuration summary
        for idx, summary in enumerate(self.report.project_configuration_summary, 1):
            print(f"--- Project {idx}: {summary.project_path} ---")
            print(f"  Project ID:        {summary.project_id}")

            if summary.covered_by_group_webhook:
                print(f"  Group Coverage:    Covered by group webhook (project webhook also configured)")

            if summary.project_access_token:
                print(f"  Project Token:     {summary.project_access_token}")
                print(f"                     ⚠️  SAVE THIS - shown only once!")
            else:
                print(f"  Project Token:     Already exists (not shown)")

            print(f"  Webhook URL:       {summary.webhook_url}")
            print(f"  Webhook Secret:    {summary.webhook_secret}")
            if self.webhook_secret_auto_generated:
                print(f"                     ⚠️  AUTO-GENERATED - SAVE THIS!")
            print()

        print("=" * 80)
        print()

        # Print summary statistics
        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Groups processed: {self.report.groups_processed}")
        logger.info(f"Groups skipped: {self.report.groups_skipped}")
        logger.info(f"Projects processed: {self.report.projects_processed}")
        logger.info(f"Projects skipped: {self.report.projects_skipped}")
        logger.info(f"Tokens created: {len(self.report.tokens_created)}")
        logger.info(f"Tokens verified: {len(self.report.tokens_verified)}")
        logger.info(f"Webhooks created: {len(self.report.webhooks_created)}")
        logger.info(f"Webhooks updated: {len(self.report.webhooks_updated)}")
        logger.info(f"Webhooks unchanged: {len(self.report.webhooks_unchanged)}")
        logger.info(f"Errors: {len(self.report.errors)}")
        logger.info("=" * 80)


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    webhook_config = WebhookConfig(
        merge_request_url=data['webhooks']['merge_request_url'],
        secret_token=data['webhooks'].get('secret_token')  # Optional - auto-generated if not provided
    )

    root_groups = data.get('root_groups') or []
    projects = data.get('projects') or []

    if not isinstance(root_groups, list):
        raise ValueError("'root_groups' must be a list")
    if not isinstance(projects, list):
        raise ValueError("'projects' must be a list")

    root_groups = [str(x) for x in root_groups]
    projects = [str(x) for x in projects]

    if not root_groups and not projects:
        raise ValueError("Configuration must specify at least one of 'root_groups' or 'projects'")

    return Config(
        gitlab_base_url=data['gitlab_base_url'],
        auth_mode=data['auth_mode'],
        webhooks=webhook_config,
        root_groups=root_groups,
        projects=projects,
        dry_run=data.get('dry_run', False),
        log_level=data.get('log_level', 'info'),
        token_expires_in_days=data.get('token_expires_in_days', 365)
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Qodo GitLab Integration Setup Script',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        required=True,
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform dry run (no changes made)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error'],
        default='info',
        help='Logging level'
    )
    
    parser.add_argument(
        '--state',
        help='Path to state file (for tracking changes)'
    )
    
    parser.add_argument(
        '--report',
        help='Path to save JSON report'
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='Validate configuration without making changes'
    )

    args = parser.parse_args()
    
    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 3
    
    # Override with CLI args
    if args.dry_run:
        config.dry_run = True
    if args.log_level:
        config.log_level = args.log_level
    
    # Get GitLab token from environment
    gitlab_token = os.environ.get('GITLAB_ADMIN_TOKEN') or os.environ.get('GITLAB_BOT_PAT')
    if not gitlab_token:
        logger.error("GitLab token not found. Set GITLAB_ADMIN_TOKEN or GITLAB_BOT_PAT environment variable.")
        return 3
    
    # Run installer
    installer = QodoGitLabInstaller(config, gitlab_token)

    if args.check:
        # Check mode: validate without making changes
        results = installer.run_checks()
        installer.print_check_report(results)
        installer.report.check_results = results

        # Save report if requested
        if args.report:
            report_dict = asdict(installer.report)
            with open(args.report, 'w') as f:
                json.dump(report_dict, f, indent=2)
            logger.info(f"Report saved to {args.report}")

        has_failures = any(r.status == "fail" for r in results)
        return 1 if has_failures else 0

    exit_code = installer.run()

    # Save report if requested
    if args.report:
        report_dict = asdict(installer.report)
        with open(args.report, 'w') as f:
            json.dump(report_dict, f, indent=2)
        logger.info(f"Report saved to {args.report}")

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
