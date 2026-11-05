"""The DMPs of the database: a project's template DMP,
``<organization>-<project>-template``, and its production DMPs,
``<organization>-<project>-<number>``, written version by version, never
overwritten. Every function takes an open connection, a write running inside
``conn.transaction()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from madmp.errors import DmpNotFoundError, StoreError, VersionConflictError


@dataclass(frozen=True)
class Stored:
    """What a write did: the DMP's key, the version it is now at, and
    ``created`` (its first version), ``updated`` (a new one) or ``unchanged``
    (the same content as the latest, nothing added)."""

    key: str
    version: int
    action: str


@dataclass(frozen=True)
class Version:
    """One version of a DMP, as it was stored. ``metadata`` is rebuilt from
    the definitions the database holds: the project, its version as
    ``project_version``, and the rules it pins."""

    key: str
    version: int
    document: dict[str, Any]
    project_version: str
    metadata: dict[str, Any]
    assessment: dict[str, Any]
    source: str
    created_at: datetime
    from_template_version: int | None


def template_key(organization: str, project: str) -> str:
    """The key of a project's template DMP."""
    return f"{organization}-{project}-template"


def production_key(organization: str, project: str, number: int) -> str:
    """The key of a project's production DMP, its number on four digits at least."""
    return f"{organization}-{project}-{number:04}"


def project_pins(
    conn: psycopg.Connection, project: str, version: str
) -> list[dict[str, str]] | None:
    """The rules a project version pins, as a project writes them, base first,
    ``None`` when the database does not hold that version."""
    if _project_version(conn, project, version) is None:
        return None
    rows = conn.execute(
        "SELECT standard, rules_version FROM project_rules "
        "WHERE project_id = %s AND version = %s ORDER BY position",
        (project, version),
    ).fetchall()
    return [{standard: rules_version} for standard, rules_version in rows]


def _project_version(
    conn: psycopg.Connection, project: str, version: str
) -> dict[str, Any] | None:
    """A project version's YAML as the database holds it, ``None`` when it
    does not."""
    row = conn.execute(
        "SELECT content FROM project_versions WHERE project_id = %s AND version = %s",
        (project, version),
    ).fetchone()
    return None if row is None else row[0]


def _organization(conn: psycopg.Connection, project: str, version: str) -> str:
    """The organization a project version declares, refused when the database
    does not hold that version: its definitions were never synced."""
    content = _project_version(conn, project, version)
    if content is None:
        raise StoreError(
            f"{project} {version} is not in the DMP database, its definitions were "
            f"never synced: run `madmp store sync`"
        )
    return content["organizationId"]


def dmp_project(conn: psycopg.Connection, key: str) -> tuple[str, str] | None:
    """The project and the kind of a DMP, ``None`` when there is no such DMP."""
    return conn.execute(
        "SELECT project_id, kind FROM dmps WHERE key = %s", (key,)
    ).fetchone()


def template_project_version(
    conn: psycopg.Connection, project: str, version: int
) -> str | None:
    """The project version a version of the project's template was produced
    from, ``None`` when the template or that version of it is not there."""
    row = conn.execute(
        "SELECT v.project_version FROM dmps d JOIN dmp_versions v ON v.dmp_key = d.key "
        "WHERE d.project_id = %s AND d.kind = 'template' AND v.version = %s",
        (project, version),
    ).fetchone()
    return None if row is None else row[0]


def _template_version(conn: psycopg.Connection, project: str, version: int) -> str:
    """``template_project_version()``, refused when the template or that
    version of it is not there. Checked here, not by a foreign key: a template
    version can be deleted."""
    project_version = template_project_version(conn, project, version)
    if project_version is None:
        raise StoreError(
            f"the template of {project!r} has no version {version}, a production "
            f"DMP is filled from one that is stored"
        )
    return project_version


