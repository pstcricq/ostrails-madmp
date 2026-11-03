"""The two packages of one project version: ``build()`` builds and checks them,
one time stamp for both, ``write()`` writes them as the files DSW imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2

from madmp.errors import PackageError
from madmp.model import Model
from madmp.packages.common import package_id, utc_timestamp
from madmp.packages.km import build_km_bundle
from madmp.packages.template import build_template_bundle


@dataclass(frozen=True)
class Packages:
    """A project version's KM bundle and document template bundle."""

    km: dict[str, Any]
    template: dict[str, Any]


def build(
    definition: dict[str, Any], model: Model, created_at: str | None = None
) -> Packages:
    """Both packages of a project version, or ``PackageError`` with every
    problem found."""
    created_at = created_at or utc_timestamp()
    km = build_km_bundle(definition, model, created_at=created_at)
    template = build_template_bundle(definition, model, created_at=created_at)
    problems = []
    if twice := _duplicate_entities(km):
        problems.append(
            f"the KM emits {len(twice)} entity(ies) twice, first {twice[0]}"
        )
    if error := _jinja_error(template):
        problems.append(f"the document template is not Jinja, {error}")
    if problems:
        raise PackageError(problems, package_id(definition))
    return Packages(km, template)


def write(
    packages: Packages, definition: dict[str, Any], out: Path
) -> tuple[Path, Path]:
    """Write both packages into ``out``, created if missing, as
    ``<id>_<version>_km.km`` and ``<id>_<version>_template.json``, and return
    the two paths."""
    name = f"{definition['id']}_{definition['version']}"
    km_file, template_file = out / f"{name}_km.km", out / f"{name}_template.json"
    out.mkdir(parents=True, exist_ok=True)
    for path, bundle in ((km_file, packages.km), (template_file, packages.template)):
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    return km_file, template_file


def _duplicate_entities(km: dict[str, Any]) -> list[str]:
    """Entities the KM emits twice, as a declared answer ``other`` beside a
    synthetic "Other" would."""
    seen, twice = set(), []
    for event in km["packages"][0]["events"]:
        if event["entityUuid"] in seen:
            twice.append(event["entityUuid"])
        seen.add(event["entityUuid"])
    return twice


def _jinja_error(template: dict[str, Any]) -> str | None:
    """What makes the document template's body not Jinja, if anything. A
    vocabulary label is written into the body as a Jinja literal."""
    try:
        jinja2.Environment().parse(template["files"][0]["content"])
    except jinja2.TemplateSyntaxError as err:
        return f"line {err.lineno}: {err.message}"
    return None
