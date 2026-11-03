"""The ``madmp`` command, a group of commands per area. The exit code is 0
when every item passed, 1 otherwise.
"""

from __future__ import annotations

import argparse

from madmp.cli import validate

GROUPS = (validate,)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madmp",
        description="maDMP definitions.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for group in GROUPS:
        group.add_commands(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.run(args)
