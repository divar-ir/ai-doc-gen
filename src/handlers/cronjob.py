import shutil
import warnings
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from git import Repo
from pydantic import BaseModel, Field, model_validator

import config
from config import load_config_from_file
from handlers.analyze import AnalyzeHandler, AnalyzeHandlerConfig
from scm_providers import SCMProvider, Repository
from utils import Logger
from utils.dict import merge_dicts

from .base_handler import AbstractHandler

COMMIT_MESSAGE_TITLE = "[AI] Analyzer-Agent: Create/Update AI Analysis"

# List of repository IDs to ignore (provider-specific format)
# GitLab: integer project IDs
# Bitbucket: "project_key/repo_slug" format
IGNORED_REPOSITORIES: List[str] = []

# List of namespace names to ignore (case-insensitive)
# GitLab: group names in the path
# Bitbucket: project keys
IGNORED_NAMESPACES: List[str] = []


class CronjobAnalyzeHandlerConfig(BaseModel):
    """Configuration for the cronjob analyze handler."""

    max_days_since_last_commit: Optional[int] = Field(
        default=30,
        description="Maximum days since last commit to consider a repository for analysis",
    )
    working_path: Optional[Path] = Field(
        default=Path("/tmp/cronjob/repositories"),
        description="Path to clone repositories for cronjob execution",
    )
    namespace_id: Optional[str] = Field(
        default=None,
        description="Namespace/group ID to analyze (GitLab: group ID, Bitbucket: project key)",
    )

    # Deprecated: Use namespace_id instead (kept for backwards compatibility)
    group_project_id: Optional[str] = Field(
        default=None,
        description="DEPRECATED: Use --namespace-id instead. Will be removed in v2.0",
    )

    @model_validator(mode="after")
    def handle_deprecated_group_project_id(self):
        """Handle backwards compatibility for deprecated group_project_id field."""
        if self.group_project_id is not None:
            warnings.warn(
                "The '--group-project-id' argument is deprecated and will be removed in v2.0. "
                "Please use '--namespace-id' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            # If namespace_id is not set, use the deprecated value
            if self.namespace_id is None:
                self.namespace_id = self.group_project_id
        return self


# Backward compatibility alias
JobAnalyzeHandlerConfig = CronjobAnalyzeHandlerConfig


class CronjobAnalyzeHandler(AbstractHandler):
    """
    Handler for automated repository analysis via cronjob.

    This handler iterates over repositories in an SCM system, analyzes them,
    and creates pull requests with the analysis results.
    """

    def __init__(
        self,
        scm_provider: SCMProvider,
        config: CronjobAnalyzeHandlerConfig,
    ) -> None:
        super().__init__()

        self._config = config
        self._scm_provider = scm_provider

        self._config.working_path.mkdir(parents=True, exist_ok=True)

    async def handle(self):
        Logger.info(f"Starting cronjob handler with {self._scm_provider.provider_name} provider")

        for repo in self._scm_provider.list_repositories(
            namespace_id=self._config.namespace_id,
            include_subgroups=True,
        ):
            try:
                Logger.info(f"Checking repository {repo.name} (ID: {repo.id})")

                if self._is_applicable_repository(repo):
                    Logger.debug(f"Repository {repo.name} (ID: {repo.id}) is applicable")
                    await self._handle_repository(repo)

            except Exception as err:
                Logger.error(
                    f"Error handling repository {repo.name} (ID: {repo.id}): {err}",
                    data={
                        "repository_id": repo.id,
                        "repository_name": repo.name,
                    },
                    exc_info=True,
                )

    def _is_applicable_repository(self, repo: Repository) -> bool:
        """
        Check if a repository should be analyzed.

        Filters out:
        - Archived repositories
        - Repositories in ignored namespaces
        - Repositories in the ignore list
        - Repositories with no updates since last analysis
        - Repositories that already have today's analysis branch
        - Repositories with an existing open PR from this tool
        """
        # Check if repository is archived
        if repo.archived:
            Logger.debug(f"Repository {repo.name} is archived, skipping")
            return False

        # Check if repository is in ignored namespaces
        if self._scm_provider.is_namespace_ignored(repo, IGNORED_NAMESPACES):
            Logger.debug(f"Repository {repo.name} is in ignored namespace, skipping")
            return False

        # Check if repository is in ignored list
        if repo.id in IGNORED_REPOSITORIES:
            Logger.debug(f"Repository {repo.name} is in ignore list, skipping")
            return False

        # Get default branch info
        default_branch = self._scm_provider.get_default_branch(repo)

        # Check if last commit was from this tool (no updates since last analysis)
        if COMMIT_MESSAGE_TITLE in default_branch.commit_message:
            Logger.debug(f"Repository {repo.name} has no updates since last analysis")
            return False

        # Check if repository is too old (no recent commits)
        if default_branch.committed_at:
            days_since_last_commit = (datetime.now() - default_branch.committed_at).days
            if days_since_last_commit > self._config.max_days_since_last_commit:
                Logger.debug(f"Repository {repo.name} has no commits in {days_since_last_commit} days, skipping")
                return False

        # Check if today's branch already exists
        branch_name = self._get_branch_name()
        if self._scm_provider.branch_exists(repo, branch_name):
            Logger.debug(f"Today's branch {branch_name} already exists, skipping")
            return False

        # Check if similar PR already exists
        existing_prs = self._scm_provider.list_open_pull_requests(
            repo=repo,
            author=config.SCM_GIT_USER_USERNAME,
            search=COMMIT_MESSAGE_TITLE,
        )
        if existing_prs:
            Logger.debug("Similar PR already exists, skipping")
            return False

        return True

    async def _handle_repository(self, repo: Repository):
        """Clone, analyze, and create PR for a repository."""
        Logger.info(f"Running cronjob for repository {repo.name} (ID: {repo.id})")

        local_repo = None
        try:
            # Clone repository
            local_repo = self._clone_repository(repo)

            # Analyze repository
            await self._analyze_repository(repo=repo, local_repo=local_repo)

            # Create PR
            await self._create_pull_request(repo=repo, local_repo=local_repo)

        finally:
            # Cleanup
            if local_repo:
                self._cleanup_repository(repo=repo, local_repo=local_repo)

    def _clone_repository(self, repo: Repository) -> Repo:
        """Clone a repository to local filesystem."""
        Logger.info(f"Cloning repository {repo.name} (ID: {repo.id})")

        # Get authenticated clone URL
        clone_url = self._scm_provider.get_authenticated_clone_url(repo)

        repo_dir = self._config.working_path / f"{repo.name}-{repo.id.replace('/', '-')}"

        if repo_dir.exists():
            Logger.debug(f"Removing existing repository directory {repo_dir}")
            shutil.rmtree(repo_dir, ignore_errors=True)

        local_repo = Repo.clone_from(
            url=clone_url,
            to_path=repo_dir,
            branch=repo.default_branch,
        )

        # Configure git credentials
        self._scm_provider.configure_git_credentials(repo_dir)

        # Create analysis branch
        branch_name = self._get_branch_name()
        local_repo.git.checkout("-b", branch_name)

        Logger.debug(f"Cloned repository {repo.name} to branch {branch_name}")

        return local_repo

    async def _analyze_repository(self, repo: Repository, local_repo: Repo):
        """Run analysis on the cloned repository."""
        Logger.info(f"Analyzing repository {repo.name} (ID: {repo.id})")

        # Create an args object for config loading
        args = SimpleNamespace(repo_path=local_repo.working_dir, config=None)
        project_config = load_config_from_file(args, "analyzer")

        # Base config with cronjob defaults
        base_config = {
            "repo_path": Path(local_repo.working_dir),
        }

        # Merge project config with base config (project config takes precedence)
        final_config = merge_dicts(base_config, project_config)

        analyzer = AnalyzeHandler(config=AnalyzeHandlerConfig(**final_config))

        await analyzer.handle()

    async def _create_pull_request(self, repo: Repository, local_repo: Repo):
        """Commit changes and create a pull request."""
        Logger.info(f"Creating pull request for repository {repo.name} (ID: {repo.id})")

        # Commit and push changes
        local_repo.git.add(".")
        commit_message = f"{COMMIT_MESSAGE_TITLE} [skip ci]\n\nAnalyzer Version: {config.VERSION}"

        local_repo.git.commit("-m", commit_message)
        local_repo.git.push("origin", local_repo.active_branch.name, "-f")

        # Create PR via SCM provider
        pr = self._scm_provider.create_pull_request(
            repo=repo,
            source_branch=local_repo.active_branch.name,
            target_branch=repo.default_branch,
            title=f"{COMMIT_MESSAGE_TITLE} for {repo.name} - {datetime.now().strftime('%Y-%m-%d')} [skip ci]",
            description=(
                f"This pull request contains updated AI analysis results.\n\n"
                f"Analyzer Version: `{config.VERSION}`\n\n"
                f"**Note:** This pull request was automatically created by the AI Analyzer Agent."
            ),
        )

        Logger.debug(
            f"Created pull request {pr.id} for repository {repo.name} (ID: {repo.id})",
            data={
                "pull_request_id": pr.id,
                "pull_request_title": pr.title,
                "web_url": pr.web_url,
            },
        )

    def _cleanup_repository(self, repo: Repository, local_repo: Repo):
        """Clean up cloned repository from filesystem."""
        Logger.info(f"Cleaning up repository {repo.name} (ID: {repo.id})")

        local_repo.close()
        local_repo.git.clear_cache()

        repo_path = Path(local_repo.working_dir)
        shutil.rmtree(repo_path, ignore_errors=True)

        Logger.debug(f"Cleaned up repository {repo.name} at {repo_path}")

    def _get_branch_name(self) -> str:
        """Get the branch name for today's analysis."""
        return f"ai-analyzer-{datetime.now().strftime('%Y-%m-%d')}"


# Backward compatibility alias
JobAnalyzeHandler = CronjobAnalyzeHandler
