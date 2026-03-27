"""OpenVault CLI — Git for engineering files."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click
import git

from openvault import __version__
from openvault.step_parser import is_step_file, parse_step_file

# Engineering file extensions that OpenVault cares about.
ENGINEERING_EXTS = {
    ".step",
    ".stp",
    ".stl",
    ".3mf",
    ".obj",
    ".iges",
    ".igs",
    ".brep",
    ".fcstd",
    ".f3d",
    ".sldprt",
    ".sldasm",
    ".prt",
    ".asm",
    ".ipt",
    ".iam",
    ".catpart",
    ".catproduct",
    ".dxf",
    ".dwg",
}

# Binary formats that should be tracked by LFS.
LFS_EXTS = {".stl", ".3mf", ".obj"}

# Default .gitattributes content for engineering repos.
DEFAULT_GITATTRIBUTES = """\
*.stl filter=lfs diff=lfs merge=lfs -text
*.3mf filter=lfs diff=lfs merge=lfs -text
*.obj filter=lfs diff=lfs merge=lfs -text
# STEP files stay in regular git (text-based)
*.step text
*.stp text
"""

# Default .gitignore additions for engineering repos.
DEFAULT_GITIGNORE_LINES = [
    "# OS files",
    ".DS_Store",
    "Thumbs.db",
    "",
    "# Python",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "",
    "# CAD temp/recovery files",
    "*.bak",
    "*.tmp",
    "~$*",
]


def _find_repo(path: str | None = None) -> git.Repo:
    """Locate the Git repository from *path* or cwd."""
    try:
        return git.Repo(path or os.getcwd(), search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        raise click.ClickException(
            "Not inside an OpenVault (git) repository.  Run 'openvault init' first."
        )


def _is_engineering_file(path: str) -> bool:
    return Path(path).suffix.lower() in ENGINEERING_EXTS


def _step_metadata_lines(path: Path) -> list[str]:
    """Return metadata summary lines for a STEP file, or []."""
    if not is_step_file(path) or not path.exists():
        return []
    try:
        meta = parse_step_file(path)
        d = meta.as_dict()
        if not d:
            return []
        return [f"    {k}: {v}" for k, v in d.items()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__)
def main():
    """OpenVault — Git for engineering files."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@main.command()
@click.argument("directory", default=".", type=click.Path())
@click.option("--bare", is_flag=True, help="Create a bare repository.")
def init(directory: str, bare: bool):
    """Initialise an OpenVault repository.

    Sets up a git repo with engineering-aware .gitattributes (LFS for
    binary CAD formats) and a sensible .gitignore.
    """
    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)

    git.Repo.init(str(target), bare=bare)

    if not bare:
        # .gitattributes
        ga_path = target / ".gitattributes"
        if not ga_path.exists():
            ga_path.write_text(DEFAULT_GITATTRIBUTES)
            click.echo(f"  Created {ga_path.relative_to(target)}")

        # .gitignore
        gi_path = target / ".gitignore"
        if gi_path.exists():
            existing = gi_path.read_text()
        else:
            existing = ""
        additions = [
            line
            for line in DEFAULT_GITIGNORE_LINES
            if line not in existing.splitlines()
        ]
        if additions:
            with gi_path.open("a") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n".join(additions) + "\n")
            click.echo(f"  Updated {gi_path.relative_to(target)}")

    click.echo(
        f"Initialised OpenVault repository in {target}" + (" (bare)" if bare else "")
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--all", "show_all", is_flag=True, help="Show all files, not just engineering."
)
def status(show_all: bool):
    """Show modified engineering files with metadata changes."""
    repo = _find_repo()
    workdir = Path(repo.working_dir)

    # Collect changed files (staged + unstaged + untracked).
    changed: dict[str, str] = {}  # path -> status-label

    # Staged
    for diff in repo.index.diff("HEAD"):
        changed[diff.a_path] = "staged"
    for diff in repo.index.diff("HEAD", R=True):
        if diff.a_path not in changed:
            changed[diff.a_path] = "staged"

    # Unstaged
    for diff in repo.index.diff(None):
        label = changed.get(diff.a_path, "")
        changed[diff.a_path] = "staged+modified" if label == "staged" else "modified"

    # Untracked
    for p in repo.untracked_files:
        changed[p] = "untracked"

    if not changed:
        click.echo("Nothing to report — working tree clean.")
        return

    eng_files = {
        p: s for p, s in changed.items() if show_all or _is_engineering_file(p)
    }
    other_count = len(changed) - len(eng_files)

    if not eng_files and not show_all:
        click.echo(
            f"No engineering files changed ({other_count} other file(s) modified)."
        )
        return

    click.echo("Engineering files:" if not show_all else "All changed files:")
    for p, s in sorted(eng_files.items()):
        click.echo(f"  [{s:>16}]  {p}")
        for line in _step_metadata_lines(workdir / p):
            click.echo(line)

    if other_count and not show_all:
        click.echo(f"\n  ({other_count} non-engineering file(s) also changed)")


