# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Custom Git Manager",
    "version": "19.0.2.0.0",
    "category": "Tools/Git",
    "summary": (
        "Branch-based GitHub commit tracking + local Git operations "
        "(status, diff, log, add, commit, push, pull, fetch, stash, checkout)"
    ),
    "author": "Custom",
    "license": "AGPL-3",
    "depends": [
        "base",
        "mail",
    ],
    "external_dependencies": {
        "python": ["github"],   # PyGithub — for remote GitHub API operations
    },
    "data": [
        # Security — load first
        "security/security.xml",
        "security/ir.model.access.csv",
        # Core repository / branch / commit views
        "views/git_repository_views.xml",
        "views/git_branch_views.xml",
        "views/git_commit_views.xml",
        "views/git_commit_file_views.xml",
        # Local Git operations (extends repository form)
        "views/git_local_ops_views.xml",
        # Wizard views for all local Git operations
        "views/git_wizard_views.xml",
        # Menus
        "views/git_menu.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
