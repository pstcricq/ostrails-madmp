"""The definitions, read and validated, one kind per directory of
``definitions/``, validated in the order of ``KINDS``.
"""

from madmp.definitions.loader import Kind, files, load
from madmp.definitions.projects import PROJECTS, ProjectFileError
from madmp.definitions.rules import RULES, RulesFileError, field_children

KINDS = (RULES, PROJECTS)

__all__ = [
    "KINDS",
    "PROJECTS",
    "RULES",
    "Kind",
    "ProjectFileError",
    "RulesFileError",
    "field_children",
    "files",
    "load",
]
