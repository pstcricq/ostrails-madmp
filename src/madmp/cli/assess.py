"""The ``madmp assess`` commands: ``conformance``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from madmp.assessment import STATUSES, check_conformance, envelope, read_document
from madmp.cli import output
from madmp.errors import ProblemsError
from madmp.model import model_for


def _assess_one(path: Path) -> bool:
    """Assess one DMP against the rules it pins, every failing check on its
    own line."""
    try:
        document, pins = read_document(path)
        model = model_for(pins)
    except ProblemsError as err:  # unreadable, unresolved pins, or a bad set
        output.fail(output.shown(path), err)
        return False
    written = envelope(model, check_conformance(model, document), output.shown(path))
    summary = written["summary"]
    counts = ", ".join(f"{summary[status]} {status}" for status in STATUSES)
    head = f"{' + '.join(written['standards'])}, {summary['total']} checks: {counts}"
    if written["verdict"] == "fail":
        failures = "\n".join(
            f"- {row['instance_path']}: {row['message']}" for row in written["fail"]
        )
        output.fail(written["dmp"], f"{head}\n{failures}")
        return False
    output.ok(f"{written['dmp']} : {head}")
    return True


def _documents(given: list[str]) -> list[Path]:
    """The DMP files named on the command line, a directory standing for
    every JSON file in it, by name."""
    paths: list[Path] = []
    for name in given:
        path = Path(name)
        paths += sorted(path.glob("*.json")) if path.is_dir() else [path]
    return paths


def _conformance(args: argparse.Namespace) -> int:
    paths = _documents(args.documents)
    if not paths:
        print("No DMP found.", file=sys.stderr)
        return 1
    failed = [path for path in paths if not _assess_one(path)]
    return output.summary(
        len(paths), len(failed), "DMP", "assessed, none failing", "failing"
    )


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp assess`` to the madmp command."""
    assess = commands.add_parser("assess", help="assess DMPs")
    assess_commands = assess.add_subparsers(dest="assess_command", required=True)
    conformance = assess_commands.add_parser(
        "conformance", help="check DMPs against the rules they pin"
    )
    conformance.add_argument(
        "documents",
        nargs="+",
        metavar="DMP",
        help="a DMP JSON file with its metadata, or a directory of them",
    )
    conformance.set_defaults(run=_conformance)
