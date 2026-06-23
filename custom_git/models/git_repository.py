# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Custom Git Repository — stores GitHub repository configuration.

This is a standalone model that stores repository details and
connects to GitHub via PyGithub to sync branches and commits.
No dependency on OCA github_connector.
"""

import logging
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.github_api import GitHubAPI

_logger = logging.getLogger(__name__)


class CustomGitRepository(models.Model):
    _name = "custom.git.repository"
    _description = "Custom Git Repository"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "display_name"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Repository Name",
        required=True,
        help="Short name for this repository (e.g. my-project).",
    )

    full_name = fields.Char(
        string="GitHub Full Name",
        required=True,
        help='GitHub "owner/repo" identifier (e.g. "octocat/Hello-World").',
        index=True,
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    github_url = fields.Char(
        string="GitHub URL",
        compute="_compute_github_url",
    )

    github_token = fields.Char(
        string="GitHub Token",
        groups="base.group_system",
        help="Personal access token for this repository. "
        "If empty, the system-wide token from System Parameters is used.",
    )

    last_sync = fields.Datetime(
        string="Last Sync",
        help="Last time commits were synced.",
    )

    branch_ids = fields.One2many(
        comodel_name="custom.git.branch",
        inverse_name="repository_id",
        string="Branches",
    )

    commit_ids = fields.One2many(
        comodel_name="custom.git.commit",
        inverse_name="repository_id",
        string="Commits",
    )

    branch_count = fields.Integer(
        string="Branches",
        compute="_compute_counts",
    )

    commit_count = fields.Integer(
        string="Commits",
        compute="_compute_counts",
    )

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("full_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.full_name or rec.name

    @api.depends("full_name")
    def _compute_github_url(self):
        for rec in self:
            if rec.full_name:
                rec.github_url = "https://github.com/%s" % rec.full_name
            else:
                rec.github_url = ""

    @api.depends("branch_ids", "commit_ids")
    def _compute_counts(self):
        for rec in self:
            rec.branch_count = len(rec.branch_ids)
            rec.commit_count = len(rec.commit_ids)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_github(self):
        """Open the repository on GitHub in a new browser tab."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.github_url or "https://github.com",
            "target": "_blank",
        }

    def action_sync_branches(self):
        """Fetch all branches from GitHub and create/update records.

        Uses PyGithub to list branches and upserts them in Odoo.
        """
        self.ensure_one()
        api = GitHubAPI(self.env)

        try:
            gh_repo = api.get_repo(self.full_name, self.github_token)
            branch_names = api.list_branches(gh_repo)
        except (ValueError, Exception) as exc:
            raise UserError(str(exc)) from exc

        branch_model = self.env["custom.git.branch"]
        created = 0
        updated = 0

        for bname in branch_names:
            existing = branch_model.search(
                [
                    ("repository_id", "=", self.id),
                    ("name", "=", bname),
                ],
                limit=1,
            )
            if existing:
                updated += 1
            else:
                branch_model.create(
                    {
                        "repository_id": self.id,
                        "name": bname,
                    }
                )
                created += 1

        self.message_post(
            body=self.env._(
                "<b>Branches Synced</b><br/>"
                "Created %d new, updated %d existing branches.",
                created,
                updated,
            )
        )

    def action_sync_all_commits(self):
        """Sync commits for every branch of this repository."""
        self.ensure_one()
        total = 0
        for branch in self.branch_ids:
            try:
                count = branch._sync_commits_from_github()
                total += count
            except Exception as exc:
                _logger.warning(
                    "Failed to sync branch '%s': %s", branch.name, exc
                )
        self.message_post(
            body=self.env._(
                "<b>All Branches Synced</b><br/>"
                "%d new commits fetched across all branches.",
                total,
            )
        )

    def action_view_branches(self):
        """Open the branches list for this repository."""
        self.ensure_one()
        return {
            "name": self.env._("Branches"),
            "type": "ir.actions.act_window",
            "res_model": "custom.git.branch",
            "view_mode": "list,form",
            "domain": [("repository_id", "=", self.id)],
            "context": {"default_repository_id": self.id},
        }

    def action_view_commits(self):
        """Open all commits for this repository."""
        self.ensure_one()
        return {
            "name": self.env._("Commits"),
            "type": "ir.actions.act_window",
            "res_model": "custom.git.commit",
            "view_mode": "list,form",
            "domain": [("repository_id", "=", self.id)],
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # def _check_admin(self):
    #     if not self.user_has_groups("custom_git.group_git_admin"):
    #         raise UserError(
    #             self.env._("You need Git Admin access to perform this action.")
    #         )