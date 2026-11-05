"""The API's logic, without HTTP: ``check_document()`` assesses a document
against the rules its metadata names, ``handle_template()``,
``handle_new_production()`` and ``handle_production_version()`` write it with
its assessment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg

from madmp.assessment import check_conformance, envelope
from madmp.definitions import PROJECTS, files
from madmp.errors import (
    AssessmentError,
    DmpNotFoundError,
    ProblemsError,
    RequestError,
    StoreError,
)
from madmp.model import model_for, pin_problems
from madmp.store import (
    Database,
    Stored,
    add_production_version,
    create_production,
    dmp_project,
    project_pins,
    template_project_version,
    write_template,
)

# A project version, X.Y.Z.
_VERSION = re.compile(r"^[0-9]+[.][0-9]+[.][0-9]+$")

# How many failures a refusal spells out before counting the rest, the count
# above the list saying how many there were.
_SPELLED_OUT = 20


@dataclass(frozen=True)
class Document:
    """A document that passed every check but the database's, ready to be
    written."""

    project: str
    dmp: dict[str, Any]
    metadata: dict[str, Any]
    assessment: dict[str, Any]


def version_number(value: Any, name: str) -> int:
    """A DMP version number the body gives, or a refusal naming the field."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RequestError(f"{name} is {value!r}, not a version number (1, 2, ...)")
    return value


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
    """The document's metadata: the project, the project version it was
    produced from, ``project_version``, and the rules that version pins.

    Absent or malformed is a refusal.
    """
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise RequestError(
            "document carries no 'metadata' object, so the rules it was built "
            "from are unknown"
        )
    if not isinstance(metadata.get("project"), str):
        raise RequestError(f"metadata.project is {metadata.get('project')!r}")
    version = metadata.get("project_version")
    if not (isinstance(version, str) and _VERSION.match(version)):
        raise RequestError(f"metadata.project_version is {version!r}, not X.Y.Z")
    if problems := pin_problems(metadata.get("rules")):
        raise RequestError(f"metadata.rules: {' '.join(problems)}")
    return metadata


def _listed(rows: list[dict[str, Any]], head: str) -> list[str]:
    """One headed block of result messages, cut at ``_SPELLED_OUT``."""
    lines = [
        f"{head}, the first {_SPELLED_OUT}:" if len(rows) > _SPELLED_OUT else f"{head}:"
    ]
    lines += [f"  {row['message']}" for row in rows[:_SPELLED_OUT]]
    if len(rows) > _SPELLED_OUT:
        lines.append(f"  [...] {len(rows) - _SPELLED_OUT} more not shown.")
    return lines


def _counted(assessment: dict[str, Any]) -> str:
    """The line that closes every message: what held up, and what was left
    empty."""
    summary = assessment["summary"]
    return (
        f"{summary['pass']} checks passed, "
        f"{summary['missing']} optional fields left empty."
    )


def _refusal(assessment: dict[str, Any]) -> str:
    """What the author of a document that does not hold up is told: the
    failures first, then the warnings, which do not block."""
    versions = ", ".join(
        f"{name} {version}" for name, version in assessment["rules_versions"].items()
    )
    lines = [f"Assessment failed against {versions}.", ""]
    lines += _listed(assessment["fail"], f"{len(assessment['fail'])} failure(s) to fix")
    if assessment["warning"]:
        head = f"{len(assessment['warning'])} warning(s), which do not block"
        lines += ["", *_listed(assessment["warning"], head)]
    return "\n".join([*lines, "", _counted(assessment)])


def _outcome(stored: Stored, assessment: dict[str, Any]) -> str:
    """What the author of a written document is told."""
    if stored.action == "unchanged":
        head = f"Unchanged, {stored.key} version {stored.version} already holds it."
    else:
        head = f"Stored as {stored.key} version {stored.version}."
    if not assessment["warning"]:
        return f"{head} {_counted(assessment)}"
    warnings = assessment["warning"]
    lines = [head, "", *_listed(warnings, f"{len(warnings)} warning(s)")]
    return "\n".join([*lines, "", _counted(assessment)])


def check_document(document: Any, name: str | None = None) -> Document:
    """Every check a document goes through before the database's, in this
    order, the first that fails refusing it: a body with no ``dmp`` object,
    metadata that is absent or malformed, a project or a project version that
    is not defined, and a document that does not hold up against the rules its
    metadata names. ``name`` is what the assessment names the DMP by, its
    project and project version by default."""
    if not isinstance(document, dict) or not isinstance(document.get("dmp"), dict):
        raise RequestError("document has no dmp object")
    metadata = _metadata(document)
    project, version = metadata["project"], metadata["project_version"]
    # Looked up among the definitions: a project and a version are known, or
    # refused.
    versions = {path.stem for path in files(PROJECTS) if path.parent.name == project}
    if not versions:
        raise RequestError(f"project {project!r} is not defined")
    if version not in versions:
        raise RequestError(f"{project} {version} is not defined")
    try:
        model = model_for(metadata["rules"])
    except ProblemsError as err:
        raise AssessmentError(
            f"the rules this document names cannot be loaded, {err}"
        ) from err
    assessment = envelope(
        model, check_conformance(model, document), name or f"{project} {version}"
    )
    if assessment["verdict"] == "fail":
        raise AssessmentError(_refusal(assessment))
    return Document(project, document["dmp"], metadata, assessment)


