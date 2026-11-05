"""The ``madmp api`` commands: ``serve``."""

from __future__ import annotations

import argparse
import sys


def _serve(args: argparse.Namespace) -> int:
    """Check the values and the schema, then serve the API until stopped.

    ``madmp.api``, psycopg and uvicorn are imported on call, from the ``api``
    extra.
    """
    import psycopg
    import uvicorn

    from madmp.api.app import app, check_schema, from_environment

    try:
        check_schema(from_environment())
    except (RuntimeError, psycopg.Error) as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp api`` to the madmp command."""
    api = commands.add_parser("api", help="the DMP API")
    api_commands = api.add_subparsers(dest="api_command", required=True)
    serve = api_commands.add_parser("serve", help="serve the DMP API")
    serve.add_argument(
        "--host", default="127.0.0.1", help="the address to listen on (127.0.0.1)"
    )
    serve.add_argument(
        "--port", type=int, default=8081, help="the port to listen on (8081)"
    )
    serve.set_defaults(run=_serve)
