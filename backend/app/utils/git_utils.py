import os
import subprocess
from typing import List, Optional


def _repo_root() -> str:
    """Return absolute repository root path based on this file location."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def is_git_repo(path: Optional[str] = None) -> bool:
    root = path or _repo_root()
    return os.path.isdir(os.path.join(root, ".git"))


def git_auto_commit(files: List[str], message: str) -> bool:
    """Best-effort: add and commit the specified files to git.
    Returns True on success, False if git is unavailable or commit fails.
    """
    try:
        root = _repo_root()
        if not is_git_repo(root):
            return False
        # Normalize file paths relative to repo root
        rel_files = []
        for f in files:
            if not f:
                continue
            try:
                absf = os.path.abspath(f)
                # Ensure path is inside repo
                if absf.startswith(root):
                    rel_files.append(os.path.relpath(absf, root))
                else:
                    # Use absolute path but git may still accept it
                    rel_files.append(absf)
            except Exception:
                rel_files.append(f)
        # git add
        add_cmd = ["git", "add", "--"] + rel_files
        subprocess.run(add_cmd, cwd=root, check=False, capture_output=True)
        # git commit
        commit_cmd = ["git", "commit", "-m", message]
        res = subprocess.run(commit_cmd, cwd=root, check=False, capture_output=True)
        return res.returncode == 0
    except Exception:
        return False
