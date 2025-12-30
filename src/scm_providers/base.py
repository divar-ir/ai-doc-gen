"""
Abstract base class for SCM (Source Code Management) providers.

This module defines provider-agnostic interfaces for interacting with
different SCM systems like GitLab and Bitbucket Server.

Terminology mapping:
- Repository: GitLab calls these "projects", Bitbucket calls them "repositories"
- Pull Request: GitLab calls these "merge requests", Bitbucket calls them "pull requests"
- Group/Namespace: GitLab uses "groups", Bitbucket uses "projects" (containers for repos)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class Branch:
    """Provider-agnostic representation of a branch."""

    name: str
    commit_sha: str
    commit_message: str
    committed_at: Optional[datetime] = None


@dataclass
class Repository:
    """
    Provider-agnostic representation of a repository.

    Note: GitLab calls these "projects", Bitbucket calls them "repositories".
    We use the term "repository" as it's more universally understood.
    """

    id: str  # Unique identifier (GitLab: project ID, Bitbucket: project_key/repo_slug)
    name: str
    full_path: str  # Full path including namespace/group
    clone_url: str  # HTTP URL for cloning
    default_branch: str
    archived: bool = False
    namespace: str = ""  # GitLab group path or Bitbucket project key

    # Provider-specific raw object for advanced operations
    _raw: Optional[object] = None


@dataclass
class PullRequest:
    """
    Provider-agnostic representation of a pull request.

    Note: GitLab calls these "merge requests", Bitbucket calls them "pull requests".
    We use "pull request" as it's more common in the industry.
    """

    id: str
    title: str
    source_branch: str
    target_branch: str
    web_url: str
    state: str  # open, closed, merged


class SCMProvider(ABC):
    """
    Abstract base class for SCM providers.

    Implementations should handle provider-specific authentication and API calls
    while exposing a unified interface for common operations.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the SCM provider (e.g., 'gitlab', 'bitbucket_server')."""
        pass

    @abstractmethod
    def list_repositories(
        self,
        namespace_id: Optional[str] = None,
        include_subgroups: bool = True,
    ) -> Iterator[Repository]:
        """
        List repositories accessible to the authenticated user.

        Args:
            namespace_id: Optional namespace/group/project key to filter repositories.
                         For GitLab: group ID. For Bitbucket: project key.
            include_subgroups: Whether to include repositories from subgroups/sub-projects.

        Yields:
            Repository objects.
        """
        pass

    @abstractmethod
    def get_repository(self, repo_id: str) -> Repository:
        """
        Get a single repository by its identifier.

        Args:
            repo_id: Repository identifier.
                    For GitLab: project ID.
                    For Bitbucket: "project_key/repo_slug" format.

        Returns:
            Repository object.
        """
        pass

    @abstractmethod
    def get_default_branch(self, repo: Repository) -> Branch:
        """
        Get the default branch of a repository.

        Args:
            repo: Repository object.

        Returns:
            Branch object for the default branch.
        """
        pass

    @abstractmethod
    def branch_exists(self, repo: Repository, branch_name: str) -> bool:
        """
        Check if a branch exists in the repository.

        Args:
            repo: Repository object.
            branch_name: Name of the branch to check.

        Returns:
            True if branch exists, False otherwise.
        """
        pass

    @abstractmethod
    def list_open_pull_requests(
        self,
        repo: Repository,
        author: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[PullRequest]:
        """
        List open pull requests for a repository.

        Args:
            repo: Repository object.
            author: Optional filter by author username.
            search: Optional search string in PR title.

        Returns:
            List of PullRequest objects.
        """
        pass

    @abstractmethod
    def create_pull_request(
        self,
        repo: Repository,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> PullRequest:
        """
        Create a new pull request.

        Args:
            repo: Repository object.
            source_branch: Source branch name.
            target_branch: Target branch name.
            title: Pull request title.
            description: Pull request description.

        Returns:
            Created PullRequest object.
        """
        pass

    @abstractmethod
    def configure_git_credentials(self, repo_path: Path) -> None:
        """
        Configure git credentials for pushing to the repository.

        This may set up credential helpers, configure remote URLs with tokens, etc.

        Args:
            repo_path: Path to the local git repository.
        """
        pass

    @abstractmethod
    def get_authenticated_clone_url(self, repo: Repository) -> str:
        """
        Get the clone URL with embedded authentication.

        Args:
            repo: Repository object.

        Returns:
            Clone URL with authentication (e.g., https://token@host/repo.git).
        """
        pass

    def is_namespace_ignored(self, repo: Repository, ignored_namespaces: list[str]) -> bool:
        """
        Check if repository is in an ignored namespace.

        Args:
            repo: Repository object.
            ignored_namespaces: List of namespace names to ignore.

        Returns:
            True if repository is in an ignored namespace.
        """
        namespace_parts = repo.namespace.lower().split("/")
        for ignored in ignored_namespaces:
            if ignored.lower() in namespace_parts:
                return True
        return False
