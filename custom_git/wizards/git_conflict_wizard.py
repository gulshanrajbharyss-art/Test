# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Wizard: Git Conflict — displayed when merge or stash-pop conflicts detected."""

from odoo import api, fields, models

from ..services import local_git as lgit


class GitConflictWizard(models.TransientModel):
    _name = "git.conflict.wizard"
    _description = "Git Merge Conflict Wizard"

    repository_id = fields.Many2one(
        "custom.git.repository",
        string="Repository",
        required=True,
        readonly=True,
    )

    conflict_status = fields.Text(
        string="Conflicting Files",
        compute="_compute_conflict_status",
        help="Files with conflicts are marked with 'UU', 'AA', or 'DD'.",
    )

    instructions = fields.Html(
        string="Resolution Steps",
        compute="_compute_instructions",
    )

    @api.depends("repository_id")
    def _compute_conflict_status(self):
        for rec in self:
            if rec.repository_id and rec.repository_id.local_path:
                result = lgit.git_status(rec.repository_id.local_path)
                rec.conflict_status = result.get("output") or "(status unavailable)"
            else:
                rec.conflict_status = ""

    @api.depends("repository_id")
    def _compute_instructions(self):
        for rec in self:
            rec.instructions = """
<div class="alert alert-warning" role="alert">
    <h4><i class="fa fa-exclamation-triangle"/> Merge Conflicts Detected</h4>
    <p>Files marked with <code>UU</code>, <code>AA</code>, or <code>DD</code>
    in the status above have conflicts that must be resolved manually.</p>
    <ol>
        <li>Open each conflicting file in your editor on the server.</li>
        <li>Look for <code>&lt;&lt;&lt;&lt;&lt;&lt;&lt;</code>,
            <code>=======</code>, <code>&gt;&gt;&gt;&gt;&gt;&gt;&gt;</code> markers.</li>
        <li>Edit the file to keep the correct content and remove the markers.</li>
        <li>After resolving, click <b>Git Add</b> on the repository form to stage the fixes.</li>
        <li>Then click <b>Git Commit</b> to complete the merge.</li>
    </ol>
    <p>To abort the merge entirely, run <code>git merge --abort</code>
    (or <code>git rebase --abort</code>) in a terminal.</p>
</div>
"""

    def action_open_repository(self):
        """Close wizard and return to the repository form."""
        return {
            "type": "ir.actions.act_window",
            "res_model": "custom.git.repository",
            "res_id": self.repository_id.id,
            "view_mode": "form",
            "target": "current",
        }
