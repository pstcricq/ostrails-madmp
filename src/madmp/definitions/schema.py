"""A document checked against a JSON Schema, every problem at once."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@cache
def _validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validator_for(schema_path: str | Path) -> Draft202012Validator:
    """A cached validator for a schema file, the schema first checked against
    JSON Schema's own meta-schema.

    The path is normalised before it becomes the cache key, so ``"s.json"``
    and ``Path("s.json")`` share one validator.
    """
    return _validator(Path(schema_path))


def schema_problems(validator: Draft202012Validator, doc: Any) -> list[str]:
    """Every schema violation of ``doc``, as sorted ``"path: message"`` strings
    (``"(root)"`` for a top-level problem)."""
    problems = []
    for error in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        where = ".".join(str(part) for part in error.path) or "(root)"
        problems.append(f"{where}: {error.message}")
    return problems
