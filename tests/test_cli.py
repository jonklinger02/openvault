"""Tests for OpenVault CLI commands."""

import os
import textwrap
from pathlib import Path

import git
from click.testing import CliRunner

from openvault.cli import main

SAMPLE_STEP = textwrap.dedent("""\
    ISO-10303-21;
    HEADER;
    FILE_DESCRIPTION(('Test bracket'),'2;1');
    FILE_NAME('bracket.step','2024-11-15T10:30:00',('Alice'),
      ('Acme Corp'),'FreeCAD 0.21','FreeCAD STEP exporter','');
    FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
    ENDSEC;
    DATA;
    #1=IFCPROJECT('test');
    ENDSEC;
    END-ISO-10303-21;
""")


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_init_creates_repo(tmp_path):
    runner = CliRunner()
    target = str(tmp_path / "myrepo")
    result = runner.invoke(main, ["init", target])
    assert result.exit_code == 0
    assert "Initialised OpenVault repository" in result.output

    # Verify files were created.
    assert (Path(target) / ".git").is_dir()
    assert (Path(target) / ".gitattributes").exists()
    assert (Path(target) / ".gitignore").exists()

    # Verify .gitattributes content.
    ga = (Path(target) / ".gitattributes").read_text()
    assert "*.stl filter=lfs" in ga
    assert "*.step text" in ga


def test_init_existing_dir(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_path)])
    assert result.exit_code == 0


def test_status_clean(tmp_path):
    """Status in a clean repo."""
    repo = git.Repo.init(str(tmp_path))
    # Need at least one commit for HEAD to exist.
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "clean" in result.output.lower() or "no engineering" in result.output.lower()


def test_status_with_engineering_file(tmp_path):
    """Status shows modified engineering files."""
    repo = git.Repo.init(str(tmp_path))
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    (tmp_path / "bracket.step").write_text(SAMPLE_STEP)

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "bracket.step" in result.output


def test_status_all_flag(tmp_path):
    """--all shows non-engineering files too."""
    repo = git.Repo.init(str(tmp_path))
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    (tmp_path / "notes.txt").write_text("todo")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["status", "--all"])
    assert result.exit_code == 0
    assert "notes.txt" in result.output


def test_commit_with_step_metadata(tmp_path):
    """Commit appends STEP metadata to message."""
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    (tmp_path / "bracket.step").write_text(SAMPLE_STEP)
    repo.index.add(["bracket.step"])

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["commit", "-m", "Add bracket"])
    assert result.exit_code == 0
    assert "Committed" in result.output
    assert "STEP metadata" in result.output

    # Verify the commit message contains metadata.
    last = repo.head.commit
    assert "STEP metadata" in last.message
    assert "bracket.step" in last.message


def test_commit_add_all(tmp_path):
    """commit -a stages engineering files automatically."""
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    (tmp_path / "part.stp").write_text(SAMPLE_STEP)

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["commit", "-a", "-m", "Add part"])
    assert result.exit_code == 0
    assert "Staged 1 engineering file" in result.output


def test_branch_list(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["branch"])
    assert result.exit_code == 0
    # Should show the default branch.
    assert "master" in result.output or "main" in result.output


def test_branch_create(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["branch", "feature/new-part"])
    assert result.exit_code == 0
    assert "Created branch feature/new-part" in result.output


def test_switch_branch(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    repo.create_head("feature/design-review")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["switch", "feature/design-review"])
    assert result.exit_code == 0
    assert "Switched to branch feature/design-review" in result.output
    assert repo.active_branch.name == "feature/design-review"


def test_switch_create(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["switch", "-b", "hotfix/bracket"])
    assert result.exit_code == 0
    assert repo.active_branch.name == "hotfix/bracket"


def test_merge(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    # Create a feature branch with a change.
    feature = repo.create_head("feature/widget")
    feature.checkout()
    (tmp_path / "widget.step").write_text(SAMPLE_STEP)
    repo.index.add(["widget.step"])
    repo.index.commit("Add widget")

    # Switch back to master and merge.
    repo.heads.master.checkout()

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["merge", "feature/widget"])
    assert result.exit_code == 0
    assert "Merged feature/widget" in result.output


def test_history(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    (tmp_path / "bracket.step").write_text(SAMPLE_STEP)
    repo.index.add(["bracket.step"])
    repo.index.commit("Add bracket")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["history"])
    assert result.exit_code == 0
    assert "Add bracket" in result.output
    assert "Initial commit" in result.output


def test_history_step_file_metadata(tmp_path):
    """history <file.step> shows per-commit STEP metadata."""
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    (tmp_path / "bracket.step").write_text(SAMPLE_STEP)
    repo.index.add(["bracket.step"])
    repo.index.commit("Add bracket")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["history", "bracket.step"])
    assert result.exit_code == 0
    assert "bracket.step" in result.output
    # Should show metadata from the STEP header.
    assert "AUTOMOTIVE_DESIGN" in result.output or "Acme" in result.output


def test_diff_no_changes(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (tmp_path / "README.md").write_text("hello")
    repo.index.add(["README.md"])
    repo.index.commit("init")

    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["diff"])
    assert result.exit_code == 0
    assert "No differences" in result.output


def test_not_in_repo(tmp_path):
    """Commands fail gracefully outside a repo."""
    runner = CliRunner()
    os.chdir(str(tmp_path))
    result = runner.invoke(main, ["status"])
    assert result.exit_code != 0
    assert "Not inside" in result.output
