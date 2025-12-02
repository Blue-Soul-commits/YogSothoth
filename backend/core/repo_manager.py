from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .models import Repo


class RepoManager:
    """Manages local clones of Git repositories.

    This class knows where repositories are stored on disk and is
    responsible for cloning and updating them. The actual git
    integration will be implemented in later iterations.
    """

    def __init__(self, root_dir: Path) -> None:
        # Root directory where all git repositories will be stored.
        # We do not create it lazily to fail fast on permission issues.
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, repo_id: str) -> Path:
        """Return the local path for a given repo id."""

        return self.root_dir / repo_id

    def clone_or_update(self, repo: Repo, branch: Optional[str] = None) -> Path:
        """Clone a new repo or update an existing one using the local `git` CLI.

        - If the repo path does not exist, a fresh clone is performed.
        - If it exists, a `git fetch` + `git checkout` + `git pull` is executed.

        The resolved local path is also assigned to ``repo.local_path``.
        """

        repo_path = self.get_repo_path(repo.id)
        target_branch = branch or repo.default_branch or "main"

        # Perform a fresh clone if needed.
        if not repo_path.exists():
            # Fresh clone into a directory named after the repo id.
            # We run git with cwd at the root_dir and use a relative
            # target directory to avoid accidentally nesting root_dir
            # inside itself (which would happen if we passed the full
            # repo_path while also using root_dir as cwd).
            self._run_git(
                [
                    "git",
                    "clone",
                    "--origin",
                    "origin",
                    repo.git_url,
                    repo.id,
                ],
                cwd=self.root_dir,
            )
        else:
            # Existing clone: make sure it's a git repo and update it
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                raise RuntimeError(
                    f"Expected {repo_path} to be a git repository (missing .git)."
                )

            # Fetch latest refs
            self._run_git(["git", "fetch", "origin"], cwd=repo_path)

        # Ensure we are on the desired branch and up to date.
        # Some older repositories still use `master` as the default
        # branch name; if checkout of `main` fails we fall back to
        # `master` automatically.
        try:
            self._run_git(["git", "checkout", target_branch], cwd=repo_path)
        except RuntimeError:
            if target_branch != "master":
                fallback_branch = "master"
                self._run_git(
                    ["git", "checkout", fallback_branch],
                    cwd=repo_path,
                )
                target_branch = fallback_branch
            else:
                # If even the requested branch is `master`, re-raise.
                raise

        self._run_git(["git", "pull", "origin", target_branch], cwd=repo_path)

        repo.local_path = repo_path
        return repo_path

    def _run_git(self, args: list[str], cwd: Path) -> None:
        """Run a git command and raise a helpful error on failure."""

        result = subprocess.run(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            cmd = " ".join(args)
            raise RuntimeError(
                f"Git command failed ({cmd}) in {cwd}:\n{result.stderr.strip()}"
            )
