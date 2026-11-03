"""madmp validate on the definitions of the repository and on files written for a test, the steps it runs, in which order, the lines it prints and its exit code."""

import re

import pytest

from madmp.cli import main
from madmp.definitions import KINDS, RULES, files


def test_validate_all_runs_every_step_and_says_each(capsys):
    assert main(["validate", "all"]) == 0
    out = capsys.readouterr().out
    for kind in KINDS:
        assert re.search(rf"^{kind.name}: \d+ files? valid\.$", out, re.MULTILINE)


@pytest.mark.parametrize("step", [kind.name for kind in KINDS])
def test_validate_runs_one_step(step, capsys):
    assert main(["validate", step]) == 0
    assert capsys.readouterr().out.count("\n\n") == 1


def test_validate_all_stops_at_the_first_step_that_fails(monkeypatch, capsys):
    monkeypatch.setattr("madmp.cli.validate.files", lambda kind: [])
    assert main(["validate", "all"]) == 1
    captured = capsys.readouterr()
    assert "rules: no file found" in captured.err
    assert "projects" not in captured.out + captured.err


def test_validate_names_its_step(capsys):
    with pytest.raises(SystemExit) as refused:
        main(["validate"])
    assert refused.value.code == 2
    assert "all" in capsys.readouterr().err


def test_validate_fails_with_no_file(monkeypatch, capsys):
    monkeypatch.setattr("madmp.cli.validate.files", lambda kind: [])
    assert main(["validate", "rules"]) == 1
    assert "rules: no file found" in capsys.readouterr().err


def test_a_rejected_file_is_named(monkeypatch, tmp_path, capsys):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "1.0.0.json").write_text("{}")
    monkeypatch.setattr("madmp.cli.validate.files", lambda kind: files(kind, tmp_path))
    assert main(["validate", "rules"]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err and "broken/1.0.0.json" in err
    assert "rules: 1 of 1 file rejected." in err


def test_every_file_is_listed(capsys):
    assert main(["validate", "rules"]) == 0
    out = capsys.readouterr().out
    assert out.count("ok   ") == len(files(RULES))
