"""The projects, ``PROJECTS``: ``definitions/projects/<id>/<version>.yaml``,
checked against ``project.schema.json`` and its path.
"""

from __future__ import annotations

from madmp.definitions.loader import Kind
from madmp.errors import ProjectFileError
from madmp.paths import PROJECT_SCHEMA, PROJECTS_DIR

PROJECTS = Kind(
    directory=PROJECTS_DIR,
    schema=PROJECT_SCHEMA,
    key="id",
    suffix=".yaml",
    error=ProjectFileError,
)
