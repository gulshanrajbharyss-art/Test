# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Custom Git Branch — per-branch commit sync and viewing.

Each branch record links to a repository and provides:
- A "Sync Commits" button that fetches ALL commits from GitHub
  for that specific branch using the configured token.
- A "View Commits" button that opens the commit list filtered
  by this branch.
"""

import logging
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.github_api import GitHubAPI

_logger = logging.getLogger(__name__)


class CustomGitBranch(models.Model):
    _name = "custom.git.branch"
    _description = "Custom Git Branch"
    _rec_name = "name"
    _order = "name"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Branch Name",
        required=True,
        index=True,
    )

    repository_id = fields.Many2one(
        comodel_name="custom.git.repository",
        string="Repository",
        required=True,
        ondelete="cascade",
        index=True,
    )

    commit_count = fields.Integer(
        string="Commits",
        compute="_compute_stats",
    )

    last_commit_sha = fields.Char(
        string="Last Commit",
        compute="_compute_stats",
    )

    last_commit_date = fields.Datetime(
        string="Last Commit Date",
        compute="_compute_stats",
    )

    last_sync = fields.Datetime(
        string="Last Sync",
        help="Last time commits were synced for this branch.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    def _compute_stats(self):
        commit_model = self.env["custom.git.commit"]
        for branch in self:
            latest = commit_model.search(
                [
                    ("repository_id", "=", branch.repository_id.id),
                    ("branch_id", "=", branch.id),
                ],
                limit=1,
                order="commit_date desc",
            )
            if latest:
                branch.last_commit_sha = latest.short_sha
                branch.last_commit_date = latest.commit_date
            else:
                branch.last_commit_sha = False
                branch.last_commit_date = False
            branch.commit_count = commit_model.search_count(
                [
                    ("repository_id", "=", branch.repository_id.id),
                    ("branch_id", "=", branch.id),
                ]
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_sync_commits(self):
        """Fetch ALL commits for this branch from GitHub API.

        Uses the repository's token (or system token) to call
        ``repo.get_commits(sha=branch_name)`` via PyGithub.
        Stores each commit with: who (author name/login/email),
        when (commit_date), what (message, files changed, +/- lines).

        Returns:
            Action dict opening the commits list for this branch.
        """
        self.ensure_one()
        self._check_admin()
        count = self._sync_commits_from_github()
        self.repository_id.message_post(
            body=self.env._(
                "<b>Branch '%s' Synced</b><br/>"
                "%d new commits fetched from GitHub.",
                self.name,
                count,
            )
        )
        return self.action_view_commits()

    def _sync_commits_from_github(self):
        """Core sync logic — fetches commits from GitHub and creates records.

        Returns:
            int: Number of new commits created.
        """
        self.ensure_one()
        api = GitHubAPI(self.env)
        commit_model = self.env["custom.git.commit"]
        file_model = self.env["custom.git.commit.file"]
        new_count = 0

        try:
            gh_repo = api.get_repo(
                self.repository_id.full_name,
                self.repository_id.github_token,
            )
            gh_commits = api.list_commits(gh_repo, self.name)
        except (ValueError, Exception) as exc:
            raise UserError(str(exc)) from exc

        for gh_commit in gh_commits:
            sha = gh_commit.sha

            # Skip duplicates
            if commit_model.search_count(
                [
                    ("repository_id", "=", self.repository_id.id),
                    ("sha", "=", sha),
                    ("branch_id", "=", self.id),
                ]
            ):
                continue

            # If commit exists under another branch, link it here too
            existing = commit_model.search(
                [
                    ("repository_id", "=", self.repository_id.id),
                    ("sha", "=", sha),
                ],
                limit=1,
            )
            if existing:
                existing.branch_id = self.id
                new_count += 1
                continue

            # Parse commit metadata
            data = api.parse_commit(gh_commit)
            files_data, total_add, total_del = api.parse_commit_files(gh_commit)

            commit = commit_model.create(
                {
                    "repository_id": self.repository_id.id,
                    "branch_id": self.id,
                    "sha": data["sha"],
                    "author_name": data["author_name"],
                    "author_email": data["author_email"],
                    "author_login": data["author_login"],
                    "commit_message": data["commit_message"],
                    "commit_date": data["commit_date"],
                    "files_changed": len(files_data),
                    "additions": total_add,
                    "deletions": total_del,
                    "url": data["url"],
                }
            )

            # Create file-level records
            for fd in files_data:
                file_model.create(
                    {
                        "commit_id": commit.id,
                        "filename": fd["filename"],
                        "status": fd["status"],
                        "additions": fd["additions"],
                        "deletions": fd["deletions"],
                        "changes": fd["changes"],
                        "raw_url": fd["raw_url"],
                        "patch": fd["patch"],
                        "previous_filename": fd["previous_filename"],
                    }
                )

            new_count += 1

        if new_count > 0:
            self.last_sync = datetime.now()

        return new_count

    def action_view_commits(self):
        """Open the commit list filtered to this branch.

        Returns:
            Action dict opening ``custom.git.commit`` list view.
        """
        self.ensure_one()
        return {
            "name": self.env._("Commits — %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "custom.git.commit",
            "view_mode": "list,form",
            "domain": [
                ("repository_id", "=", self.repository_id.id),
                ("branch_id", "=", self.id),
            ],
            "context": {
                "default_repository_id": self.repository_id.id,
                "default_branch_id": self.id,
            },
        }

    def _check_admin(self):
        if not self.env.user.has_group("custom_git.group_git_admin"):
            raise UserError(
                self.env._("You need Git Admin access to perform this action.")
            )