def _latest(
    conn: psycopg.Connection,
    key: str,
    document: dict[str, Any],
    project_version: str,
    from_template_version: int | None,
) -> tuple[int, bool] | None:
    """The latest version of a DMP, and whether it holds this content: the
    same document (jsonb equality), produced from the same project version,
    filled from the same template version. ``None`` for a DMP with no
    version yet."""
    return conn.execute(
        "SELECT version, document = %s AND project_version = %s "
        "AND from_template_version IS NOT DISTINCT FROM %s "
        "FROM dmp_versions WHERE dmp_key = %s ORDER BY version DESC LIMIT 1",
        (Jsonb(document), project_version, from_template_version, key),
    ).fetchone()


def _insert_version(
    conn: psycopg.Connection,
    *,
    key: str,
    version: int,
    project: str,
    project_version: str,
    from_template_version: int | None,
    document: dict[str, Any],
    assessment: dict[str, Any],
    source: str,
) -> None:
    conn.execute(
        "INSERT INTO dmp_versions (dmp_key, version, project_id, project_version, "
        "from_template_version, document, assessment, source) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            key,
            version,
            project,
            project_version,
            from_template_version,
            Jsonb(document),
            Jsonb(assessment),
            source,
        ),
    )


def write_template(
    conn: psycopg.Connection,
    *,
    project: str,
    project_version: str,
    document: dict[str, Any],
    assessment: dict[str, Any],
    source: str,
) -> Stored:
    """Write a version of a project's template DMP.

    The template's row is created on the first write, keyed by the
    organization of that project version, and its key kept after that. The
    key is what ``dmp_id`` is set to before the content is compared.

    The template's row is locked for the length of the transaction, so two
    writes at once take their numbers one after the other.
    """
    with conn.transaction():
        organization = _organization(conn, project, project_version)
        conn.execute(
            "INSERT INTO dmps (key, project_id, kind) VALUES (%s, %s, 'template') "
            "ON CONFLICT (project_id) WHERE kind = 'template' DO NOTHING",
            (template_key(organization, project), project),
        )
        (key,) = conn.execute(
            "SELECT key FROM dmps WHERE project_id = %s AND kind = 'template' "
            "FOR UPDATE",
            (project,),
        ).fetchone()
        document = {**document, "dmp_id": {"identifier": key, "type": "other"}}
        latest = _latest(conn, key, document, project_version, None)
        if latest is not None and latest[1]:
            return Stored(key, latest[0], "unchanged")
        version = 1 if latest is None else latest[0] + 1
        _insert_version(
            conn,
            key=key,
            version=version,
            project=project,
            project_version=project_version,
            from_template_version=None,
            document=document,
            assessment=assessment,
            source=source,
        )
    return Stored(key, version, "created" if version == 1 else "updated")


def create_production(
    conn: psycopg.Connection,
    *,
    project: str,
    from_template_version: int,
    document: dict[str, Any],
    assessment: dict[str, Any],
    source: str,
) -> Stored:
    """Create a project's next production DMP, filled from a version of its template,
    and write its first version, produced from that template version's
    project version.

    The project's row is locked for the length of the transaction, so two
    creations at once take two numbers. A number is never given twice: it
    only goes up.
    """
    with conn.transaction():
        row = conn.execute(
            "SELECT next_number FROM projects WHERE id = %s FOR UPDATE", (project,)
        ).fetchone()
        if row is None:
            raise StoreError(
                f"{project!r} is not in the DMP database, its definitions were "
                f"never synced: run `madmp store sync`"
            )
        project_version = _template_version(conn, project, from_template_version)
        key = production_key(
            _organization(conn, project, project_version), project, row[0]
        )
        conn.execute(
            "UPDATE projects SET next_number = next_number + 1 WHERE id = %s",
            (project,),
        )
        conn.execute(
            "INSERT INTO dmps (key, project_id, kind) VALUES (%s, %s, 'production')",
            (key, project),
        )
        _insert_version(
            conn,
            key=key,
            version=1,
            project=project,
            project_version=project_version,
            from_template_version=from_template_version,
            document={**document, "dmp_id": {"identifier": key, "type": "other"}},
            assessment=assessment,
            source=source,
        )
    return Stored(key, 1, "created")


