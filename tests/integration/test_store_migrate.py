"""The migrations the package carries, applied once per database, on the
PostgreSQL of the tests."""

import pytest

from madmp.errors import StoreError
from madmp.store import migrate, pending
from madmp.store.migrate import migrations


def _empty(conn):
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")


def test_an_empty_database_gets_every_migration_once(conn):
    _empty(conn)
    assert migrate(conn) == [name for _, name, _ in migrations()]
    applied = conn.execute("SELECT name FROM schema_versions ORDER BY number")
    assert [row[0] for row in applied] == [name for _, name, _ in migrations()]


def test_migrating_again_applies_nothing(conn):
    assert migrate(conn) == []


def test_a_migrated_database_has_nothing_pending(conn):
    assert pending(conn) == []


def test_a_database_never_migrated_has_everything_pending(conn):
    _empty(conn)
    assert pending(conn) == [name for _, name, _ in migrations()]


def test_a_database_migrated_by_a_newer_version_is_refused(conn):
    conn.execute("INSERT INTO schema_versions (number, name) VALUES (999, '999_x.sql')")
    with pytest.raises(StoreError, match="999"):
        migrate(conn)
