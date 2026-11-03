"""The ``madmp validate`` commands: ``rules``."""

from __future__ import annotations

import argparse
from pathlib import Path

from madmp.cli import output
from madmp.definitions import KINDS, Kind, files, load


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


_VALIDATE_STEPS = {
    kind.name: (lambda kind=kind: _validate_kind(kind)) for kind in KINDS
}


def _validate(args: argparse.Namespace) -> int:
    return _VALIDATE_STEPS[args.step]()


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp validate`` to the madmp command."""
    validate = commands.add_parser("validate", help="validate the definitions")
    validate.add_argument("step", choices=list(_VALIDATE_STEPS), help="the step")
    validate.set_defaults(run=_validate)
