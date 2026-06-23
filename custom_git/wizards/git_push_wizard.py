# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Push — push commits to remote."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import local_git as lgit


class GitLocalPushWizard(models.TransientModel):
    _name = "git.local.push.wizard"
    _description = "Git Push Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    remote = fields.Char(
        string="Remote",
        default="origin",
        required=True,
    )

    branch = fields.Char(
        string="Branch",
        help="Leave empty to push the current branch.",
    )

    force_push = fields.Boolean(
        string="Force Push (--force-with-lease)",
        default=False,
        help="Force push with lease — safer than --force. "
             "Will fail if the remote has commits you have not fetched.",
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

    @api.onchange("repository_id")
    def _onchange_repository(self):
        if self.repository_id and self.repository_id.local_path:
            self.branch = lgit.get_current_branch(self.repository_id.local_path)

    def action_confirm(self):
        """Execute git push."""
        self.ensure_one()
        repo = self.repository_id
        result = lgit.git_push(
            repo.local_path,
            remote=self.remote or "origin",
            branch=self.branch or None,
            force=self.force_push,
        )
        repo._post_result("Git Push", result)
        if not result["success"]:
            raise UserError(
                "Git push failed:\n%s\n%s"
                % (result.get("output", ""), result.get("error", ""))
            )
        return {"type": "ir.actions.act_window_close"}
