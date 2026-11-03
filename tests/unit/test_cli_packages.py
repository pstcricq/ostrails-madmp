"""madmp packages generate, with and without --out."""

import re

from madmp.cli import main
from madmp.definitions import PROJECTS, files, load


def test_generate_builds_every_version_and_writes_nothing(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    assert main(["packages", "generate"]) == 0
    out = capsys.readouterr().out
    paths = files(PROJECTS)
    for path in paths:
        definition = load(PROJECTS, path)
        assert f"ok   {definition['id']} {definition['version']} : " in out
    assert re.search(r"^packages: \d+ project versions? built\.$", out, re.MULTILINE)
    assert list(tmp_path.iterdir()) == []


def test_generate_writes_both_packages_with_out(tmp_path, capsys):
    out_dir = tmp_path / "packages"
    assert main(["packages", "generate", "--out", str(out_dir)]) == 0
    expected = set()
    for path in files(PROJECTS):
        definition = load(PROJECTS, path)
        name = f"{definition['id']}_{definition['version']}"
        expected |= {f"{name}_km.km", f"{name}_template.json"}
    assert {p.name for p in out_dir.iterdir()} == expected
    out = capsys.readouterr().out
    assert all(name in out for name in expected)
    assert f"built, written into {out_dir}." in out


def test_a_project_that_does_not_load_is_not_generated(tmp_path, capsys):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "1.0.0.yaml").write_text("id: broken\n")
    assert main(["packages", "generate", str(tmp_path / "broken")]) == 1
    err = capsys.readouterr().err
    assert "SKIP" in err and "broken/1.0.0.yaml" in err
    assert "packages: 1 of 1 project version not built." in err
