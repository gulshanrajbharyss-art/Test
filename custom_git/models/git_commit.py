# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Custom Git Commit — stores individual commit data fetched from GitHub.

Each record represents one commit on one branch of one repository,
showing who committed, when, and what changed.
"""

from odoo import api, fields, models


class CustomGitCommit(models.Model):
    _name = "custom.git.commit"
    _description = "Custom Git Commit"
    _order = "commit_date desc"
    _rec_name = "short_sha"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    repository_id = fields.Many2one(
        comodel_name="custom.git.repository",
        string="Repository",
        required=True,
        index=True,
        ondelete="cascade",
    )

    branch_id = fields.Many2one(
        comodel_name="custom.git.branch",
        string="Branch",
        index=True,
        ondelete="set null",
    )

    sha = fields.Char(
        string="SHA",
        required=True,
        index=True,
        help="Full SHA-1 hash of the commit.",
    )

    short_sha = fields.Char(
        string="Short SHA",
        compute="_compute_short_sha",
        store=True,
    )

    # -- Who committed --

    author_name = fields.Char(
        string="Author Name",
        index=True,
        help="Name of the person who made the commit.",
    )

    author_login = fields.Char(
        string="GitHub Username",
        index=True,
        help="GitHub login of the commit author.",
    )

    author_email = fields.Char(
        string="Author Email",
    )

    # -- When --

    commit_date = fields.Datetime(
        string="Commit Date",
        index=True,
        help="When the commit was created.",
    )

    # -- What --

    commit_message = fields.Text(
        string="Message",
        help="The full commit message.",
    )

    files_changed = fields.Integer(
        string="Files Changed",
        default=0,
    )

    additions = fields.Integer(
        string="Additions",
        default=0,
        help="Total lines added.",
    )

    deletions = fields.Integer(
        string="Deletions",
        default=0,
        help="Total lines deleted.",
    )

    url = fields.Char(
        string="GitHub URL",
        help="Direct link to the commit on GitHub.",
    )

    changed_file_ids = fields.One2many(
        comodel_name="custom.git.commit.file",
        inverse_name="commit_id",
        string="Changed Files",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        related="repository_id.company_id",
        store=True,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends("sha")
    def _compute_short_sha(self):
        for rec in self:
            rec.short_sha = rec.sha[:7] if rec.sha else ""

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_view_on_github(self):
        """Open the commit on GitHub."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "_blank",
        }