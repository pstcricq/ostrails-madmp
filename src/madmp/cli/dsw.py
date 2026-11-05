"""The ``madmp dsw`` commands, on a running DS Wizard instance: ``admin``,
``publish`` and ``submission``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from madmp.cli import output
from madmp.cli.packages import built, projects
from madmp.definitions import PROJECTS, files, load
from madmp.dsw import admin, client, publish, submission
from madmp.errors import DswError, ProblemsError, PublishError
from madmp.packages.common import utc_timestamp
from madmp.paths import PROJECTS_DIR


def _admin(args: argparse.Namespace) -> int:
    """Make sure of the instance's administrator."""
    try:
        lines = admin.admin(client.from_environment())
    except (PublishError, DswError) as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1
    for line in lines:
        output.ok(line)
    return 0


def _publish(args: argparse.Namespace) -> int:
    """Log in once, then build each project version's packages and upload the
    ones the instance does not hold, oldest first. One time stamp for the
    whole run."""
    try:
        dsw = client.login(client.from_environment())
    except (PublishError, DswError) as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1
    paths = projects(args.projects)
    stamp = utc_timestamp()

    def step(path: Path) -> bool:
        result = built(path, stamp)
        if result is None:
            return False
        definition, _, packages = result
        try:
            lines = publish.publish_packages(
                dsw, definition, packages.km, packages.template
            )
        except DswError as err:
            output.fail(output.shown(path), err)
            return False
        except PublishError as err:
            output.fail(output.shown(path), "\n".join(f"- {p}" for p in err.problems))
            return False
        for line in lines:
            output.ok(f"{definition['id']} {definition['version']} : {line}")
        return True

    failed = output.each(paths, "project version", PROJECTS_DIR, step, "packages")
    if failed is None:
        return 1
    return output.summary(
        len(paths),
        len(failed),
        "project version",
        "published",
        "not published",
        "packages",
    )


def _submission(args: argparse.Namespace) -> int:
    """Log in, then create or refresh the submission service for every
    version of every project the instance holds."""
    try:
        webhook = submission.from_environment()
        dsw = client.login(client.from_environment())
        definitions = [load(PROJECTS, path) for path in files(PROJECTS)]
        line = submission.submission(dsw, definitions, webhook)
    except (ProblemsError, DswError) as err:
        print(f"FAIL {err}", file=sys.stderr)
        return 1
    output.ok(line)
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp dsw`` to the madmp command."""
    dsw = commands.add_parser("dsw", help="a running DS Wizard instance")
    dsw_commands = dsw.add_subparsers(dest="dsw_command", required=True)

    admin_command = dsw_commands.add_parser(
        "admin", help="make sure of DSW's administrator, DSW_USER"
    )
    admin_command.set_defaults(run=_admin)

    publish_command = dsw_commands.add_parser(
        "publish", help="upload the KM and the document template to DSW"
    )
    publish_command.add_argument(
        "projects",
        nargs="*",
        metavar="PROJECT",
        help="definitions/projects/<id>[/<version>.yaml], every version of every "
        "project by default",
    )
    publish_command.set_defaults(run=_publish)

    submission_command = dsw_commands.add_parser(
        "submission", help="set the submission service of DSW"
    )
    submission_command.set_defaults(run=_submission)