# ---------------------------------------------------------------------------
# commit
# ---------------------------------------------------------------------------


@main.command()
@click.option("-m", "--message", required=True, help="Commit message.")
@click.option(
    "-a",
    "--add-all",
    is_flag=True,
    help="Stage all modified engineering files before committing.",
)
def commit(message: str, add_all: bool):
    """Commit with auto-extracted STEP metadata in the message."""
    repo = _find_repo()
    workdir = Path(repo.working_dir)

    if add_all:
        # Stage all modified/untracked engineering files.
        changed = [d.a_path for d in repo.index.diff(None)] + list(repo.untracked_files)
        eng = [p for p in changed if _is_engineering_file(p)]
        if eng:
            repo.index.add(eng)
            click.echo(f"Staged {len(eng)} engineering file(s).")

    # Collect STEP metadata from staged files.
    staged_paths = [d.a_path for d in repo.index.diff("HEAD")]
    # Also include newly added files.
    try:
        staged_paths += [d.a_path for d in repo.index.diff("HEAD", R=True)]
    except Exception:
        pass
    meta_lines: list[str] = []
    seen: set[str] = set()
    for p in staged_paths:
        if p in seen:
            continue
        seen.add(p)
        full = workdir / p
        if is_step_file(full) and full.exists():
            try:
                meta = parse_step_file(full)
                summary = meta.summary()
                if summary != "(no metadata)":
                    meta_lines.append(f"  {p}: {summary}")
            except Exception:
                pass

    full_message = message
    if meta_lines:
        full_message += "\n\nSTEP metadata:\n" + "\n".join(meta_lines)

    try:
        repo.index.commit(full_message)
    except Exception as exc:
        raise click.ClickException(f"Commit failed: {exc}")

    click.echo(f"Committed: {message}")
    if meta_lines:
        click.echo("STEP metadata appended to commit message.")


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


