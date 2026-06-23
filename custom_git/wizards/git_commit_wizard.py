# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Commit — write a commit message and commit staged changes."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import local_git as lgit


class GitLocalCommitWizard(models.TransientModel):
    _name = "git.local.commit.wizard"
    _description = "Git Commit Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    commit_message = fields.Text(
        string="Commit Message",
        required=True,
        help="Enter your commit message. Use the imperative mood: 'Fix bug', not 'Fixed bug'.",
    )

    author_name = fields.Char(
        string="Author Name",
        default=lambda self: self.env.user.name,
        help="Defaults to the current Odoo user name. "
             "Leave blank to use the global Git config.",
    )

    author_email = fields.Char(
        string="Author Email",
        default=lambda self: self.env.user.email or "",
        help="Defaults to the current Odoo user email.",
    )

    current_branch = fields.Char(
        string="Current Branch",
        compute="_compute_branch",
    )

    staged_output = fields.Text(
        string="Staged Changes",
        compute="_compute_staged",
        help="What will be committed (`git diff --cached --stat`).",
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
    def _compute_staged(self):
        for rec in self:
            if rec.repository_id and rec.repository_id.local_path:
                result = lgit.git_diff(rec.repository_id.local_path, staged=True)
                rec.staged_output = result.get("output") or "(nothing staged)"
            else:
                rec.staged_output = ""

    def action_confirm(self):
        """Execute git commit."""
        self.ensure_one()
        if not self.commit_message or not self.commit_message.strip():
            raise UserError("Commit message cannot be empty.")
        repo = self.repository_id
        result = lgit.git_commit(
            repo.local_path,
            message=self.commit_message,
            author_name=self.author_name or None,
            author_email=self.author_email or None,
        )
        repo._post_result("Git Commit", result)
        if not result["success"]:
            raise UserError(
                "Git commit failed:\n%s\n%s"
                % (result.get("output", ""), result.get("error", ""))
            )
        return {"type": "ir.actions.act_window_close"}
