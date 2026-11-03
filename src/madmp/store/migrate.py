"""The DMP database brought to this package's schema: the files
``migrations/NNN_<name>.sql`` in order, each recorded in ``schema_versions``,
in one transaction behind an advisory lock. A database holding a migration
this package lacks is refused.
"""

from __future__ import annotations

import re
from importlib import resources

import psycopg

from madmp.errors import StoreError

# The name a migration file has: its number, then what it does.
MIGRATION = re.compile(r"^(?P<number>[0-9]{3})_[a-z0-9_]+\.sql$")

# The key of the advisory lock taken while migrating, any number no other
# client of this database uses.
LOCK = 4_242_001

_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_versions (
    number      integer PRIMARY KEY,
    name        text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""


def migrations() -> list[tuple[int, str, str]]:
    """Every migration of this package, as (number, file name, SQL), in the
    order they apply. Two files with the same number are refused."""
    found: dict[int, tuple[str, str]] = {}
    for entry in resources.files("madmp.store").joinpath("migrations").iterdir():
        match = MIGRATION.match(entry.name)
        if not match:
            continue
        number = int(match["number"])
        if number in found:
            raise StoreError(
                f"two migrations numbered {number:03}: "
                f"{found[number][0]} and {entry.name}"
            )
        found[number] = (entry.name, entry.read_text())
    return [(number, *found[number]) for number in sorted(found)]


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply the migrations this database has not had, and return their file
    names, empty when it was up to date."""
    known = migrations()
    applied_now: list[str] = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
        conn.execute(_SCHEMA_VERSION)
        applied = {row[0] for row in conn.execute("SELECT number FROM schema_versions")}
        unknown = sorted(applied - {number for number, _, _ in known})
        if unknown:
            raise StoreError(
                "the database has migration(s) "
                f"{', '.join(f'{n:03}' for n in unknown)}, which this version of "
                "madmp does not know: it was migrated by a newer one"
            )
        for number, name, sql in known:
            if number in applied:
                continue
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_versions (number, name) VALUES (%s, %s)",
                (number, name),
            )
            applied_now.append(name)
    return applied_now


def pending(conn: psycopg.Connection) -> list[str]:
    """The file names of the migrations this database has not had, in the
    order they would apply. Every one of them on a database never migrated."""
    exists = conn.execute("SELECT to_regclass('schema_versions')").fetchone()[0]
    applied = (
        {row[0] for row in conn.execute("SELECT number FROM schema_versions")}
        if exists
        else set()
    )
    return [name for number, name, _ in migrations() if number not in applied]
