# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Lightweight GitHub API wrapper using PyGithub.

This service connects to the GitHub REST API using a personal access
token (stored as an Odoo system parameter or per-repository override).
It provides methods to fetch repositories, branches, and commits
without any dependency on OCA github_connector modules.
"""

import logging

from github import Github, GithubException

_logger = logging.getLogger(__name__)

# System parameter key for the global GitHub token
SYSTEM_TOKEN_KEY = "custom_git.github_token"


class GitHubAPI:
    """Thin wrapper around PyGithub for branch-based commit fetching.

    Usage::

        api = GitHubAPI(env)
        repo = api.get_repo("owner/repo-name")
        branches = api.list_branches(repo)
        commits = api.list_commits(repo, branch_name="main")
    """

    def __init__(self, env):
        """Initialise with an Odoo environment to read config.

        Args:
            env: Odoo environment (``self.env`` from a model).
        """
        self.env = env

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------

    def _get_token(self, repo_token=None):
        """Return the GitHub personal-access token to use.

        Resolution order:
        1. ``repo_token`` passed explicitly (per-repository override).
        2. System parameter ``custom_git.github_token``.
        3. Raise if nothing is configured.

        Args:
            repo_token: Optional token string from the repository record.

        Returns:
            str: The resolved token.

        Raises:
            ValueError: If no token is configured anywhere.
        """
        token = repo_token or self.env["ir.config_parameter"].sudo().get_param(
            SYSTEM_TOKEN_KEY
        )
        if not token:
            raise ValueError(
                "No GitHub token configured. "
                "Set 'custom_git.github_token' in Settings > Technical > System Parameters "
                "or add a token on the repository record."
            )
        return token.strip()

    def _get_github_client(self, repo_token=None):
        """Return an authenticated ``github.Github`` instance.

        Args:
            repo_token: Optional per-repository token override.

        Returns:
            github.Github: Authenticated GitHub client.
        """
        token = self._get_token(repo_token)
        return Github(token)

    # ------------------------------------------------------------------
    # Repository operations
    # ------------------------------------------------------------------

    def get_repo(self, full_name, repo_token=None):
        """Get a PyGithub ``Repository`` object by full name.

        Args:
            full_name: e.g. ``"owner/repo-name"``.
            repo_token: Optional per-repository token.

        Returns:
            github.Repository: The GitHub repository object.
        """
        gh = self._get_github_client(repo_token)
        try:
            return gh.get_repo(full_name)
        except GithubException as exc:
            if exc.status == 404:
                raise ValueError(
                    "Repository '%s' not found or token lacks access." % full_name
                ) from exc
            raise

    # ------------------------------------------------------------------
    # Branch operations
    # ------------------------------------------------------------------

    def list_branches(self, gh_repo):
        """List all branch names for a GitHub repository.

        Args:
            gh_repo: A PyGithub ``Repository`` object.

        Returns:
            list[str]: Branch name strings.
        """
        try:
            return [b.name for b in gh_repo.get_branches()]
        except GithubException as exc:
            _logger.error("Failed to list branches: %s", exc)
            raise ValueError("Failed to fetch branches from GitHub: %s" % exc) from exc

    # ------------------------------------------------------------------
    # Commit operations
    # ------------------------------------------------------------------

    def list_commits(self, gh_repo, branch_name):
        """Fetch all commits on a specific branch.

        Args:
            gh_repo: A PyGithub ``Repository`` object.
            branch_name: Name of the branch (e.g. ``"main"``).

        Returns:
            PaginatedList[Commit]: Iterable of PyGithub ``Commit`` objects.
        """
        try:
            return gh_repo.get_commits(sha=branch_name)
        except GithubException as exc:
            _logger.error(
                "Failed to fetch commits for branch '%s': %s",
                branch_name,
                exc,
            )
            raise ValueError(
                "Failed to fetch commits for branch '%s': %s"
                % (branch_name, exc)
            ) from exc

    @staticmethod
    def parse_commit(gh_commit):
        """Extract commit data from a PyGithub Commit into a plain dict.

        Args:
            gh_commit: A PyGithub ``Commit`` object.

        Returns:
            dict: Flat dict with commit fields ready for Odoo record creation.
        """
        author_name = ""
        author_email = ""
        author_login = ""
        commit_date = False

        if gh_commit.author:
            author_login = gh_commit.author.login or ""

        if gh_commit.commit and gh_commit.commit.author:
            author_name = gh_commit.commit.author.name or ""
            author_email = gh_commit.commit.author.email or ""
            try:
                raw_date = gh_commit.commit.author.date
                if raw_date:
                    # PyGithub returns timezone-aware datetime;
                    # Odoo needs naive UTC datetime.
                    commit_date = raw_date.replace(tzinfo=None)
            except (ValueError, TypeError, AttributeError):
                commit_date = False

        return {
            "sha": gh_commit.sha,
            "author_name": author_name,
            "author_email": author_email,
            "author_login": author_login,
            "commit_message": gh_commit.commit.message if gh_commit.commit else "",
            "commit_date": commit_date,
            "url": gh_commit.html_url or "",
        }

    @staticmethod
    def parse_commit_files(gh_commit):
        """Extract file-level change data from a PyGithub Commit.

        Args:
            gh_commit: A PyGithub ``Commit`` object.

        Returns:
            tuple[list[dict], int, int]:
                - List of file dicts (filename, status, additions, …).
                - Total additions across all files.
                - Total deletions across all files.
        """
        files_data = []
        total_additions = 0
        total_deletions = 0

        try:
            if gh_commit.files:
                for f in gh_commit.files:
                    files_data.append(
                        {
                            "filename": f.filename or "",
                            "status": f.status or "modified",
                            "additions": f.additions or 0,
                            "deletions": f.deletions or 0,
                            "changes": f.changes or 0,
                            "raw_url": f.raw_url or "",
                            "patch": f.patch or "",
                            "previous_filename": f.previous_filename or "",
                        }
                    )
                    total_additions += f.additions or 0
                    total_deletions += f.deletions or 0
        except Exception as exc:
            _logger.warning(
                "Could not fetch file changes for commit %s: %s",
                gh_commit.sha[:7],
                exc,
            )

        return files_data, total_additions, total_deletions