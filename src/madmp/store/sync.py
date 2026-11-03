"""The definitions copied into the DMP database, the rules first: what is
missing is added, and a version already there with another content refuses
the whole sync.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from madmp.definitions import KINDS, PROJECTS, RULES, files, load
from madmp.errors import StoreError
from madmp.paths import PROJECTS_DIR, RULES_DIR

# The key of the advisory lock taken while syncing, any number no other
# client of this database uses: two syncs at once copy everything once.
LOCK = 4_242_002


def _insert_rules(conn: psycopg.Connection, content: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO rules (standard, version, content) VALUES (%s, %s, %s)",
        (content["standard"], content["version"], Jsonb(content)),
    )


def _insert_project(conn: psycopg.Connection, content: dict[str, Any]) -> None:
    """A project version, the project itself the first time, and the rules it
    pins, which have to be there: the rules are synced first."""
    project, version = content["id"], content["version"]
    conn.execute(
        "INSERT INTO projects (id) VALUES (%s) ON CONFLICT DO NOTHING", (project,)
    )
    pins = [next(iter(pin.items())) for pin in content["rules"]]
    for standard, rules_version in pins:
        found = conn.execute(
            "SELECT 1 FROM rules WHERE standard = %s AND version = %s",
            (standard, rules_version),
        ).fetchone()
        if found is None:
            raise StoreError(
                f"project {project} {version} pins {standard} {rules_version}, "
                f"which no rules file defines"
            )
    conn.execute(
        "INSERT INTO project_versions (project_id, version, content) "
        "VALUES (%s, %s, %s)",
        (project, version, Jsonb(content)),
    )
    for position, (standard, rules_version) in enumerate(pins, start=1):
        conn.execute(
            "INSERT INTO project_rules (project_id, version, position, standard, "
            "rules_version) VALUES (%s, %s, %s, %s, %s)",
            (project, version, position, standard, rules_version),
        )


# Where each kind is kept: the table a version is one row of, the column its
# key is in, and how a new version is inserted, which is each kind's own. A
# kind of KINDS needs its line here, and its tables.
_KEPT = {
    RULES: ("rules", "standard", _insert_rules),
    PROJECTS: ("project_versions", "project_id", _insert_project),
}


def sync(
    conn: psycopg.Connection,
    rules_dir: Path = RULES_DIR,
    projects_dir: Path = PROJECTS_DIR,
) -> list[str]:
    """Copy every version of every kind the database does not have yet, in
    the order of KINDS, the rules first, and return what was
    added, one line each, empty when it was up to date.

    One transaction: a version whose content changed, or a project pinning
    rules that do not exist, refuses the whole sync.
    """
    directories = {RULES: rules_dir, PROJECTS: projects_dir}
    added: list[str] = []
    changed: list[str] = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
        for kind in KINDS:
            table, column, insert = _KEPT[kind]
            same_content = sql.SQL(
                "SELECT content = %s FROM {} WHERE {} = %s AND version = %s"
            ).format(sql.Identifier(table), sql.Identifier(column))
            for path in files(kind, directories[kind]):
                content = load(kind, path)
                key, version = content[kind.key], content["version"]
                stored = conn.execute(
                    same_content, (Jsonb(content), key, version)
                ).fetchone()
                if stored is None:
                    insert(conn, content)
                    added.append(f"{kind.name} {key} {version}")
                elif not stored[0]:
                    changed.append(f"{kind.name} {key} {version} ({path.name})")
        if changed:
            raise StoreError(
                f"changed since they were synced, which a published version never "
                f"is: {', '.join(changed)}. Publish a new version instead."
            )
    return added
