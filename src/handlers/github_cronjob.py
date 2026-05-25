import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from git import Repo
from github import Github
from github.Repository import Repository
from pydantic import BaseModel, Field

import config
from config import load_config_from_file
from handlers.analyze import AnalyzeHandler, AnalyzeHandlerConfig
from utils import Logger
from utils.dict import merge_dicts

from .base_handler import AbstractHandler

COMMIT_MESSAGE_TITLE = "[AI] Analyzer-Agent: Create/Update AI Analysis"
IGNORED_REPOS: List[str] = []  # List of repo full_names to ignore (e.g. "org/repo-name")
IGNORED_TOPICS: List[str] = []  # List of GitHub topics to ignore


class GithubJobAnalyzeHandlerConfig(BaseModel):
    max_days_since_last_commit: Optional[int] = Field(
        default=30,
        description="Maximum days since last commit to consider a repo for cronjob execution",
    )
    working_path: Optional[Path] = Field(
        default=Path("/tmp/cronjob/projects"),
        description="Path to clone projects for cronjob execution",
    )
    org_name: str = Field(
        ...,
        description="GitHub organization name to analyze",
    )


class GithubJobAnalyzeHandler(AbstractHandler):
    def __init__(self, github_client: Github, config: GithubJobAnalyzeHandlerConfig) -> None:
        super().__init__()

        self._config = config
        self._github_client = github_client

        self._config.working_path.mkdir(parents=True, exist_ok=True)

    async def handle(self):
        Logger.info(f"Starting GitHub cronjob handler for org: {self._config.org_name}")

        org = self._github_client.get_organization(self._config.org_name)

        for repo in org.get_repos(type="sources"):
            try:
                Logger.info(f"Checking repo {repo.full_name}")
                if self._is_applicable_repo(repo):
                    Logger.debug(f"Repo {repo.full_name} is applicable")
                    await self._handle_repo(repo)
            except Exception as err:
                Logger.error(
                    f"Error handling repo {repo.full_name}: {err}",
                    data={"repo": repo.full_name},
                    exc_info=True,
                )

    def _is_applicable_repo(self, repo: Repository) -> bool:
        if repo.archived:
            return False

        if repo.full_name in IGNORED_REPOS:
            Logger.debug(f"Repo {repo.full_name} is ignored for cronjob")
            return False

        for topic in IGNORED_TOPICS:
            if topic in repo.get_topics():
                return False

        # Check if last commit is the AI analysis commit
        default_branch = repo.get_branch(repo.default_branch)
        last_commit_message = default_branch.commit.commit.message
        if COMMIT_MESSAGE_TITLE in last_commit_message:
            Logger.debug(f"Repo {repo.full_name} is not updated since last analysis")
            return False

        # Check if last commit is recent enough
        last_commit_date = default_branch.commit.commit.author.date.replace(tzinfo=None)
        days_since_last_commit = (datetime.now() - last_commit_date).days
        if days_since_last_commit > self._config.max_days_since_last_commit:
            Logger.debug(f"Repo {repo.full_name} last commit is {days_since_last_commit} days ago, skipping")
            return False

        # Check if today's branch already exists
        branch_name = self._get_branch_name()
        try:
            repo.get_branch(branch_name)
            Logger.debug(f"Today's branch {branch_name} already exists in {repo.full_name}")
            return False
        except Exception:
            pass

        # Check if a similar PR already exists
        open_prs = repo.get_pulls(state="open")
        for pr in open_prs:
            if COMMIT_MESSAGE_TITLE in pr.title:
                Logger.debug(f"Similar PR already exists in {repo.full_name}")
                return False

        return True

    async def _handle_repo(self, repo: Repository):
        Logger.info(f"Running GitHub cronjob for repo {repo.full_name}")
        git_repo = None

        try:
            git_repo = self._clone_repo(repo)
            await self._analyze_repo(repo=repo, git_repo=git_repo)
            await self._create_pull_request(repo=repo, git_repo=git_repo)
        finally:
            if git_repo is not None:
                self._cleanup_repo(repo=repo, git_repo=git_repo)

    def _clone_repo(self, repo: Repository) -> Repo:
        Logger.info(f"Cloning repo {repo.full_name}")

        # Inject token into clone URL for authentication
        clone_url = repo.clone_url.replace("https://", f"https://x-access-token:{config.GITHUB_TOKEN}@")

        repo_dir = self._config.working_path / f"{repo.name}-{repo.id}"

        if repo_dir.exists():
            Logger.debug(f"Removing existing repo directory {repo_dir}")
            shutil.rmtree(repo_dir, ignore_errors=True)

        git_repo = Repo.clone_from(
            url=clone_url,
            to_path=repo_dir,
            branch=repo.default_branch,
        )

        git_repo.git.config("user.name", config.GITHUB_USER_NAME)
        git_repo.git.config("user.email", config.GITHUB_USER_EMAIL)

        branch_name = self._get_branch_name()
        git_repo.git.checkout("-b", branch_name)

        Logger.debug(f"Cloned {repo.full_name} to branch {branch_name}")

        return git_repo

    async def _analyze_repo(self, repo: Repository, git_repo: Repo):
        Logger.info(f"Analyzing repo {repo.full_name}")

        args = SimpleNamespace(repo_path=git_repo.working_dir, config=None)
        project_config = load_config_from_file(args, "analyzer")

        base_config = {"repo_path": Path(git_repo.working_dir)}
        final_config = merge_dicts(base_config, project_config)

        analyzer = AnalyzeHandler(config=AnalyzeHandlerConfig(**final_config))
        await analyzer.handle()

    async def _create_pull_request(self, repo: Repository, git_repo: Repo):
        Logger.info(f"Creating pull request for repo {repo.full_name}")

        git_repo.git.add(".")
        commit_message = f"{COMMIT_MESSAGE_TITLE} [skip ci]\n\nAnalyzer Version: {config.VERSION}"
        git_repo.git.commit("-m", commit_message)
        git_repo.git.push("origin", git_repo.active_branch.name, "-f")

        pr = repo.create_pull(
            title=f"{COMMIT_MESSAGE_TITLE} for {repo.name} - {datetime.now().strftime('%Y-%m-%d')} [skip ci]",
            body=(
                "This pull request contains updated AI analysis results.\n\n"
                f"Analyzer Version: `{config.VERSION}`\n\n"
                "**Note:** This pull request is automatically created by the AI Analyzer Agent."
            ),
            head=git_repo.active_branch.name,
            base=repo.default_branch,
        )

        Logger.debug(
            f"Created PR #{pr.number} for repo {repo.full_name}",
            data={
                "pr_number": pr.number,
                "pr_title": pr.title,
                "html_url": pr.html_url,
            },
        )

    def _cleanup_repo(self, repo: Repository, git_repo: Repo):
        Logger.info(f"Cleaning up repo {repo.full_name}")

        git_repo.close()
        git_repo.git.clear_cache()

        repo_path = Path(git_repo.working_dir)
        shutil.rmtree(repo_path, ignore_errors=True)

        Logger.debug(f"Cleaned up repo {repo.full_name} at {repo_path}")

    def _get_branch_name(self) -> str:
        return f"ai-analyzer-{datetime.now().strftime('%Y-%m-%d')}"
