# madmp

[![CI](https://github.com/pstcricq/ostrails-madmp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pstcricq/ostrails-madmp/actions/workflows/ci.yml) [![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org) [![uv](https://img.shields.io/badge/uv-0.12.5-DE5FE9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Machine-actionable Data Management Plans (maDMPs) following the [RDA DMP Common Standard](https://github.com/RDA-DMP-Common/RDA-DMP-Common-Standard), extended by the [OSTrails Application Profile for maDMPs](https://docs.ostrails.eu/en/latest/commons/dmp/application-profile.html).

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/) 0.12.5
- make

## Quick start

```bash
make install
```

`make install` sets up the locked environment in `.venv` and the git hooks. `make help` lists every target.

## CI

The same pipeline runs on GitHub Actions and on GitLab CI, one job per make target of the same name: `lint` and `pre-commit`. `make ci` runs every check of the CI on this machine.

## Test

```bash
make lint
```

`make lint` checks the Python, `make format` fixes what it can, `make pre-commit` runs every hook on every file.

## Licence

Copyright 2026 Pierre St-Cricq dit Lompre (SOCIB), as part of the OSTrails project, funded by the European Union, grant agreement 101130187.

Apache 2.0, see [LICENSE](LICENSE).
