# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Local Git Operations model.

Extends custom.git.repository with local-path-based Git operations:
Status, Diff, Stash, Stash Pop, Stash List, Pull, Add, Commit,
Push, Fetch, Checkout Branch, Log.

All operations:
- use secure subprocess calls (no shell=True) via services/local_git.py
- automatically detect and display the current branch
- log output to the chatter (mail.thread)
- restrict execution to git_admin group
- handle merge conflicts with a dedicated warning
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import local_git as lgit

_logger = logging.getLogger(__name__)


class CustomGitRepository(models.Model):
    """Extend git repository with local-path Git operations."""

    _inherit = "custom.git.repository"

    # ------------------------------------------------------------------
    # Local path configuration
    # ------------------------------------------------------------------

    local_path = fields.Char(
        string="Local Repository Path",
        help="Absolute path to the local Git clone on the server "
             "(e.g. /opt/odoo/myproject). Required for local Git operations.",
    )

    current_branch = fields.Char(
        string="Current Branch",
        compute="_compute_current_branch",
        store=False,
        help="Auto-detected from the local repository.",
    )

    last_operation_output = fields.Text(
        string="Last Operation Output",
        readonly=True,
        help="Stdout/stderr of the last local Git operation.",
    )

    last_operation = fields.Char(
        string="Last Operation",
        readonly=True,
    )

    has_conflict = fields.Boolean(
        string="Merge Conflict Detected",
        readonly=True,
        default=False,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends("local_path")
    def _compute_current_branch(self):
        for rec in self:
            if rec.local_path:
                rec.current_branch = lgit.get_current_branch(rec.local_path)
            else:
                rec.current_branch = "—"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_git_admin(self):
        """Raise if the current user is not a Git Administrator."""
        if not self.env.user.has_group("custom_git.group_git_admin"):
            raise UserError(
                "You need Git Administrator access to perform local Git operations."
            )

    def _require_local_path(self):
        """Raise if local_path is not configured."""
        self.ensure_one()
        if not self.local_path or not self.local_path.strip():
            raise UserError(
                "No local repository path configured. "
                "Please set the 'Local Repository Path' field on this repository."
            )

    def _post_result(self, operation, result):
        """Store output and post to chatter.

        Args:
            operation: short label for the operation (e.g. 'Git Status')
            result: dict from lgit._run()
        """
        output_parts = []
        if result.get("output"):
            output_parts.append(result["output"])
        if result.get("error") and not result["success"]:
            output_parts.append("STDERR:\n" + result["error"])
        full_output = "\n".join(output_parts) or "(no output)"

        self.write(
            {
                "last_operation": operation,
                "last_operation_output": full_output,
                "has_conflict": result.get("has_conflicts", False),
            }
        )

        if result["success"]:
            icon = "✅"
            status_word = "succeeded"
        else:
            icon = "❌"
            status_word = "failed"

        conflict_note = ""
        if result.get("has_conflicts"):
            conflict_note = (
                "<br/><b>⚠️ MERGE CONFLICTS DETECTED.</b> "
                "Resolve conflicts manually, then run Git Add + Git Commit."
            )

        body = (
            "<b>%s %s — %s</b>%s"
            "<pre style='background:#f5f5f5;padding:8px;font-size:12px;"
            "border-radius:4px;white-space:pre-wrap;'>%s</pre>"
            % (
                icon,
                operation,
                status_word,
                conflict_note,
                full_output,
            )
        )
        self.message_post(body=body)

        # Re-compute branch after any write operation
        self.invalidate_recordset(["current_branch"])

    # ------------------------------------------------------------------
    # Git Status
    # ------------------------------------------------------------------

    def action_git_status(self):
        """Show working tree status."""
        self._check_git_admin()
        self._require_local_path()
        result = lgit.git_status(self.local_path)
        self._post_result("Git Status", result)
        return self._reload_action()

    # ------------------------------------------------------------------
    # Git Diff
    # ------------------------------------------------------------------

    def action_git_diff(self):
        """Open the diff wizard (unstaged changes)."""
        self._check_git_admin()
        self._require_local_path()
        return {
            "type": "ir.actions.act_window",
            "name": "Git Diff",
            "res_model": "git.local.diff.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Git Log
    # ------------------------------------------------------------------

    def action_git_log(self):
        """Show recent commit log."""
        self._check_git_admin()
        self._require_local_path()
        result = lgit.git_log(self.local_path, max_count=30)
        self._post_result("Git Log", result)
        return self._reload_action()

    # ------------------------------------------------------------------
    # Git Fetch
    # ------------------------------------------------------------------

    def action_git_fetch(self):
        """Fetch from origin (no merge)."""
        self._check_git_admin()
        self._require_local_path()
        result = lgit.git_fetch(self.local_path)
        self._post_result("Git Fetch", result)
        return self._reload_action()

    # ------------------------------------------------------------------
    # Git Pull
    # ------------------------------------------------------------------

    def action_git_pull(self):
        """Pull from origin / current branch. Detects merge conflicts."""
        self._check_git_admin()
        self._require_local_path()
        branch = lgit.get_current_branch(self.local_path)
        result = lgit.git_pull(self.local_path, branch=branch)
        self._post_result("Git Pull", result)
        if result.get("has_conflicts"):
            return {
                "type": "ir.actions.act_window",
                "name": "Merge Conflict Detected",
                "res_model": "git.conflict.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_repository_id": self.id},
            }
        return self._reload_action()

    # ------------------------------------------------------------------
    # Git Add
    # ------------------------------------------------------------------

    def action_git_add(self):
        """Open the Git Add wizard (choose files or add all)."""
        self._check_git_admin()
        self._require_local_path()
        return {
            "type": "ir.actions.act_window",
            "name": "Git Add",
            "res_model": "git.local.add.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Git Commit
    # ------------------------------------------------------------------

    def action_git_commit(self):
        """Open the Git Commit wizard."""
        self._check_git_admin()
        self._require_local_path()
        return {
            "type": "ir.actions.act_window",
            "name": "Git Commit",
            "res_model": "git.local.commit.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Git Push
    # ------------------------------------------------------------------

    def action_git_push(self):
        """Open the Git Push wizard."""
        self._check_git_admin()
        self._require_local_path()
        return {
            "type": "ir.actions.act_window",
            "name": "Git Push",
            "res_model": "git.local.push.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Git Stash
    # ------------------------------------------------------------------

    def action_git_stash(self):
        """Open the Git Stash wizard."""
        self._check_git_admin()
        self._require_local_path()
        return {
            "type": "ir.actions.act_window",
            "name": "Git Stash",
            "res_model": "git.local.stash.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Git Stash Pop
    # ------------------------------------------------------------------

    def action_git_stash_pop(self):
        """Pop the most recent stash entry."""
        self._check_git_admin()
        self._require_local_path()
        result = lgit.git_stash_pop(self.local_path)
        self._post_result("Git Stash Pop", result)
        if result.get("has_conflicts"):
            return {
                "type": "ir.actions.act_window",
                "name": "Stash Pop Conflict",
                "res_model": "git.conflict.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_repository_id": self.id},
            }
        return self._reload_action()

    # ------------------------------------------------------------------
    # Git Stash List
    # ------------------------------------------------------------------

    def action_git_stash_list(self):
        """Show stash list."""
        self._check_git_admin()
        self._require_local_path()
        result = lgit.git_stash_list(self.local_path)
        self._post_result("Git Stash List", result)
        return self._reload_action()

    # ------------------------------------------------------------------
    # Git Checkout Branch
    # ------------------------------------------------------------------

    def action_git_checkout_branch(self):
        """Open the branch checkout wizard."""
        self._check_git_admin()
        self._require_local_path()
        return {
            "type": "ir.actions.act_window",
            "name": "Git Checkout Branch",
            "res_model": "git.local.checkout.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repository_id": self.id},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reload_action(self):
        """Reload the current form so updated output fields are visible.

        Returning the 'reload' client action forces the web client to
        re-fetch the record from the server, making last_operation_output
        and the chatter appear immediately without a manual page refresh.
        """
        return {"type": "ir.actions.client", "tag": "reload"}
