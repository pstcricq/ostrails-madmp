"""The published version files, which never change: ``changed_since()`` names
those a git revision holds and the checkout changed or removed,
``branch_point()`` is the commit a branch starts from.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

from madmp.definitions.loader import Kind
from madmp.paths import ROOT


def version_files(kinds: Iterable[Kind]) -> re.Pattern[str]:
    """What a version file of any of ``kinds`` is named, as git names it from
    the root of the repository: ``definitions/<kind>/<key>/<X.Y.Z><suffix>``."""
    return re.compile(
        "^definitions/(?:"
        + "|".join(
            rf"{re.escape(kind.directory.name)}/[^/]+/[0-9]+\.[0-9]+\.[0-9]+"
            + re.escape(kind.suffix)
            for kind in kinds
        )
        + ")$"
    )


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True
    ).stdout


def changed_since(revision: str, kinds: Iterable[Kind], root: Path = ROOT) -> list[str]:
    """The version files of ``kinds`` that ``revision`` has and the checkout
    at ``root`` has changed or removed, as paths from the root of the
    repository, sorted.

    Raises ``subprocess.CalledProcessError`` when git cannot read the
    revision.
    """
    version_file = version_files(kinds)
    listed = _git(
        root, "ls-tree", "-r", "--name-only", revision, "--", "definitions"
    ).decode()
    changed = []
    for name in listed.splitlines():
        if not version_file.match(name):
            continue
        current = root / name
        if not current.is_file() or current.read_bytes() != _git(
            root, "show", f"{revision}:{name}"
        ):
            changed.append(name)
    return sorted(changed)


def branch_point(base: str, root: Path = ROOT) -> str | None:
    """The commit where the checkout at ``root`` left ``base``, a branch, or
    ``base`` itself when it is a commit the checkout holds. None when there is
    none to find: no git, no such branch, or no history in common."""
    try:
        return _git(root, "merge-base", base, "HEAD").decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return None
