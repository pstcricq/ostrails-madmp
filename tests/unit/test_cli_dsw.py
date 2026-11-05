"""madmp dsw publish and submission without their values."""

from madmp.cli import main


def test_publish_names_every_value_it_lacks(monkeypatch, capsys):
    for name in ("DSW_API_URL", "DSW_USER", "DSW_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    assert main(["dsw", "publish"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAIL 3 publish problem(s):")
    assert "DSW_PASSWORD is not set" in err


def test_submission_names_every_value_it_lacks(monkeypatch, capsys):
    for name in ("SUBMISSION_URL", "TEMPLATE_WRITE_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    assert main(["dsw", "submission"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAIL 2 publish problem(s):")
    assert "SUBMISSION_URL is not set" in err
