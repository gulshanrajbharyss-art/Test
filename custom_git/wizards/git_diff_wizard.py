# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Diff — shows unstaged or staged diff output."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import local_git as lgit


class GitLocalDiffWizard(models.TransientModel):
    _name = "git.local.diff.wizard"
    _description = "Git Diff Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    diff_type = fields.Selection(
        selection=[
            ("unstaged", "Unstaged Changes"),
            ("staged", "Staged Changes (Cached)"),
        ],
        string="Diff Type",
        default="unstaged",
        required=True,
    )

    diff_output = fields.Text(
        string="Diff Output",
        readonly=True,
    )

    current_branch = fields.Char(
        string="Current Branch",
        compute="_compute_branch",
    )

    @api.depends("repository_id")
    def _compute_branch(self):
        for rec in self:
            if rec.repository_id and rec.repository_id.local_path:
                rec.current_branch = lgit.get_current_branch(
                    rec.repository_id.local_path
                )
            else:
                rec.current_branch = "—"

    def action_run_diff(self):
        """Execute git diff and populate output field."""
        self.ensure_one()
        repo = self.repository_id
        staged = self.diff_type == "staged"
        result = lgit.git_diff(repo.local_path, staged=staged)

        output = result["output"] or "(no diff — working tree is clean)"
        if not result["success"] and result["error"]:
            output = result["error"]

        self.diff_output = output

        repo._post_result(
            "Git Diff (%s)" % self.diff_type,
            result,
        )
        # Return same wizard staying open to show output
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
