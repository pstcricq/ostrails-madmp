"""The rules, ``RULES``: ``definitions/rules/<standard>/<version>.json``,
checked against ``rules.schema.json``, its path, then ``rules_checks()``: the
coherence of its fields, and an extension of another standard.
"""

from __future__ import annotations

from typing import Any

from madmp.definitions.loader import Kind
from madmp.errors import RulesFileError
from madmp.paths import RULES_DIR, RULES_SCHEMA


def field_children(node: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """A field node's declared child fields: every key not starting with ``_``."""
    return [(k, v) for k, v in node.items() if not k.startswith("_")]


def _field_problems(
    tree: dict[str, Any], prefix: str, base: bool, depth: int = 1
) -> list[str]:
    """Every coherence constraint broken in a field tree, at once, in one
    walk.

    ``prefix`` is the dotted path of ``tree``, ``depth`` its level, 1 for
    ``dmp``'s own fields. ``base`` is whether the file is the base standard,
    where every field needs a ``_description``.
    """
    problems = []
    for key, node in field_children(tree):
        path = f"{prefix}.{key}"
        if field_children(node) and node.get("_type") != "object":
            problems.append(
                f"{path}: declares child fields but has _type "
                f"{node.get('_type')!r}, only 'object' fields may have children."
            )
        if node.get("_type") == "object" and not field_children(node):
            problems.append(
                f"{path}: _type 'object' but declares no child fields, an "
                f"object field must declare at least one."
            )
        for vocab_key in ("_allowed_values", "_suggested_values"):
            if vocab_key in node and node.get("_type") == "object":
                problems.append(
                    f"{path}: {vocab_key} on an 'object' field, vocabularies "
                    f"only apply to scalar fields."
                )
        if "_allowed_values" in node and "_suggested_values" in node:
            problems.append(
                f"{path}: both _allowed_values and _suggested_values, a "
                f"vocabulary is either closed or recommended, not both "
                f"(keep one)."
            )
        if "_chapter_description" in node and not (
            depth == 1 and node.get("_type") == "object"
        ):
            reason = (
                f"_type {node.get('_type')!r} is not an object"
                if depth == 1
                else "it is not a top-level field"
            )
            problems.append(
                f"{path}: _chapter_description but {reason} (use _description instead)."
            )
        if base and "_description" not in node:
            problems.append(
                f"{path}: no _description, every field of the base standard "
                f"needs one, it is the question a researcher reads."
            )
        problems.extend(_field_problems(node, path, base, depth + 1))
    return problems


def rules_checks(doc: dict[str, Any]) -> list[str]:
    """Every problem of a rules file beyond its schema and its layout: its
    fields' coherence, then an extension of its own standard."""
    problems = _field_problems(doc["dmp"], "dmp", base="extends" not in doc)
    if "extends" in doc and doc["extends"]["standard"] == doc["standard"]:
        problems.append(
            f"extends {doc['standard']!r}, its own standard: an extension "
            f"extends the base."
        )
    return problems


RULES = Kind(
    directory=RULES_DIR,
    schema=RULES_SCHEMA,
    key="standard",
    suffix=".json",
    error=RulesFileError,
    checks=rules_checks,
)
