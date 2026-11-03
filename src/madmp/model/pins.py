"""Pins turned into the rules files they name, ``<standard>/<version>.json``:
``resolve_pins()`` checks their shape and that the files exist, without
reading them.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from madmp.errors import UnresolvedPinsError

Pin = dict[str, str]

# A rules file is JSON.
SUFFIX = ".json"

# The two halves of a pin, as the schemas write them. Neither can hold a
# separator or a dot name, so a pin always names one file under the tree.
_STANDARD = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION = re.compile(r"^[0-9]+[.][0-9]+[.][0-9]+$")


def pin_problems(pins: Any) -> list[str]:
    """Everything wrong with the shape of a list of pins, at once, empty when
    there is nothing: a non-empty list of ``{standard: version}``, the
    standard in snake_case, the version an X.Y.Z string."""
    if not isinstance(pins, list) or not pins:
        return [f"{pins!r} is not a non-empty list of {{standard: version}} pins."]
    problems = []
    for number, pin in enumerate(pins, start=1):
        if not (isinstance(pin, dict) and len(pin) == 1):
            problems.append(f"pin {number}, {pin!r}: not one {{standard: version}}.")
            continue
        ((name, version),) = pin.items()
        if not (isinstance(name, str) and _STANDARD.match(name)):
            problems.append(
                f"pin {number}, {name!r}: not a standard's identifier, snake_case."
            )
        if not (isinstance(version, str) and _VERSION.match(version)):
            problems.append(
                f"pin {number}, {name}: {version!r} is not a version X.Y.Z, quoted."
            )
    return problems


def _standards_in(root: Path) -> str:
    """What the tree offers, read off the disk, for an error message.

    A directory counts only if it holds a versioned file. A tree that is not
    there at all says so.
    """
    if not root.is_dir():
        return "nothing, no such directory"
    names = sorted(
        p.name for p in root.iterdir() if p.is_dir() and any(p.glob(f"*{SUFFIX}"))
    )
    return ", ".join(names) or "nothing"


def _versions_in(directory: Path) -> str:
    """The versions one standard directory offers, for an error message."""
    return ", ".join(sorted(p.stem for p in directory.glob(f"*{SUFFIX}"))) or "nothing"


def resolve_pins(pins: list[Pin], rules_dir: str | Path) -> list[Path]:
    """The rules files a project's ``rules:`` pins name, in the order written.

    Raises ``UnresolvedPinsError`` listing every malformed pin, or else every
    pin that does not resolve, each with the names the tree does offer.
    """
    if problems := pin_problems(pins):
        raise UnresolvedPinsError(problems)
    root = Path(rules_dir)
    paths = []
    for pin in pins:
        ((name, version),) = pin.items()
        directory = root / name
        path = directory / f"{version}{SUFFIX}"
        if not directory.is_dir():
            problems.append(
                f"unknown standard {name!r}, {root} has {_standards_in(root)}."
            )
        elif not path.is_file():
            problems.append(
                f"standard {name}: unknown version {version!r}, it has "
                f"{_versions_in(directory)}."
            )
        else:
            paths.append(path)
    if problems:
        raise UnresolvedPinsError(problems)
    return paths