def _pins_agree(conn: psycopg.Connection, checked: Document) -> str:
    """The project version the document was produced from, once the rules its
    metadata names are the ones the database holds for that version."""
    version = checked.metadata["project_version"]
    pins = project_pins(conn, checked.project, version)
    if pins is None:
        raise StoreError(
            f"{checked.project} {version} is not in the DMP database, its "
            f"definitions were never synced: run `madmp store sync`"
        )
    if pins != checked.metadata["rules"]:
        raise RequestError(
            f"metadata.rules is {checked.metadata['rules']}, and {checked.project} "
            f"{version} pins {pins}: the document was not produced from that version"
        )
    return version


def _filled_from(
    conn: psycopg.Connection, checked: Document, template_version: int
) -> None:
    """Refuse a production document whose metadata is not the one of the
    template version it says it was filled from: the version written is
    produced from that template version's project version."""
    project_version = template_project_version(conn, checked.project, template_version)
    if project_version is None:
        raise StoreError(
            f"the template of {checked.project!r} has no version {template_version}, "
            f"a production DMP is filled from one that is stored"
        )
    if project_version != checked.metadata["project_version"]:
        raise RequestError(
            f"metadata.project_version is {checked.metadata['project_version']}, "
            f"and version {template_version} of the template was produced from "
            f"{project_version}"
        )


def _result(project: str, stored: Stored, assessment: dict[str, Any]) -> dict[str, Any]:
    """What every write answers: where it landed, and its assessment."""
    return {
        "project": project,
        "key": stored.key,
        "version": stored.version,
        "action": stored.action,
        "message": _outcome(stored, assessment),
        "assessment": assessment,
    }


def handle_template(document: Any, database: Database) -> dict[str, Any]:
    """Write a document as the next version of its project's template DMP.

    Nothing is written for a document that is refused. A document saying what
    the latest version says adds nothing."""
    checked = check_document(document)
    with database.connect() as conn:
        stored = write_template(
            conn,
            project=checked.project,
            project_version=_pins_agree(conn, checked),
            document=checked.dmp,
            assessment=checked.assessment,
            source="templates",
        )
    return _result(checked.project, stored, checked.assessment)


def handle_new_production(body: Any, database: Database) -> dict[str, Any]:
    """Create a project's next production DMP from a body holding
    ``from_template_version`` and the document as that template version was
    read back, ``dmp`` and ``metadata``, filled in."""
    if not isinstance(body, dict):
        raise RequestError("body is not a JSON object")
    template_version = version_number(
        body.get("from_template_version"), "from_template_version"
    )
    checked = check_document(body)
    with database.connect() as conn:
        _pins_agree(conn, checked)
        _filled_from(conn, checked, template_version)
        stored = create_production(
            conn,
            project=checked.project,
            from_template_version=template_version,
            document=checked.dmp,
            assessment=checked.assessment,
            source="productions",
        )
    return _result(checked.project, stored, checked.assessment)


def handle_production_version(
    key: str, body: Any, database: Database
) -> dict[str, Any]:
    """Write the next version of a production DMP from a body holding
    ``based_on``, the version the changes were made on,
    ``from_template_version``, and the document, ``dmp`` and ``metadata``.

    The document has to be of the DMP's own project, and the write refuses a
    ``based_on`` that is no longer the latest."""
    if not isinstance(body, dict):
        raise RequestError("body is not a JSON object")
    based_on = version_number(body.get("based_on"), "based_on")
    template_version = version_number(
        body.get("from_template_version"), "from_template_version"
    )
    with database.connect() as conn:
        found = dmp_project(conn, key)
        if found is None or found[1] != "production":
            raise DmpNotFoundError(f"no production DMP {key!r}")
        checked = check_document(body, key)
        if checked.project != found[0]:
            raise RequestError(
                f"metadata.project is {checked.project!r}, and {key} is a DMP of "
                f"{found[0]!r}"
            )
        _pins_agree(conn, checked)
        _filled_from(conn, checked, template_version)
        stored = add_production_version(
            conn,
            key=key,
            based_on=based_on,
            from_template_version=template_version,
            document=checked.dmp,
            assessment=checked.assessment,
            source="productions",
        )
    return _result(checked.project, stored, checked.assessment)
