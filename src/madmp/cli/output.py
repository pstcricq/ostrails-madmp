"""What the madmp command prints: ``ok`` on standard output, ``FAIL`` on
standard error, then one summary line."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from madmp.paths import ROOT


def shown(path: Path) -> str:
    """A path as a line names it, from the root of the checkout when it is
    inside it."""
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def ok(text: str) -> None:
    print(f"ok   {text}")


def fail(subject: str, problem: object) -> None:
    details = str(problem).replace("\n", "\n     ")
    print(f"FAIL {subject}\n     {details}", file=sys.stderr)


def count(n: int, noun: str) -> str:
    """``1 file``, ``2 files``."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def summary(
    total: int, failed: int, noun: str, passed: str, refused: str, scope: str = ""
) -> int:
    """The closing line, and the exit code it stands for. ``scope``, a kind's
    name, opens it: ``rules: 2 files valid.``"""
    head = f"{scope}: " if scope else ""
    if failed:
        print(f"\n{head}{failed} of {count(total, noun)} {refused}.", file=sys.stderr)
        return 1
    print(f"\n{head}{count(total, noun)} {passed}.")
    return 0


def each(
    paths: list[Path],
    noun: str,
    empty_dir: Path,
    step: Callable[[Path], bool],
    scope: str = "",
) -> list[Path] | None:
    """Run ``step`` on every path and return those that failed, ``None`` when
    there is no path. ``step`` prints its own line and says whether the path
    passed."""
    if not paths:
        head = f"{scope}: no" if scope else "No"
        print(f"{head} {noun} found under {shown(empty_dir)}.", file=sys.stderr)
        return None
    return [path for path in paths if not step(path)]
