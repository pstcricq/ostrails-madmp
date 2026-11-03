"""The ``madmp validate`` commands: ``rules``, ``projects``, ``models``,
``frozen``, and ``all`` for every one of them in this order.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from madmp.cli import output
from madmp.definitions import (
    KINDS,
    PROJECTS,
    Kind,
    ProjectFileError,
    branch_point,
    changed_since,
    files,
    load,
)
from madmp.errors import ProblemsError
from madmp.model import model_for
from madmp.paths import PROJECTS_DIR


def _validate_kind(kind: Kind) -> int:
    """Every file of one kind, against its schema, its path and its kind's
    own checks, the kind's name opening the summary line."""
    paths = files(kind)

    def step(path: Path) -> bool:
        try:
            doc = load(kind, path)
        except kind.error as err:
            output.fail(output.shown(path), err)
            return False
        output.ok(f"{output.shown(path)} : {doc[kind.key]} {doc['version']}")
        return True

    failed = output.each(paths, "file", kind.directory, step, kind.name)
    if failed is None:
        return 1
    return output.summary(
        len(paths), len(failed), "file", "valid", "rejected", kind.name
    )


def _validate_models() -> int:
    """Every project version's pins resolved and their rules merged. A project
    that does not load is skipped."""
    paths = files(PROJECTS)

    def step(path: Path) -> bool:
        try:
            model = model_for(load(PROJECTS, path)["rules"])
        except ProjectFileError:
            output.fail(
                output.shown(path),
                "does not load, see `madmp validate projects`.",
                skip=True,
            )
            return False
        # Unresolved pins, an ill-formed or conflicting set.
        except ProblemsError as err:
            output.fail(output.shown(path), "\n".join(f"- {p}" for p in err.problems))
            return False
        merged = " + ".join(model.standards)
        fields = sum(1 for _ in model.walk())
        output.ok(f"{output.shown(path)} : {merged}, {fields} fields")
        return True

    failed = output.each(paths, "project version", PROJECTS_DIR, step, "models")
    if failed is None:
        return 1
    return output.summary(
        len(paths),
        len(failed),
        "project version",
        "resolved and merged",
        "not resolved and merged",
        "models",
    )


# Every kind, then the models, which merge what the projects pin.
_VALIDATE_STEPS = {
    **{kind.name: (lambda kind=kind: _validate_kind(kind)) for kind in KINDS},
    "models": _validate_models,
}


def _validate_frozen(base: str) -> int:
    """Every version file of the point this checkout left ``base`` unchanged
    in the checkout. With nothing to compare with, it says so and passes. A
    commit is shown by its short hash."""
    revision = branch_point(base)
    if revision is None:
        print(f"frozen: nothing to compare with, no {base}: set --base <branch>.")
        return 0
    shown = revision[:7] if re.fullmatch(r"[0-9a-f]{40}", revision) else revision
    try:
        changed = changed_since(revision, KINDS)
    except subprocess.CalledProcessError as err:
        output.fail(shown, f"git cannot read it: {err.stderr.decode().strip()}")
        return 1
    for name in changed:
        output.fail(
            name, f"changed or removed since {shown}, add a new version instead"
        )
    if changed:
        published = output.count(len(changed), "published version")
        print(f"\nfrozen: {published} changed.", file=sys.stderr)
        return 1
    print(f"frozen: no published version changed since {shown}.")
    return 0


def _validate(args: argparse.Namespace) -> int:
    """One step, or ``all`` in order, a blank line between two, stopping at
    the first that fails."""
    steps = {**_VALIDATE_STEPS, "frozen": lambda: _validate_frozen(args.base)}
    names = list(steps) if args.step == "all" else [args.step]
    for number, name in enumerate(names):
        if number:
            print()
        if steps[name]():
            return 1
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp validate`` to the madmp command."""
    validate = commands.add_parser("validate", help="validate the definitions")
    validate.add_argument(
        "step",
        choices=[*_VALIDATE_STEPS, "frozen", "all"],
        help="one step, or all in this order",
    )
    validate.add_argument(
        "--base",
        metavar="BRANCH",
        default="origin/main",
        help="for frozen and all, the branch or the commit this checkout left "
        "(origin/main)",
    )
    validate.set_defaults(run=_validate)
