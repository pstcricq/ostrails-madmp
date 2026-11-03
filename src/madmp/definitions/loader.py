"""How a definition of any kind is read: ``load()`` checks one file's format,
its schema, then its path and the kind's own checks, every problem of a step
at once; ``files()`` lists a kind's files, each key's oldest version first.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from madmp.definitions.schema import schema_problems, validator_for
from madmp.errors import SchemaFileError


@dataclass(frozen=True)
class Kind:
    """One kind of definition, and what sets it apart from the others.

    Frozen, so a kind can be a dictionary key.
    """

    # Its files' home, whose name is the kind's (``name``).
    directory: Path
    schema: Path
    # The field a file's directory is named after.
    key: str
    # The one format the kind's files are written in, ".json" or ".yaml".
    suffix: str
    error: type[SchemaFileError]
    # Every coherence problem of one document, once its schema passed. None
    # for a kind with no checks of its own beyond its schema and its layout.
    checks: Callable[[dict[str, Any]], list[str]] | None = None

    @property
    def name(self) -> str:
        """What the kind is called, its directory's name: "rules"."""
        return self.directory.name


# What reads each format, and what a syntax error is called.
_READERS: dict[str, tuple[Callable[[str], Any], type[Exception], str]] = {
    ".json": (json.loads, json.JSONDecodeError, "JSON"),
    ".yaml": (yaml.safe_load, yaml.YAMLError, "YAML"),
}


def _read(kind: Kind, path: Path) -> Any:
    if path.suffix != kind.suffix:
        raise kind.error(
            path,
            [
                (
                    f"is a {path.suffix or 'suffixless'} file, "
                    f"{kind.name} are {kind.suffix} files."
                )
            ],
        )
    parse, syntax_error, format_name = _READERS[kind.suffix]
    try:
        return parse(path.read_text())
    except OSError as err:
        raise kind.error(path, [f"cannot be read: {err.strerror}."]) from err
    except syntax_error as err:
        raise kind.error(path, [f"invalid {format_name}: {err}"]) from err


def _layout_problems(kind: Kind, path: Path, doc: dict[str, Any]) -> list[str]:
    """Every way the file disagrees with the path it sits at, at once:
    ``<key>/<version><suffix>``, string for string."""
    problems = []
    if doc[kind.key] != path.parent.name:
        problems.append(
            f"declares {kind.key} {doc[kind.key]!r} but sits in directory "
            f"{path.parent.name!r}, the two must agree."
        )
    if doc["version"] != path.stem:
        problems.append(
            f"declares version {doc['version']!r} but is named {path.stem!r}, "
            f"the two must agree."
        )
    return problems


def load(kind: Kind, path: str | Path) -> dict[str, Any]:
    """Load one file of a kind, fully validated.

    Returns the parsed document. Raises the kind's error listing every problem
    found, an unreadable path and a syntax error included.
    """
    path = Path(path)
    doc = _read(kind, path)
    # An empty YAML file reads as None, which the schema refuses as a
    # non-object.
    problems = schema_problems(validator_for(kind.schema), doc)
    if not problems:
        problems = _layout_problems(kind, path, doc)
        if kind.checks:
            problems += kind.checks(doc)
    if problems:
        raise kind.error(path, problems)
    return doc


def version_key(path: Path) -> tuple[int, ...]:
    """A file's version as numbers, so 1.10.0 sorts after 1.9.0. A name that
    is no version sorts first, and its load says what is wrong."""
    parts = path.stem.split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else ()


def files(kind: Kind, directory: Path | None = None) -> list[Path]:
    """Every file under ``<key>/`` of a kind's directory, or of ``directory``,
    by key, each key's oldest version first.

    Every file is listed, whatever its format, so its load refuses one of
    another format. Hidden files are left out.
    """
    root = kind.directory if directory is None else directory
    found = [
        path
        for path in root.glob("*/*")
        if path.is_file() and not path.name.startswith(".")
    ]
    return sorted(found, key=lambda path: (path.parent.name, version_key(path)))
