"""
Bitbucket Server SCM provider implementation.

This module provides a Bitbucket Server-specific implementation of the SCMProvider interface,
using the atlassian-python-api library.

Note: This is for Bitbucket SERVER (self-hosted), not Bitbucket Cloud.
The API and authentication methods differ between the two.
"""

from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

from atlassian import Bitbucket

from .base import Branch, PullRequest, Repository, SCMProvider


class BitbucketServerProvider(SCMProvider):
    """
    Bitbucket Server implementation of the SCM provider interface.

    Terminology mapping:
    - Repository → Bitbucket "Repository"
    - Pull Request → Bitbucket "Pull Request"
    - Namespace → Bitbucket "Project" (container for repositories)

    Important: Bitbucket Server uses project_key/repo_slug as the repository identifier.
    """

    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        git_username: Optional[str] = None,
        git_email: Optional[str] = None,
    ):
        """
        Initialize Bitbucket Server provider.

        Args:
            url: Bitbucket Server instance URL.
            username: Username for authentication (used with password).
            password: Password for authentication (used with username).
            token: Personal access token for authentication (alternative to username/password).
            git_username: Git username for commits.
            git_email: Git email for commits.
        """
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._token = token
        self._git_username = git_username or "AI Analyzer"
        self._git_email = git_email

        # Initialize Bitbucket client
        if token:
            self._client = Bitbucket(
                url=url,
                token=token,
            )
        else:
            self._client = Bitbucket(
                url=url,
                username=username,
                password=password,
            )

    @property
    def provider_name(self) -> str:
        return "bitbucket_server"

    @property
    def git_user_name(self) -> str:
        return self._git_username

    @property
    def git_email(self) -> Optional[str]:
        return self._git_email

    def _repo_to_repository(self, project_key: str, repo_data: dict) -> Repository:
        """Convert Bitbucket repository data to provider-agnostic Repository."""
        # Build clone URL from repo data
        clone_url = ""
        for clone_link in repo_data.get("links", {}).get("clone", []):
            if clone_link.get("name") == "http":
                clone_url = clone_link.get("href", "")
                break

        # Get default branch - Bitbucket may not include this in list response
        default_branch = repo_data.get("defaultBranch", "main")
        if isinstance(default_branch, dict):
            default_branch = default_branch.get("displayId", "main")

        return Repository(
            id=f"{project_key}/{repo_data['slug']}",
            name=repo_data["name"],
            full_path=f"{project_key}/{repo_data['slug']}",
            clone_url=clone_url,
            default_branch=default_branch,
            archived=repo_data.get("archived", False),
            namespace=project_key,
            _raw=repo_data,
        )

    def list_repositories(
        self,
        namespace_id: Optional[str] = None,
        include_subgroups: bool = True,
    ) -> Iterator[Repository]:
        """
        List repositories in a Bitbucket project.

        Args:
            namespace_id: Bitbucket project key. If None, lists all accessible repos.
            include_subgroups: Not applicable for Bitbucket (no subgroups concept).

        Yields:
            Repository objects.
        """
        if namespace_id:
            # List repos in a specific project
            repos = self._client.repo_list(namespace_id, limit=1000)
            for repo in repos:
                yield self._repo_to_repository(namespace_id, repo)
        else:
            # List all projects and their repos
            projects = self._client.project_list()
            for project in projects:
                project_key = project["key"]
                repos = self._client.repo_list(project_key, limit=1000)
                for repo in repos:
                    yield self._repo_to_repository(project_key, repo)

    def get_repository(self, repo_id: str) -> Repository:
        """
        Get a Bitbucket repository by project_key/repo_slug.

        Args:
            repo_id: Repository identifier in "project_key/repo_slug" format.

        Returns:
            Repository object.
        """
        project_key, repo_slug = repo_id.split("/", 1)
        repo_data = self._client.get_repo(project_key, repo_slug)

        # Get default branch separately if not in repo data
        if "defaultBranch" not in repo_data:
            try:
                branches = self._client.get_branches(project_key, repo_slug, limit=100)
                for branch in branches:
                    if branch.get("isDefault"):
                        repo_data["defaultBranch"] = branch.get("displayId", "main")
                        break
            except Exception:
                repo_data["defaultBranch"] = "main"

        return self._repo_to_repository(project_key, repo_data)

    def get_default_branch(self, repo: Repository) -> Branch:
        """
        Get the default branch of a repository.

        Args:
            repo: Repository object.

        Returns:
            Branch object.
        """
        project_key, repo_slug = repo.id.split("/", 1)

        # Get branches and find the default one
        branches = self._client.get_branches(project_key, repo_slug, limit=100, details=True)

        for branch_data in branches:
            if branch_data.get("isDefault"):
                # Get latest commit info
                commit_sha = branch_data.get("latestCommit", "")
                commit_message = ""
                committed_at = None

                # Try to get commit details
                if commit_sha:
                    try:
                        commits = self._client.get_commits(
                            project_key,
                            repo_slug,
                            commit_sha,
                            commit_sha,
                            limit=1,
                        )
                        if commits:
                            commit = commits[0]
                            commit_message = commit.get("message", "")
                            if author_timestamp := commit.get("authorTimestamp"):
                                # Bitbucket returns timestamp in milliseconds
                                committed_at = datetime.fromtimestamp(author_timestamp / 1000)
                    except Exception:
                        pass

                return Branch(
                    name=branch_data.get("displayId", repo.default_branch),
                    commit_sha=commit_sha,
                    commit_message=commit_message,
                    committed_at=committed_at,
                )

        # Fallback if no default branch found
        return Branch(
            name=repo.default_branch,
            commit_sha="",
            commit_message="",
            committed_at=None,
        )

    def branch_exists(self, repo: Repository, branch_name: str) -> bool:
        """
        Check if a branch exists in the Bitbucket repository.

        Args:
            repo: Repository object.
            branch_name: Branch name to check.

        Returns:
            True if branch exists.
        """
        project_key, repo_slug = repo.id.split("/", 1)

        try:
            branches = self._client.get_branches(
                project_key,
                repo_slug,
                filter=branch_name,
                limit=10,
            )
            for branch in branches:
                if branch.get("displayId") == branch_name:
                    return True
            return False
        except Exception:
            return False

    def list_open_pull_requests(
        self,
        repo: Repository,
        author: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[PullRequest]:
        """
        List open pull requests for a Bitbucket repository.

        Args:
            repo: Repository object.
            author: Filter by author username (note: Bitbucket doesn't support this directly).
            search: Search string in PR title (note: filtering done client-side).

        Returns:
            List of PullRequest objects.
        """
        project_key, repo_slug = repo.id.split("/", 1)

        pull_requests = self._client.get_pull_requests(
            project_key,
            repo_slug,
            state="OPEN",
            limit=100,
        )

        result = []
        for pr in pull_requests:
            pr_title = pr.get("title", "")

            # Client-side filtering
            if author:
                pr_author = pr.get("author", {}).get("user", {}).get("name", "")
                if pr_author.lower() != author.lower():
                    continue

            if search and search.lower() not in pr_title.lower():
                continue

            # Build web URL
            web_url = f"{self._url}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr.get('id')}"

            result.append(
                PullRequest(
                    id=str(pr.get("id")),
                    title=pr_title,
                    source_branch=pr.get("fromRef", {}).get("displayId", ""),
                    target_branch=pr.get("toRef", {}).get("displayId", ""),
                    web_url=web_url,
                    state="open",
                )
            )

        return result

    def create_pull_request(
        self,
        repo: Repository,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> PullRequest:
        """
        Create a pull request in Bitbucket.

        Args:
            repo: Repository object.
            source_branch: Source branch name.
            target_branch: Target branch name.
            title: Pull request title.
            description: Pull request description.

        Returns:
            Created PullRequest object.
        """
        project_key, repo_slug = repo.id.split("/", 1)

        pr = self._client.open_pull_request(
            source_project=project_key,
            source_repo=repo_slug,
            dest_project=project_key,
            dest_repo=repo_slug,
            source_branch=source_branch,
            destination_branch=target_branch,
            title=title,
            description=description,
        )

        web_url = f"{self._url}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr.get('id')}"

        return PullRequest(
            id=str(pr.get("id")),
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            web_url=web_url,
            state="open",
        )

    def configure_git_credentials(self, repo_path: Path) -> None:
        """
        Configure git credentials for the repository.

        For Bitbucket Server, we configure user.name and user.email.
        """
        from git import Repo

        repo = Repo(repo_path)
        repo.git.config("user.name", self._git_username)
        if self._git_email:
            repo.git.config("user.email", self._git_email)

    def get_authenticated_clone_url(self, repo: Repository) -> str:
        """
        Get clone URL with authentication embedded.

        Args:
            repo: Repository object.

        Returns:
            Clone URL with authentication.
        """
        parsed = urlparse(repo.clone_url)

        if self._token:
            # Use token-based auth
            return f"{parsed.scheme}://x-token-auth:{self._token}@{parsed.netloc}{parsed.path}"
        elif self._username and self._password:
            # Use basic auth (URL-encode special characters in password)
            from urllib.parse import quote

            encoded_password = quote(self._password, safe="")
            return f"{parsed.scheme}://{self._username}:{encoded_password}@{parsed.netloc}{parsed.path}"

        return repo.clone_url
