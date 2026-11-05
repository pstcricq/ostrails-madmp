"""What a rules field becomes in a package, ``field_kind()`` and
``needs_a_synthetic_escape()``, the identifier a package carries,
``package_id()``, and what it says it is, ``package_description()`` and
``readme()``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from madmp.model import Field, Model

# The dmp fields filled from the render context instead of a reply: the DSW
# project's own dates, and ``dmp_id``, its URL.
COMPUTED_FIELDS = frozenset({"created", "modified", "dmp_id"})

# The output format a submitted document is rendered in.
SUBMISSION_FORMAT = "JSON"

# What a vocabulary calls "none of those listed", compared case-insensitively:
# ``other`` and ``Other`` alike.
ESCAPE_VALUE = "other"


def package_id(definition: dict[str, Any]) -> str:
    """The DSW package identifier of a project version, the one its KM and
    its template both carry."""
    return "{organizationId}:{id}:{version}".format(**definition)


def utc_timestamp() -> str:
    """The creation timestamp stamped on every generated event and bundle."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def standard_label(standard: str) -> str:
    """A standard's name as a reader sees it, ``rda_dcs`` -> ``RDA_DCS``."""
    return standard.upper()


def needs_a_synthetic_escape(field: Field) -> bool:
    """Whether a field gets an "Other" answer beside its declared values,
    opening a free-text follow-up: when its vocabulary admits values it does
    not list, and lists no ``other`` of its own.
    """
    if field.allowed_values is not None:
        return False
    if field.suggested_values is None:
        return False
    return not any(value.lower() == ESCAPE_VALUE for value in field.suggested_values)


def top_level_split(model: Model) -> tuple[list[Field], list[Field]]:
    """Split the top-level ``dmp`` fields into the general chapter and the
    fields that become chapters of their own.

    A top-level object, single or list, is a chapter of its own, every scalar
    joins the general chapter.
    """
    general, chapters = [], []
    for field in model.fields:
        (chapters if field.type == "object" else general).append(field)
    return general, chapters


# Every value field_kind() can return.
FIELD_KINDS = (
    "computed",
    "list",
    "object_gated",
    "object_inline",
    "options_strict",
    "options_suggested",
    "options_strict_multi",
    "options_suggested_multi",
    "boolean",
    "value",
    "value_multi",
)


def field_kind(
    field: Field, computed_fields: frozenset[str] | set[str] = COMPUTED_FIELDS
) -> str:
    """What DSW entity a rules field becomes.

    One of ``FIELD_KINDS``: ``"list"`` is a list of objects, ``"object_gated"``
    a ``0..1`` object behind a Yes/No gate, and ``"value_multi"`` a scalar
    repeated through its cardinality.
    """
    if len(field.path) == 1 and field.name in computed_fields:
        return "computed"
    if field.type == "object":
        if field.is_list:
            return "list"
        return "object_gated" if field.cardinality == "0..1" else "object_inline"
    multi = field.is_list
    if field.allowed_values is not None:
        return "options_strict_multi" if multi else "options_strict"
    if field.suggested_values is not None:
        return "options_suggested_multi" if multi else "options_suggested"
    if field.type == "boolean":
        return "boolean"
    return "value_multi" if multi else "value"


def package_description(model: Model) -> str:
    """What a package says it is, in plain text, the description DSW shows
    and the opening of its README: the standards it implements by their
    ``name``, base first.

        Implements the A in DS Wizard. ...
        Implements the A, extended with the B, in DS Wizard. ...
        Implements the A, extended with the B and the C, in DS Wizard. ...
    """
    base, *extensions = (f"the {source.name}" for source in model.sources)
    if not extensions:
        implements = f"Implements {base} in DS Wizard."
    else:
        joined = (
            extensions[0]
            if len(extensions) == 1
            else f"{', '.join(extensions[:-1])} and {extensions[-1]}"
        )
        implements = f"Implements {base}, extended with {joined}, in DS Wizard."
    return f"{implements} Every field of the standards is asked to the researcher."


def readme(
    definition: dict[str, Any],
    model: Model,
    kind: str,
    body: list[str],
    compatibility: list[str],
) -> str:
    """A package's README, in Markdown: its title and description, then
    ``body``, the package's own sections, then what it is compatible with,
    the rules versions it was built from last, its author and the references
    of its rules. ``compatibility`` is a list of plain facts, one per line."""
    rules = ", ".join(
        f"{standard_label(name)} {version}" for name, version in model.standard_versions
    )
    references = [ref for source in model.sources for ref in source.references]
    return "\n".join(
        [
            f"# {definition['name']} : {kind}",
            "",
            package_description(model),
            "",
            *body,
            "",
            "## Compatibility",
            "",
            *(f"- {fact}" for fact in [*compatibility, f"Rules: {rules}"]),
            "",
            "## Author",
            "",
            f"Developed by: **{definition['author']}**",
            "",
            "## References",
            "",
            *(f"- [{label}]({url})" for label, url in references),
        ]
    )
