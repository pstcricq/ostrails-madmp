"""madmp store without its variables."""

from madmp.cli import main
from madmp.store.database import ENVIRONMENT


def test_store_names_every_variable_it_lacks(monkeypatch, capsys):
    for name in ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    assert main(["store", "migrate"]) == 1
    assert "FAIL not set: DMP_HOST" in capsys.readouterr().err
