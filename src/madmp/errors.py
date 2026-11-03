"""Every error this package raises: ``ProblemsError`` and its subclasses for
what the definitions hold.
"""

from __future__ import annotations

from pathlib import Path


class ProblemsError(ValueError):
    """Every problem found by one attempt, in one exception.

    Each subclass sets ``noun`` to what its problems are called:
    "3 conflict(s)".

    ``subject`` is what the problems are about when there is a single one, a
    file path typically, and is omitted when they concern a set of things.

    Renders as ``"<subject>: <n> <noun>(s):"`` followed by one indented line
    per problem.
    """

    noun = "problem"

    def __init__(self, problems: list[str], subject: object | None = None):
        self.problems = list(problems)
        self.subject = None if subject is None else str(subject)
        head = "" if self.subject is None else f"{self.subject}: "
        details = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"{head}{len(self.problems)} {self.noun}(s):\n{details}")


class SchemaFileError(ProblemsError):
    """A file is malformed against its schema, with the path as subject.

    Subclassed per kind of file.
    """

    def __init__(self, path: str | Path, problems: list[str]):
        super().__init__(problems, subject=path)

    @property
    def path(self) -> str:
        """The file the problems are about, ``subject``."""
        return self.subject


class RulesFileError(SchemaFileError):
    """A rules file is malformed (schema, coherence or layout)."""


class ProjectFileError(SchemaFileError):
    """A project file is malformed (schema or layout)."""


class UnresolvedPinsError(ProblemsError):
    """Pins that are malformed, or name a rules file that is not there.

    No subject, the problems are about a set of pins.
    """

    noun = "unresolved pin"


class RulesSetError(ProblemsError):
    """The set of rules files is ill-formed: a standard declared twice, not
    exactly one base, an extension of another standard or of another version
    of the base, or, once merged, a field nobody describes."""


class RulesConflictError(ProblemsError):
    """Two rules files disagree on shared fields in ways the merge does not
    allow.

    No subject, the conflicts are about a set of files.
    """

    noun = "rules conflict"
