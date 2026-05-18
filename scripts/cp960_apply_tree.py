"""CP9.60 — apply an unzipped tree into the live working tree with backup discipline.

Usage:
    python scripts/cp960_apply_tree.py <source_tree> <dest_tree>

For every file under <source_tree>:
  - If the same relative path exists under <dest_tree> AND is tracked by git:
        backup current dest copy to _backup/<rel-dir>/<fname>_YYYYMMDD-HHMM.ext
        then overwrite with source copy
  - If exists but untracked:                       overwrite without backup
  - If does NOT exist:                             create new

Prints a per-file action manifest.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def is_tracked(repo_root: Path, rel_path: Path) -> bool:
    """Return True if the relative path is tracked by git."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel_path).replace("\\", "/")],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/cp960_apply_tree.py <source_tree> <dest_tree>")
        return 2

    source = Path(sys.argv[1]).resolve()
    dest = Path(sys.argv[2]).resolve()

    if not source.is_dir():
        print(f"ERROR: source {source} is not a directory")
        return 2
    if not dest.is_dir():
        print(f"ERROR: dest {dest} is not a directory")
        return 2

    # Find git repo root
    repo_root = dest
    while repo_root != repo_root.parent and not (repo_root / ".git").is_dir():
        repo_root = repo_root.parent
    if not (repo_root / ".git").is_dir():
        print(f"ERROR: no .git found at or above {dest}")
        return 2

    ts = datetime.now().strftime("%Y%m%d-%H%M")

    backed_up = []
    overwritten_untracked = []
    new_files = []
    errors = []

    for source_path in source.rglob("*"):
        if not source_path.is_file():
            continue
        rel = source_path.relative_to(source)
        dest_path = dest / rel
        rel_from_repo = dest_path.relative_to(repo_root)

        try:
            if dest_path.exists():
                if is_tracked(repo_root, rel_from_repo):
                    # Backup
                    backup_dir = repo_root / "_backup" / rel.parent
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    name = dest_path.stem + "_" + ts + dest_path.suffix
                    backup_path = backup_dir / name
                    shutil.copy2(dest_path, backup_path)
                    backed_up.append(str(rel_from_repo))
                else:
                    overwritten_untracked.append(str(rel_from_repo))
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                new_files.append(str(rel_from_repo))

            shutil.copy2(source_path, dest_path)
        except Exception as exc:  # noqa: BLE001
            errors.append((str(rel_from_repo), str(exc)))

    print(f"=== CP9.60 apply manifest (ts={ts}) ===")
    print(f"source: {source}")
    print(f"dest:   {dest}")
    print(f"backed_up (tracked, overwritten):  {len(backed_up)}")
    for p in backed_up:
        print(f"  BACKUP+OVERWRITE: {p}")
    print(f"overwritten_untracked (no backup): {len(overwritten_untracked)}")
    for p in overwritten_untracked:
        print(f"  OVERWRITE-UNTRACKED: {p}")
    print(f"new_files (created):               {len(new_files)}")
    for p in new_files:
        print(f"  NEW: {p}")
    if errors:
        print(f"ERRORS: {len(errors)}")
        for p, e in errors:
            print(f"  ERROR {p}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
