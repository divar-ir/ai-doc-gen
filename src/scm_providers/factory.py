"""
SCM Provider Factory.

This module provides a factory function for creating SCM provider instances
based on configuration (environment variables).
"""

from enum import Enum
from typing import Optional

from .base import SCMProvider
from .bitbucket_server_provider import BitbucketServerProvider
from .gitlab_provider import GitLabProvider


class SCMProviderType(str, Enum):
    """Supported SCM provider types."""

    GITLAB = "gitlab"
    BITBUCKET_SERVER = "bitbucket_server"


def create_scm_provider(
    provider_type: SCMProviderType,
    # Common settings
    url: str,
    git_username: Optional[str] = None,
    git_email: Optional[str] = None,
    # GitLab-specific
    gitlab_oauth_token: Optional[str] = None,
    gitlab_private_token: Optional[str] = None,
    # Bitbucket-specific
    bitbucket_username: Optional[str] = None,
    bitbucket_password: Optional[str] = None,
    bitbucket_token: Optional[str] = None,
) -> SCMProvider:
    """
    Create an SCM provider instance based on the provider type.

    Args:
        provider_type: Type of SCM provider to create.
        url: SCM server URL.
        git_username: Username for git commits.
        git_email: Email for git commits.
        gitlab_oauth_token: GitLab OAuth token.
        gitlab_private_token: GitLab private token.
        bitbucket_username: Bitbucket username (for basic auth).
        bitbucket_password: Bitbucket password (for basic auth).
        bitbucket_token: Bitbucket personal access token.

    Returns:
        SCMProvider instance.

    Raises:
        ValueError: If provider_type is not supported or required credentials are missing.
    """
    if provider_type == SCMProviderType.GITLAB:
        if not gitlab_oauth_token and not gitlab_private_token:
            raise ValueError("GitLab provider requires either GITLAB_OAUTH_TOKEN or GITLAB_PRIVATE_TOKEN")
        return GitLabProvider(
            url=url,
            oauth_token=gitlab_oauth_token,
            private_token=gitlab_private_token,
            username=git_username,
            email=git_email,
        )

    elif provider_type == SCMProviderType.BITBUCKET_SERVER:
        if not bitbucket_token and not (bitbucket_username and bitbucket_password):
            raise ValueError(
                "Bitbucket Server provider requires either BITBUCKET_TOKEN or "
                "both BITBUCKET_USERNAME and BITBUCKET_PASSWORD"
            )
        return BitbucketServerProvider(
            url=url,
            username=bitbucket_username,
            password=bitbucket_password,
            token=bitbucket_token,
            git_username=git_username,
            git_email=git_email,
        )

    else:
        raise ValueError(f"Unsupported SCM provider type: {provider_type}")


def create_scm_provider_from_config() -> SCMProvider:
    """
    Create an SCM provider instance from environment configuration.

    Reads configuration from the config module and creates the appropriate
    provider instance.

    Returns:
        SCMProvider instance.

    Raises:
        ValueError: If SCM_PROVIDER is not set or not supported.
    """
    import config

    provider_type_str = config.SCM_PROVIDER.lower()

    try:
        provider_type = SCMProviderType(provider_type_str)
    except ValueError:
        raise ValueError(
            f"Unsupported SCM provider: {provider_type_str}. "
            f"Supported providers: {', '.join(t.value for t in SCMProviderType)}"
        )

    if provider_type == SCMProviderType.GITLAB:
        return create_scm_provider(
            provider_type=provider_type,
            url=config.SCM_API_URL,
            git_username=config.SCM_GIT_USER_NAME,
            git_email=config.SCM_GIT_USER_EMAIL,
            gitlab_oauth_token=config.GITLAB_OAUTH_TOKEN,
            gitlab_private_token=config.GITLAB_PRIVATE_TOKEN,
        )

    elif provider_type == SCMProviderType.BITBUCKET_SERVER:
        return create_scm_provider(
            provider_type=provider_type,
            url=config.SCM_API_URL,
            git_username=config.SCM_GIT_USER_NAME,
            git_email=config.SCM_GIT_USER_EMAIL,
            bitbucket_username=config.BITBUCKET_USERNAME,
            bitbucket_password=config.BITBUCKET_PASSWORD,
            bitbucket_token=config.BITBUCKET_TOKEN,
        )

    raise ValueError(f"Unsupported SCM provider: {provider_type}")
