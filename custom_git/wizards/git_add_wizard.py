# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Add — stage files or `git add .`"""

from odoo import api, fields, models

from ..services import local_git as lgit


class GitLocalAddWizard(models.TransientModel):
    _name = "git.local.add.wizard"
    _description = "Git Add Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    add_all = fields.Boolean(
        string="Add All Files (git add .)",
        default=True,
        help="If checked, runs `git add .` to stage all changes.",
    )

    specific_files = fields.Text(
        string="Specific Files",
        help="One file path per line to stage. Used when 'Add All' is unchecked.",
    )

    current_branch = fields.Char(
        string="Current Branch",
        compute="_compute_branch",
    )

    status_output = fields.Text(
        string="Current Status",
        compute="_compute_status",
        help="Shows `git status --short` to help you decide what to stage.",
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
    def _compute_status(self):
        for rec in self:
            if rec.repository_id and rec.repository_id.local_path:
                result = lgit.git_status(rec.repository_id.local_path)
                rec.status_output = result.get("output") or "(clean)"
            else:
                rec.status_output = ""

    def action_confirm(self):
        """Execute git add."""
        self.ensure_one()
        repo = self.repository_id
        if self.add_all:
            files = None
        else:
            if not self.specific_files or not self.specific_files.strip():
                from odoo.exceptions import UserError
                raise UserError(
                    "Please enter at least one file path, or enable 'Add All Files'."
                )
            files = [
                f.strip()
                for f in self.specific_files.splitlines()
                if f.strip()
            ]
        result = lgit.git_add(repo.local_path, files=files)
        repo._post_result("Git Add", result)
        return {"type": "ir.actions.act_window_close"}
