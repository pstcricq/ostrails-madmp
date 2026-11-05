"""The tables of the DMP database and what they refuse on their own, on the
PostgreSQL of the tests."""

import psycopg
import pytest
from psycopg.types.json import Jsonb

TABLES = [
    "dmp_versions",
    "dmps",
    "project_rules",
    "project_versions",
    "projects",
    "rules",
    "schema_versions",
]


@pytest.fixture
def filled(conn):
    """One rules file, one project at one version pinning it, its template
    DMP at version 1."""
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
    conn.execute(
        "INSERT INTO dmps (key, project_id, kind) "
        "VALUES ('o-p-template', 'p', 'template')"
    )
    _version(conn, 1)
    return conn


def _version(conn, version, source="writer", key="o-p-template"):
    conn.execute(
        "INSERT INTO dmp_versions (dmp_key, version, project_id, project_version, "
        "document, assessment, source) "
        "VALUES (%s, %s, 'p', '1.0.0', %s, %s, %s)",
        (key, version, Jsonb({}), Jsonb({}), source),
    )


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
        ("dmp_versions", "document"),
    ],
)
def test_a_frozen_row_is_never_updated(filled, table, column):
    with pytest.raises(psycopg.errors.RaiseException, match="never updated"):
        filled.execute(f"UPDATE {table} SET {column} = {column}")


def test_a_dmp_version_can_be_deleted(filled):
    filled.execute("DELETE FROM dmp_versions")
    assert filled.execute("SELECT count(*) FROM dmp_versions").fetchone()[0] == 0


def test_a_version_number_is_taken_once(filled):
    with pytest.raises(psycopg.errors.UniqueViolation):
        _version(filled, 1)


def test_a_project_has_one_template(filled):
    with pytest.raises(psycopg.errors.UniqueViolation):
        filled.execute(
            "INSERT INTO dmps (key, project_id, kind) "
            "VALUES ('o-p-other', 'p', 'template')"
        )


@pytest.mark.parametrize("source", ["", "Not a name", "x" * 65])
def test_what_wrote_a_version_is_a_name(filled, source):
    with pytest.raises(psycopg.errors.CheckViolation):
        _version(filled, 2, source=source)


def test_a_version_produced_from_a_project_version_never_synced_is_refused(filled):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        filled.execute(
            "INSERT INTO dmp_versions (dmp_key, version, project_id, project_version, "
            "document, assessment, source) "
            "VALUES ('o-p-template', 2, 'p', '9.9.9', '{}', '{}', 'api')"
        )


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
