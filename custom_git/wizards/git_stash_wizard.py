# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Stash — stash current working-tree changes."""

from odoo import api, fields, models

from ..services import local_git as lgit


class GitLocalStashWizard(models.TransientModel):
    _name = "git.local.stash.wizard"
    _description = "Git Stash Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    stash_message = fields.Char(
        string="Stash Message",
        help="Optional description for this stash entry.",
    )

    current_branch = fields.Char(
        string="Current Branch",
        compute="_compute_branch",
    )

    existing_stashes = fields.Text(
        string="Existing Stashes",
        compute="_compute_stashes",
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

    @api.depends("repository_id")
    def _compute_stashes(self):
        for rec in self:
            if rec.repository_id and rec.repository_id.local_path:
                result = lgit.git_stash_list(rec.repository_id.local_path)
                rec.existing_stashes = result.get("output") or "(no stashes)"
            else:
                rec.existing_stashes = ""

    def action_confirm(self):
        """Execute git stash push."""
        self.ensure_one()
        repo = self.repository_id
        result = lgit.git_stash(
            repo.local_path,
            message=self.stash_message or None,
        )
        repo._post_result("Git Stash", result)
        return {"type": "ir.actions.act_window_close"}
