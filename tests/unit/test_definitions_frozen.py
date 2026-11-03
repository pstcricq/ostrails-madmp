"""A version file the revision has, changed or removed, is named, a new one is
not, and nothing else under definitions/ is frozen. Against a git repository
written by the tests."""

import subprocess

import pytest

from madmp.cli import main
from madmp.definitions import KINDS, changed_since
from madmp.definitions.frozen import branch_point, version_files


@pytest.mark.parametrize(
    "name, frozen",
    [
        ("definitions/rules/rda_dcs/1.0.0.json", True),
        ("definitions/projects/glider/1.0.0.yaml", True),
        ("definitions/projects/glider/1.0.0.json", False),
        ("definitions/rules/rules.schema.json", False),
        ("definitions/projects/project.schema.json", False),
    ],
)
def test_every_kind_s_versions_are_frozen_and_nothing_else(name, frozen):
    assert bool(version_files(KINDS).match(name)) is frozen


RULES_FILE = "definitions/rules/rda_dcs/1.0.0.json"
PROJECT_FILE = "definitions/projects/glider/1.0.0.yaml"
SCHEMA_FILE = "definitions/projects/project.schema.json"


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A repository whose first commit publishes one rules file, one project
    version and a schema."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.org")
    _git(tmp_path, "config", "user.name", "t")
    for name, content in (
        (RULES_FILE, "{}"),
        (PROJECT_FILE, "id: glider\n"),
        (SCHEMA_FILE, "{}"),
    ):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "publish")
    return tmp_path


def test_an_untouched_checkout_changed_nothing(repo):
    assert changed_since("HEAD", KINDS, repo) == []


@pytest.mark.parametrize("name", [RULES_FILE, PROJECT_FILE])
def test_an_edited_version_is_named(repo, name):
    (repo / name).write_text("edited")
    assert changed_since("HEAD", KINDS, repo) == [name]


def test_a_removed_version_is_named(repo):
    (repo / PROJECT_FILE).unlink()
    assert changed_since("HEAD", KINDS, repo) == [PROJECT_FILE]


def test_a_new_version_is_how_a_change_arrives(repo):
    (repo / "definitions/projects/glider/1.1.0.yaml").write_text("id: glider\n")
    (repo / "definitions/rules/rda_dcs/1.1.0.json").write_text("{}")
    assert changed_since("HEAD", KINDS, repo) == []


def test_a_schema_is_not_a_version(repo):
    (repo / SCHEMA_FILE).write_text('{"edited": true}')
    assert changed_since("HEAD", KINDS, repo) == []


def test_a_revision_git_cannot_read_is_an_error(repo):
    with pytest.raises(subprocess.CalledProcessError):
        changed_since("no-such-revision", KINDS, repo)


def test_the_command_names_what_changed(repo, monkeypatch, capsys):
    monkeypatch.setattr("madmp.cli.validate.branch_point", lambda base: base)
    monkeypatch.setattr(
        "madmp.cli.validate.changed_since",
        lambda revision, kinds: changed_since(revision, kinds, repo),
    )
    (repo / RULES_FILE).write_text("edited")
    assert main(["validate", "frozen", "--base", "HEAD"]) == 1
    err = capsys.readouterr().err
    assert RULES_FILE in err and "add a new version instead" in err


def test_a_branch_starts_where_it_left_its_base(repo):
    published = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(repo, "branch", "base")
    _git(repo, "switch", "-q", "-c", "change")
    (repo / "definitions/rules/rda_dcs/1.1.0.json").write_text("{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a new version")
    assert branch_point("base", repo) == published


def test_a_commit_the_checkout_holds_is_its_own_branch_point(repo):
    published = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo / "definitions/rules/rda_dcs/1.1.0.json").write_text("{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a new version")
    assert branch_point(published, repo) == published


def test_no_base_no_branch_point(repo):
    assert branch_point("no-such-branch", repo) is None


def test_no_git_no_branch_point(repo, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "git")

    monkeypatch.setattr(subprocess, "run", no_git)
    assert branch_point("main", repo) is None


def test_without_a_revision_the_command_compares_with_the_branch_point(
    repo, monkeypatch, capsys
):
    monkeypatch.setattr("madmp.cli.validate.branch_point", lambda base: "HEAD")
    monkeypatch.setattr(
        "madmp.cli.validate.changed_since",
        lambda revision, kinds: changed_since(revision, kinds, repo),
    )
    (repo / RULES_FILE).write_text("edited")
    assert main(["validate", "frozen"]) == 1
    assert RULES_FILE in capsys.readouterr().err


def test_with_nothing_to_compare_with_the_command_passes(monkeypatch, capsys):
    monkeypatch.setattr("madmp.cli.validate.branch_point", lambda base: None)
    assert main(["validate", "frozen", "--base", "nope"]) == 0
    assert "frozen: nothing to compare with, no nope" in capsys.readouterr().out
