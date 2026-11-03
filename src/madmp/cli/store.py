"""The ``madmp store`` commands, on the DMP database the environment names:
``migrate`` and ``sync``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from madmp.cli import output
from madmp.errors import ProblemsError


def _store(command: Callable[..., list[str]], what: str, done_how: str) -> int:
    """Run ``command(conn)`` on the DMP database the environment names, and
    print what it did, one line each, then how many.

    ``madmp.store`` and psycopg are imported on call, psycopg from the
    ``store`` extra.
    """
    import psycopg

    from madmp.errors import StoreError
    from madmp.store import Database

    try:
        database = Database.from_environment()
        with database.connect() as conn:
            done = command(conn)
    # A definition that does not load is a ProblemsError.
    except (StoreError, ProblemsError, psycopg.Error) as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1
    for line in done:
        output.ok(f"{database.name} : {line}")
    print(f"\n{database.name} up to date, {output.count(len(done), what)} {done_how}.")
    return 0


def _store_migrate(args: argparse.Namespace) -> int:
    """Apply the migrations the DMP database has not had."""
    from madmp.store import migrate

    return _store(migrate, "migration", "applied")


def _store_sync(args: argparse.Namespace) -> int:
    """Copy the definitions the DMP database does not hold yet."""
    from madmp.store import sync

    return _store(sync, "definition", "added")


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp store`` to the madmp command."""
    store = commands.add_parser("store", help="the DMP database")
    store_commands = store.add_subparsers(dest="store_command", required=True)
    store_migrate = store_commands.add_parser(
        "migrate", help="bring its tables to this version's schema"
    )
    store_migrate.set_defaults(run=_store_migrate)
    store_sync = store_commands.add_parser(
        "sync", help="copy the rules and the projects into it"
    )
    store_sync.set_defaults(run=_store_sync)
