"""madmp store migrate, on the PostgreSQL of the tests."""

from madmp.cli import main
from madmp.store import Database


def test_store_migrate_applies_what_the_database_lacks(
    conn, database, monkeypatch, capsys
):
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    monkeypatch.setattr(Database, "from_environment", lambda: database)
    assert main(["store", "migrate"]) == 0
    out = capsys.readouterr().out
    assert "001_init.sql" in out and "1 migration applied." in out
    assert main(["store", "migrate"]) == 0
    assert "0 migrations applied." in capsys.readouterr().out
