# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Custom Git Commit File — stores per-file change details for a commit."""

from odoo import fields, models


class CustomGitCommitFile(models.Model):
    _name = "custom.git.commit.file"
    _description = "Custom Git Commit File"
    _order = "filename"
    _rec_name = "filename"

    commit_id = fields.Many2one(
        comodel_name="custom.git.commit",
        string="Commit",
        required=True,
        index=True,
        ondelete="cascade",
    )

    filename = fields.Char(
        string="Filename",
        required=True,
        index=True,
    )

    status = fields.Selection(
        selection=[
            ("added", "Added"),
            ("modified", "Modified"),
            ("removed", "Removed"),
            ("renamed", "Renamed"),
        ],
        string="Status",
        required=True,
    )

    additions = fields.Integer(
        string="Additions",
        default=0,
    )

    deletions = fields.Integer(
        string="Deletions",
        default=0,
    )

    changes = fields.Integer(
        string="Changes",
        default=0,
    )

    raw_url = fields.Char(
        string="Raw URL",
    )

    previous_filename = fields.Char(
        string="Previous Filename",
        help="Original filename when status is 'renamed'.",
    )

    patch = fields.Text(
        string="Patch",
        help="The diff patch for this file.",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="commit_id.company_id",
        store=True,
    )