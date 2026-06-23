# Copyright (C) 2024-Today
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""Secure local Git operations via subprocess (no shell=True).

Every public method:
- accepts a validated repo_path (checked by _validate_repo)
- calls subprocess.run() with a list of args (never shell=True)
- raises UserError on failure with a clean message
- returns a plain dict  { 'output': str, 'error': str, 'success': bool }
"""

import logging
import os
import subprocess

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GIT_BIN = "git"  # override if git is not in PATH


def _validate_repo(path):
    """Raise UserError if *path* is not a local Git repository.

    Checks:
    - path exists and is a directory
    - path contains a .git entry OR is a bare repo (HEAD file present)
    """
    if not path or not path.strip():
        raise UserError("Repository path is empty. Please configure it first.")
    path = path.strip()
    if not os.path.isdir(path):
        raise UserError(
            "Repository path does not exist or is not a directory:\n%s" % path
        )
    git_dir = os.path.join(path, ".git")
    head_file = os.path.join(path, "HEAD")
    if not os.path.exists(git_dir) and not os.path.isfile(head_file):
        raise UserError(
            "Path is not a Git repository (no .git directory found):\n%s" % path
        )
    return path


def _run(args, cwd, env_extra=None):
    """Execute a git command safely.

    Args:
        args: list of str — the full command including "git" at index 0.
        cwd:  working directory (validated repo path).
        env_extra: optional dict of extra env vars.

    Returns:
        dict with keys: output (str), error (str), success (bool), returncode (int).
    """
    env = os.environ.copy()
    # Avoid interactive prompts
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    if env_extra:
        env.update(env_extra)

    _logger.debug("Running git command: %s in %s", args, cwd)
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        return {
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
            "success": result.returncode == 0,
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        raise UserError(
            "git binary not found. Make sure Git is installed on the server."
        )
    except subprocess.TimeoutExpired:
        raise UserError("Git command timed out after 120 seconds.")
    except Exception as exc:
        _logger.exception("Unexpected error running git: %s", exc)
        raise UserError("Unexpected error running Git: %s" % exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def git_status(repo_path):
    """Run `git status --short --branch`."""
    path = _validate_repo(repo_path)
    return _run([GIT_BIN, "status", "--short", "--branch"], cwd=path)


def git_diff(repo_path, staged=False):
    """Run `git diff` or `git diff --cached` (staged)."""
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "diff"]
    if staged:
        args.append("--cached")
    return _run(args, cwd=path)


def git_log(repo_path, max_count=20, branch=None):
    """Run `git log --oneline -n <max_count>`."""
    path = _validate_repo(repo_path)
    args = [
        GIT_BIN, "log",
        "--oneline",
        "--decorate",
        "-n", str(max_count),
    ]
    if branch:
        args.append(branch)
    return _run(args, cwd=path)


def git_fetch(repo_path, remote="origin"):
    """Run `git fetch <remote>`."""
    path = _validate_repo(repo_path)
    return _run([GIT_BIN, "fetch", remote, "--prune"], cwd=path)


def git_pull(repo_path, remote="origin", branch=None):
    """Run `git pull <remote> [branch]`.

    Detects merge-conflict output in stderr/stdout.
    """
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "pull", remote]
    if branch:
        args.append(branch)
    result = _run(args, cwd=path)
    if not result["success"]:
        combined = (result["output"] + result["error"]).lower()
        if "conflict" in combined or "merge conflict" in combined:
            result["has_conflicts"] = True
        else:
            result["has_conflicts"] = False
    else:
        result["has_conflicts"] = False
    return result


def git_add(repo_path, files=None):
    """Run `git add <files>` or `git add .` if files is empty/None."""
    path = _validate_repo(repo_path)
    if files:
        # files can be a list or a whitespace-separated string
        if isinstance(files, str):
            files = files.split()
        args = [GIT_BIN, "add"] + [f for f in files if f.strip()]
    else:
        args = [GIT_BIN, "add", "."]
    return _run(args, cwd=path)


def git_commit(repo_path, message, author_name=None, author_email=None):
    """Run `git commit -m <message>`."""
    if not message or not message.strip():
        raise UserError("Commit message cannot be empty.")
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "commit", "-m", message.strip()]
    env_extra = {}
    if author_name:
        env_extra["GIT_AUTHOR_NAME"] = author_name
        env_extra["GIT_COMMITTER_NAME"] = author_name
    if author_email:
        env_extra["GIT_AUTHOR_EMAIL"] = author_email
        env_extra["GIT_COMMITTER_EMAIL"] = author_email
    return _run(args, cwd=path, env_extra=env_extra)


def git_push(repo_path, remote="origin", branch=None, force=False):
    """Run `git push [--force] <remote> [branch]`."""
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "push", remote]
    if branch:
        args.append(branch)
    if force:
        args.append("--force-with-lease")  # safer than --force
    return _run(args, cwd=path)


def git_stash(repo_path, message=None):
    """Run `git stash push [-m <message>]`."""
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "stash", "push"]
    if message:
        args += ["-m", message.strip()]
    return _run(args, cwd=path)


def git_stash_pop(repo_path, stash_ref=None):
    """Run `git stash pop [<stash_ref>]`."""
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "stash", "pop"]
    if stash_ref:
        args.append(stash_ref.strip())
    result = _run(args, cwd=path)
    combined = (result["output"] + result["error"]).lower()
    result["has_conflicts"] = "conflict" in combined and not result["success"]
    return result


def git_stash_list(repo_path):
    """Run `git stash list`."""
    path = _validate_repo(repo_path)
    return _run([GIT_BIN, "stash", "list"], cwd=path)


def git_checkout_branch(repo_path, branch_name, create=False):
    """Run `git checkout [-b] <branch_name>`."""
    if not branch_name or not branch_name.strip():
        raise UserError("Branch name cannot be empty.")
    path = _validate_repo(repo_path)
    args = [GIT_BIN, "checkout"]
    if create:
        args.append("-b")
    args.append(branch_name.strip())
    return _run(args, cwd=path)


def get_current_branch(repo_path):
    """Return the current branch name (string) or 'HEAD detached'."""
    try:
        path = _validate_repo(repo_path)
    except UserError:
        return "unknown"
    result = _run([GIT_BIN, "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    if result["success"] and result["output"]:
        return result["output"]
    return "HEAD detached"


def list_local_branches(repo_path):
    """Return list of local branch names."""
    try:
        path = _validate_repo(repo_path)
    except UserError:
        return []
    result = _run(
        [GIT_BIN, "branch", "--format=%(refname:short)"], cwd=path
    )
    if result["success"] and result["output"]:
        return [b.strip() for b in result["output"].splitlines() if b.strip()]
    return []
