"""madmp store migrate and sync, on the PostgreSQL of the tests."""

import re

from madmp.cli import main
from madmp.definitions import RulesFileError
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


def test_store_sync_copies_the_definitions_once(conn, database, monkeypatch, capsys):
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    monkeypatch.setattr(Database, "from_environment", lambda: database)
    assert main(["store", "migrate"]) == 0
    capsys.readouterr()
    assert main(["store", "sync"]) == 0
    out = capsys.readouterr().out
    assert "rules rda_dcs 1.0.0" in out and "projects glider 1.0.0" in out
    assert re.search(r"\d+ definitions? added\.$", out, re.MULTILINE)
    assert main(["store", "sync"]) == 0
    assert "0 definitions added." in capsys.readouterr().out


def test_store_sync_names_a_definition_that_does_not_load(
    database, monkeypatch, capsys
):
    def broken(conn):
        raise RulesFileError("definitions/rules/x/1.0.0.json", ["no standard"])

    monkeypatch.setattr("madmp.store.sync", broken)
    monkeypatch.setattr(Database, "from_environment", lambda: database)
    assert main(["store", "sync"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAIL ") and "no standard" in err