@main.command()
@click.option("--remote", default="origin", help="Remote name.")
@click.option("--branch", default=None, help="Branch to push (default: current).")
@click.option(
    "--set-upstream",
    "-u",
    is_flag=True,
    help="Set upstream tracking reference.",
)
def push(remote: str, branch: str | None, set_upstream: bool):
    """Push commits to remote (LFS-aware)."""
    repo = _find_repo()
    branch = branch or repo.active_branch.name

    cmd = ["git", "push"]
    if set_upstream:
        cmd += ["-u"]
    cmd += [remote, branch]

    result = subprocess.run(cmd, cwd=repo.working_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise click.ClickException(f"Push failed:\n{result.stderr.strip()}")

    click.echo(f"Pushed {branch} to {remote}.")
    if result.stdout.strip():
        click.echo(result.stdout.strip())


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


@main.command()
@click.option("--remote", default="origin", help="Remote name.")
@click.option("--branch", default=None, help="Branch to pull (default: current).")
def pull(remote: str, branch: str | None):
    """Pull from remote (LFS-aware)."""
    repo = _find_repo()
    branch = branch or repo.active_branch.name

    cmd = ["git", "pull", remote, branch]
    result = subprocess.run(cmd, cwd=repo.working_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise click.ClickException(f"Pull failed:\n{result.stderr.strip()}")

    click.echo(f"Pulled {branch} from {remote}.")
    if result.stdout.strip():
        click.echo(result.stdout.strip())


# ---------------------------------------------------------------------------
# branch
# ---------------------------------------------------------------------------


@main.command()
@click.argument("name", required=False)
@click.option("--list", "list_branches", is_flag=True, help="List all branches.")
@click.option("-d", "--delete", "delete_branch", is_flag=True, help="Delete branch.")
def branch(name: str | None, list_branches: bool, delete_branch: bool):
    """Create, list, or delete branches for design reviews."""
    repo = _find_repo()

    if list_branches or name is None:
        active = repo.active_branch.name
        for b in repo.branches:
            marker = "* " if b.name == active else "  "
            click.echo(f"{marker}{b.name}")
        return

    if delete_branch:
        if name == repo.active_branch.name:
            raise click.ClickException("Cannot delete the currently active branch.")
        repo.delete_head(name, force=False)
        click.echo(f"Deleted branch {name}.")
        return

    repo.create_head(name)
    click.echo(f"Created branch {name}.")


# ---------------------------------------------------------------------------
# checkout (switch branch)
# ---------------------------------------------------------------------------


@main.command("switch")
@click.argument("name")
@click.option("-b", "--create", is_flag=True, help="Create and switch to new branch.")
def switch(name: str, create: bool):
    """Switch to a branch (create with -b)."""
    repo = _find_repo()

    if create:
        branch_ref = repo.create_head(name)
    else:
        try:
            branch_ref = repo.heads[name]
        except IndexError:
            raise click.ClickException(f"Branch '{name}' does not exist.")

    branch_ref.checkout()
    click.echo(f"Switched to branch {name}.")


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


@main.command()
@click.argument("source")
@click.option(
    "--no-ff", is_flag=True, help="Create a merge commit even for fast-forwards."
)
def merge(source: str, no_ff: bool):
    """Merge a branch into the current branch."""
    repo = _find_repo()
    current = repo.active_branch.name

    cmd = ["git", "merge"]
    if no_ff:
        cmd.append("--no-ff")
    cmd.append(source)

    result = subprocess.run(cmd, cwd=repo.working_dir, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stdout.strip() or result.stderr.strip()
        raise click.ClickException(f"Merge failed:\n{msg}")

    click.echo(f"Merged {source} into {current}.")


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@main.command()
@click.argument("file", required=False, type=click.Path())
@click.option("-n", "--max-count", default=10, help="Number of commits to show.")
def history(file: str | None, max_count: int):
    """Show file history with extracted STEP metadata per commit."""
    repo = _find_repo()

    kwargs: dict = {"max_count": max_count}
    if file:
        kwargs["paths"] = file

    commits = list(repo.iter_commits(**kwargs))
    if not commits:
        click.echo("No commits found.")
        return

    for c in commits:
        short = str(c)[:8]
        date = c.committed_datetime.strftime("%Y-%m-%d %H:%M")
        click.echo(f"{short}  {date}  {c.summary}")

        # If filtering to a specific STEP file, show metadata at that commit.
        if file and is_step_file(file):
            try:
                blob = c.tree / file
                content = blob.data_stream.read().decode("utf-8", errors="replace")[
                    :32768
                ]
                from openvault.step_parser import parse_step_header

                meta = parse_step_header(content)
                d = meta.as_dict()
                if d:
                    for k, v in d.items():
                        click.echo(f"           {k}: {v}")
            except (KeyError, Exception):
                pass


# ---------------------------------------------------------------------------
# diff (bonus: engineering-aware diff summary)
# ---------------------------------------------------------------------------


@main.command()
@click.argument("path", required=False, type=click.Path())
@click.option("--staged", is_flag=True, help="Show staged changes.")
def diff(path: str | None, staged: bool):
    """Show engineering-file diff summary with metadata changes."""
    repo = _find_repo()

    if staged:
        diffs = repo.index.diff("HEAD")
    else:
        diffs = repo.index.diff(None)

    if not diffs:
        click.echo("No differences found.")
        return

    for d in diffs:
        if path and d.a_path != path:
            continue
        if not _is_engineering_file(d.a_path):
            continue

        change_type = d.change_type or "M"
        click.echo(f"  [{change_type}] {d.a_path}")

        if is_step_file(d.a_path):
            workdir = Path(repo.working_dir)
            for line in _step_metadata_lines(workdir / d.a_path):
                click.echo(line)


if __name__ == "__main__":
    main()