def add_production_version(
    conn: psycopg.Connection,
    *,
    key: str,
    based_on: int,
    from_template_version: int,
    document: dict[str, Any],
    assessment: dict[str, Any],
    source: str,
) -> Stored:
    """Write the next version of a production DMP, written from version
    ``based_on``.

    Refused when ``based_on`` is no longer the latest: somebody else wrote in
    between. The DMP's row is locked for the length of the transaction, so two writes
    based on the same version end with the first one written and the second
    one refused. The same content, filled from the same template version,
    adds nothing.
    """
    with conn.transaction():
        row = conn.execute(
            "SELECT project_id, kind FROM dmps WHERE key = %s FOR UPDATE", (key,)
        ).fetchone()
        if row is None or row[1] != "production":
            raise DmpNotFoundError(f"no production DMP {key!r}")
        project = row[0]
        project_version = _template_version(conn, project, from_template_version)
        document = {**document, "dmp_id": {"identifier": key, "type": "other"}}
        found = _latest(conn, key, document, project_version, from_template_version)
        if found is None:
            raise DmpNotFoundError(f"no version left of production DMP {key!r}")
        latest, same = found
        if based_on != latest:
            raise VersionConflictError(
                f"{key} is at version {latest}, and this write is based on version "
                f"{based_on}: read it again and redo the changes on it"
            )
        if same:
            return Stored(key, latest, "unchanged")
        _insert_version(
            conn,
            key=key,
            version=latest + 1,
            project=project,
            project_version=project_version,
            from_template_version=from_template_version,
            document=document,
            assessment=assessment,
            source=source,
        )
    return Stored(key, latest + 1, "updated")


# A version, its metadata rebuilt from the project version it names, as a
# DMP carries it.
_VERSION = (
    "SELECT v.dmp_key, v.version, v.document, v.project_version, "
    "jsonb_build_object("
    "'project', v.project_id, 'project_version', v.project_version, "
    "'rules', (SELECT jsonb_agg(jsonb_build_object(r.standard, r.rules_version) "
    "ORDER BY r.position) FROM project_rules r "
    "WHERE r.project_id = v.project_id AND r.version = v.project_version)), "
    "v.assessment, v.source, v.created_at, "
    "v.from_template_version "
    "FROM dmp_versions v WHERE v.dmp_key = %s"
)


def latest_version(conn: psycopg.Connection, key: str) -> Version | None:
    """The latest version of a DMP, ``None`` when there is no such DMP."""
    row = conn.execute(_VERSION + " ORDER BY v.version DESC LIMIT 1", (key,)).fetchone()
    return None if row is None else Version(*row)


def get_version(conn: psycopg.Connection, key: str, version: int) -> Version | None:
    """One version of a DMP, ``None`` when there is no such version."""
    row = conn.execute(_VERSION + " AND v.version = %s", (key, version)).fetchone()
    return None if row is None else Version(*row)


def list_versions(conn: psycopg.Connection, key: str) -> list[dict[str, Any]]:
    """Every version of a DMP, the first one first, without its content: the
    number, when, what wrote it, the project version it was produced from, the
    template version it was filled from, and the verdict."""
    rows = conn.execute(
        "SELECT version, created_at, source, project_version, "
        "from_template_version, assessment ->> 'verdict' "
        "FROM dmp_versions WHERE dmp_key = %s ORDER BY version",
        (key,),
    ).fetchall()
    names = (
        "version",
        "created_at",
        "source",
        "project_version",
        "from_template_version",
        "verdict",
    )
    return [dict(zip(names, row, strict=True)) for row in rows]
