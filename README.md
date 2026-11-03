# madmp

[![CI](https://github.com/pstcricq/ostrails-madmp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pstcricq/ostrails-madmp/actions/workflows/ci.yml) [![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org) [![uv](https://img.shields.io/badge/uv-0.12.5-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Machine-actionable Data Management Plans (maDMPs) following the [RDA DMP Common Standard](https://github.com/RDA-DMP-Common/RDA-DMP-Common-Standard), extended by the [OSTrails Application Profile for maDMPs](https://docs.ostrails.eu/en/latest/commons/dmp/application-profile.html).

The rules of a maDMP and the projects that use them are versioned files. From them, `madmp` builds the Knowledge Model and the document template a [DS Wizard](https://ds-wizard.org) instance needs.

## How it works

1. **Rules.** A standard at one version is one JSON file: the base standard, the RDA DMP Common Standard, and the extensions that tighten it, such as the OSTrails profile. An extension may only tighten what the base defines.
2. **Projects.** A project at one version is one YAML file, which pins the rules it is built from. A published version never changes: a change is a new version.
3. **Packages.** The pinned rules merge into one model, from which `madmp` builds a DS Wizard Knowledge Model, the questions, and a document template that renders the answers as a maDMP JSON document.
4. **Assessment.** A DMP is assessed against the rules its metadata names.
5. **DMP database.** A PostgreSQL database of its own, its tables created by `madmp store migrate`.

## What is here

| | |
|---|---|
| [`definitions/rules/`](definitions/rules) | the rules, one JSON file per standard per version, `<standard>/<version>.json`, and `rules.schema.json` |
| [`definitions/projects/`](definitions/projects) | the projects, one YAML file per project per version, `<id>/<version>.yaml`, and `project.schema.json` |
| [`src/madmp/`](src/madmp) | the `madmp` command: validation, assessment, DS Wizard packages, DMP database |
| [`.env.example`](.env.example) | every value the repository reads, with its local value |
| [`tests/`](tests) | the unit and integration tests, and the DMPs they assess (`tests/fixtures/`) |

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.12.5
- make
- Docker, for the integration tests

## Quick start

```bash
make install
make validate-all
make packages-generate OUT=dsw-packages
```

`make install` sets up the locked environment in `.venv`, the `madmp` command and the git hooks. `make help` lists every target, `uv run madmp --help` every command.

## Commands

Each `madmp` command has a make target of the same name: `madmp store migrate` is `make store-migrate`. The targets that reach a server read their values from `ENV_FILE=<file>`, the lines of `.env.example` filled in, else from the environment; a missing value is named, and nothing is done.

### Definitions

| | |
|---|---|
| `make validate-all` | every rules file and project against its schema and its path, the rules each project pins merged, and no published version changed since `origin/main` (`BASE=<branch or commit>`) |
| `make assess-conformance DMP=<file or directory>` | each DMP against the rules its `metadata.rules` pins |
| `make packages-generate` | the Knowledge Model and the document template of every project version, built and checked; `OUT=<directory>` writes them, `PROJECT=definitions/projects/<id>` limits them to one project |

`make validate-rules`, `validate-projects`, `validate-models` and `validate-frozen` each run one step of `validate-all`.

### DMP database

| | |
|---|---|
| `make store-migrate` | the tables of the DMP database, up to date |

The database and its account exist beforehand. One on this machine, at the local values of `.env.example`:

```bash
docker run -d --name dmp-db -p 127.0.0.1:5432:5432 -e POSTGRES_DB=dmp -e POSTGRES_USER=dmp_app -e POSTGRES_PASSWORD=<DMP_PASSWORD> postgres:17.5
```

## CI

The same pipeline runs on GitHub Actions and on GitLab CI, one job per make target of the same name: lint, hooks, validation, packages, unit and integration tests. `make ci` runs every check of the CI on this machine.

## Test

```bash
make test-all
make lint
```

`make test-unit` needs nothing but the repository. `make test-integration` starts a PostgreSQL with docker, and checks the DMP database. `make lint` checks the Python, `make format` fixes what it can, `make pre-commit` runs every hook on every file.

## Licence

Copyright 2026 Pierre St-Cricq dit Lompre (SOCIB), as part of the OSTrails project, funded by the European Union, grant agreement 101130187.

Apache 2.0, see [LICENSE](LICENSE).
