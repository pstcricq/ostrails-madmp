"""Every error this package raises: ``ProblemsError`` and its subclasses for
what the definitions and the packages hold, ``StoreError`` for the DMP
database, ``Refused`` for what the API answers.
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


class DocumentError(ProblemsError):
    """A DMP file that cannot be assessed: unreadable, not JSON, or naming no
    rules, with the path as subject."""

    def __init__(self, problems: list[str], path: str | Path):
        super().__init__(problems, subject=path)


class PackageError(ProblemsError):
    """The two packages built for a project version do not hold: the KM emits
    an entity twice, or the template's body is not Jinja, with the package id
    as subject."""


class StoreError(RuntimeError):
    """The DMP database is not what this package can work with: unnamed by the
    environment, migrated by a newer version, or holding a DMP that cannot
    take the write asked for."""


class DmpNotFoundError(StoreError):
    """No DMP has this key, or it is not one this write can take: a new
    version is written to a production DMP."""


class VersionConflictError(StoreError):
    """A new version based on one that is no longer the latest: somebody else
    wrote in between."""


class Refused(Exception):
    """A request the API refuses, and the HTTP status it answers."""

    status = 400


class RequestError(Refused, ValueError):
    """The request cannot be taken: no such project or project version, a body
    that is not a DMP with its metadata, or metadata naming other rules than
    the project version does."""

    status = 400


class AssessmentError(Refused, ValueError):
    """The document does not hold up against the rules it names."""

    status = 422
