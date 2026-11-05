"""The ``madmp packages`` commands: ``generate``."""

from __future__ import annotations

import argparse
from pathlib import Path

from madmp.cli import output
from madmp.definitions import PROJECTS, files, load
from madmp.errors import PackageError, ProblemsError
from madmp.model import Model, model_for
from madmp.packages.build import Packages, build, write
from madmp.packages.common import utc_timestamp
from madmp.paths import PROJECTS_DIR


def projects(given: list[str]) -> list[Path]:
    """The project versions named on the command line, a project's directory
    standing for every one of its versions, or every version of every
    project. Each project's oldest version first."""
    if not given:
        return files(PROJECTS)
    paths: list[Path] = []
    for name in given:
        path = Path(name)
        if path.is_dir():
            paths += [p for p in files(PROJECTS, path.parent) if p.parent == path]
        else:
            paths.append(path)
    return paths


def built(path: Path, stamp: str) -> tuple[dict, Model, Packages] | None:
    """A project version's definition, model and packages, or ``None`` once
    its line is printed: a project that does not load is skipped, packages
    that do not hold fail."""
    try:
        definition = load(PROJECTS, path)
        model = model_for(definition["rules"])
    except ProblemsError:
        output.fail(
            output.shown(path), "does not load, see `madmp validate all`.", skip=True
        )
        return None
    try:
        return definition, model, build(definition, model, created_at=stamp)
    except PackageError as err:
        output.fail(output.shown(path), "\n".join(f"- {p}" for p in err.problems))
        return None


def _generate(args: argparse.Namespace) -> int:
    """Build and check each project version's KM and document template, and
    write them into ``--out`` when it is given. One time stamp for the whole
    run."""
    paths = projects(args.projects)
    stamp = utc_timestamp()

    def step(path: Path) -> bool:
        result = built(path, stamp)
        if result is None:
            return False
        definition, model, packages = result
        fields = sum(1 for _ in model.walk())
        line = f"{definition['id']} {definition['version']} : KM and document template"
        if args.out is None:
            output.ok(f"{line}, {fields} fields")
            return True
        km_file, template_file = write(packages, definition, args.out)
        output.ok(f"{line}, {fields} fields, {km_file.name} and {template_file.name}")
        return True

    failed = output.each(paths, "project version", PROJECTS_DIR, step, "packages")
    if failed is None:
        return 1
    written = "" if args.out is None else f", written into {output.shown(args.out)}"
    return output.summary(
        len(paths),
        len(failed),
        "project version",
        f"built{written}",
        "not built",
        "packages",
    )


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Add ``madmp packages`` to the madmp command."""
    packages = commands.add_parser("packages", help="the DS Wizard packages")
    packages_commands = packages.add_subparsers(dest="packages_command", required=True)
    generate = packages_commands.add_parser(
        "generate", help="build and check the KM and the document template"
    )
    generate.add_argument(
        "projects",
        nargs="*",
        metavar="PROJECT",
        help="definitions/projects/<id>[/<version>.yaml], every version of every "
        "project by default",
    )
    generate.add_argument(
        "--out",
        metavar="DIR",
        type=Path,
        help="write the packages into DIR, which is created if missing",
    )
    generate.set_defaults(run=_generate)
