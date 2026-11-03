"""The tables of the DMP database and what they refuse on their own, on the
PostgreSQL of the tests."""

import psycopg
import pytest
from psycopg.types.json import Jsonb

TABLES = [
    "project_rules",
    "project_versions",
    "projects",
    "rules",
    "schema_versions",
]


@pytest.fixture
def filled(conn):
    """One rules file, and one project at one version pinning it."""
    conn.execute(
        "INSERT INTO rules (standard, version, content) VALUES ('base', '1.0.0', %s)",
        (Jsonb({"standard": "base"}),),
    )
    conn.execute("INSERT INTO projects (id) VALUES ('p')")
    conn.execute(
        "INSERT INTO project_versions (project_id, version, content) "
        "VALUES ('p', '1.0.0', %s)",
        (Jsonb({"id": "p"}),),
    )
    conn.execute("INSERT INTO project_rules VALUES ('p', '1.0.0', 1, 'base', '1.0.0')")
    return conn


def test_the_migrations_create_every_table(conn):
    rows = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
    )
    assert [row[0] for row in rows] == TABLES


@pytest.mark.parametrize(
    "table, column",
    [
        ("rules", "content"),
        ("project_versions", "content"),
        ("project_rules", "position"),
    ],
)
def test_a_frozen_row_is_never_updated(filled, table, column):
    with pytest.raises(psycopg.errors.RaiseException, match="never updated"):
        filled.execute(f"UPDATE {table} SET {column} = {column}")


def test_a_version_of_a_project_never_added_is_refused(filled):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        filled.execute(
            "INSERT INTO project_versions (project_id, version, content) "
            "VALUES ('q', '1.0.0', '{}')"
        )


def test_pins_name_rules_files_that_are_there(filled):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        filled.execute(
            "INSERT INTO project_rules VALUES ('p', '1.0.0', 2, 'ext', '1.0.0')"
        )
