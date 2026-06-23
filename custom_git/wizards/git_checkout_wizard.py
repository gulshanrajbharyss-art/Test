# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Checkout Branch — switch to an existing branch or create new."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import local_git as lgit


class GitLocalCheckoutWizard(models.TransientModel):
    _name = "git.local.checkout.wizard"
    _description = "Git Checkout Branch Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    branch_name = fields.Char(
        string="Branch Name",
        required=True,
        help="Name of the branch to checkout.",
    )

    create_new = fields.Boolean(
        string="Create New Branch (-b)",
        default=False,
        help="If checked, creates a new branch with this name.",
    )

    current_branch = fields.Char(
        string="Current Branch",
        compute="_compute_branch",
    )

    available_branches = fields.Text(
        string="Available Local Branches",
        compute="_compute_available",
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
    def _compute_available(self):
        for rec in self:
            if rec.repository_id and rec.repository_id.local_path:
                branches = lgit.list_local_branches(rec.repository_id.local_path)
                rec.available_branches = "\n".join(branches) if branches else "(none)"
            else:
                rec.available_branches = ""

    def action_confirm(self):
        """Execute git checkout."""
        self.ensure_one()
        if not self.branch_name or not self.branch_name.strip():
            raise UserError("Branch name cannot be empty.")
        repo = self.repository_id
        result = lgit.git_checkout_branch(
            repo.local_path,
            branch_name=self.branch_name.strip(),
            create=self.create_new,
        )
        repo._post_result("Git Checkout Branch", result)
        if not result["success"]:
            raise UserError(
                "Git checkout failed:\n%s\n%s"
                % (result.get("output", ""), result.get("error", ""))
            )
        # Update current_branch field on repository
        repo.invalidate_recordset(["current_branch"])
        return {"type": "ir.actions.act_window_close"}
