"""
GitLab SCM provider implementation.

This module provides a GitLab-specific implementation of the SCMProvider interface,
wrapping the python-gitlab library.
"""

from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

from gitlab import Gitlab
from gitlab.v4.objects.branches import ProjectBranch
from gitlab.v4.objects.projects import Project

from .base import Branch, PullRequest, Repository, SCMProvider


class GitLabProvider(SCMProvider):
    """
    GitLab implementation of the SCM provider interface.

    Terminology mapping:
    - Repository → GitLab "Project"
    - Pull Request → GitLab "Merge Request"
    - Namespace → GitLab "Group"
    """

    def __init__(
        self,
        url: str,
        oauth_token: Optional[str] = None,
        private_token: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ):
        """
        Initialize GitLab provider.

        Args:
            url: GitLab instance URL.
            oauth_token: OAuth token for authentication.
            private_token: Private token for authentication (alternative to oauth_token).
            username: Git username for commits.
            email: Git email for commits.
        """
        self._url = url
        self._oauth_token = oauth_token
        self._private_token = private_token
        self._username = username or "AI Analyzer"
        self._email = email

        self._client = Gitlab(
            url=url,
            oauth_token=oauth_token,
            private_token=private_token,
        )

    @property
    def provider_name(self) -> str:
        return "gitlab"

    @property
    def git_username(self) -> str:
        return self._username

    @property
    def git_email(self) -> Optional[str]:
        return self._email

    def _project_to_repository(self, project: Project) -> Repository:
        """Convert GitLab Project to provider-agnostic Repository."""
        return Repository(
            id=str(project.get_id()),
            name=project.name,
            full_path=project.path_with_namespace,
            clone_url=project.http_url_to_repo,
            default_branch=project.default_branch,
            archived=project.archived,
            namespace=project.namespace.get("full_path", ""),
            _raw=project,
        )

    def list_repositories(
        self,
        namespace_id: Optional[str] = None,
        include_subgroups: bool = True,
    ) -> Iterator[Repository]:
        """
        List repositories (GitLab projects) in a group.

        Args:
            namespace_id: GitLab group ID.
            include_subgroups: Whether to include projects from subgroups.

        Yields:
            Repository objects.
        """
        if namespace_id:
            group = self._client.groups.get(id=int(namespace_id))
            for group_project in group.projects.list(
                iterator=True,
                include_subgroups=include_subgroups,
            ):
                # Get full project object (group.projects gives partial objects)
                project = self._client.projects.get(id=group_project.get_id())
                yield self._project_to_repository(project)
        else:
            for project in self._client.projects.list(iterator=True):
                yield self._project_to_repository(project)

    def get_repository(self, repo_id: str) -> Repository:
        """
        Get a GitLab project by ID.

        Args:
            repo_id: GitLab project ID.

        Returns:
            Repository object.
        """
        project = self._client.projects.get(id=int(repo_id))
        return self._project_to_repository(project)

    def get_default_branch(self, repo: Repository) -> Branch:
        """
        Get the default branch of a repository.

        Args:
            repo: Repository object.

        Returns:
            Branch object.
        """
        project: Project = repo._raw
        branch: ProjectBranch = project.branches.get(project.default_branch)

        committed_at = None
        if commit_date := branch.commit.get("committed_date"):
            committed_at = datetime.fromisoformat(commit_date).replace(tzinfo=None)

        return Branch(
            name=branch.name,
            commit_sha=branch.commit.get("id", ""),
            commit_message=branch.commit.get("message", ""),
            committed_at=committed_at,
        )

    def branch_exists(self, repo: Repository, branch_name: str) -> bool:
        """
        Check if a branch exists in the GitLab project.

        Args:
            repo: Repository object.
            branch_name: Branch name to check.

        Returns:
            True if branch exists.
        """
        project: Project = repo._raw
        return bool(project.branches.list(search=branch_name))

    def list_open_pull_requests(
        self,
        repo: Repository,
        author: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[PullRequest]:
        """
        List open merge requests for a GitLab project.

        Args:
            repo: Repository object.
            author: Filter by author username.
            search: Search string in MR title.

        Returns:
            List of PullRequest objects.
        """
        project: Project = repo._raw
        kwargs = {"state": "opened"}

        if author:
            kwargs["author_username"] = author
        if search:
            kwargs["search"] = search

        merge_requests = project.mergerequests.list(**kwargs)

        return [
            PullRequest(
                id=str(mr.get_id()),
                title=mr.title,
                source_branch=mr.source_branch,
                target_branch=mr.target_branch,
                web_url=mr.web_url,
                state="open" if mr.state == "opened" else mr.state,
            )
            for mr in merge_requests
        ]

    def create_pull_request(
        self,
        repo: Repository,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> PullRequest:
        """
        Create a merge request in GitLab.

        Args:
            repo: Repository object.
            source_branch: Source branch name.
            target_branch: Target branch name.
            title: Merge request title.
            description: Merge request description.

        Returns:
            Created PullRequest object.
        """
        project: Project = repo._raw
        mr = project.mergerequests.create(
            {
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": description,
            }
        )

        return PullRequest(
            id=str(mr.get_id()),
            title=mr.title,
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            web_url=mr.web_url,
            state="open",
        )

    def configure_git_credentials(self, repo_path: Path) -> None:
        """
        Configure git credentials for the repository.

        For GitLab, we configure user.name and user.email.
        """
        from git import Repo

        repo = Repo(repo_path)
        repo.git.config("user.name", self._username)
        if self._email:
            repo.git.config("user.email", self._email)

    def get_authenticated_clone_url(self, repo: Repository) -> str:
        """
        Get clone URL with OAuth token embedded.

        Args:
            repo: Repository object.

        Returns:
            Clone URL with authentication.
        """
        if self._oauth_token:
            parsed = urlparse(repo.clone_url)
            return f"{parsed.scheme}://oauth2:{self._oauth_token}@{parsed.netloc}{parsed.path}"
        elif self._private_token:
            parsed = urlparse(repo.clone_url)
            return f"{parsed.scheme}://gitlab-ci-token:{self._private_token}@{parsed.netloc}{parsed.path}"
        return repo.clone_url
