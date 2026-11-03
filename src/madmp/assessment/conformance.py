"""The conformance of one DMP document to the ``Model`` it pins.
``check_conformance()`` walks the model and the document together and returns
one ``CheckResult`` per check, ``fail``, ``missing``, ``warning`` or ``pass``;
``has_failures()`` is the verdict. An empty string, or a list holding nothing
else, counts as absent.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import date, datetime
from importlib.metadata import version
from typing import Any

from madmp.model import Field, Model

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://\S+$")


@dataclass(frozen=True)
class CheckResult:
    """One check on one concrete value, or absence, in the document."""

    # structure, presence, shape, type, allowed_values, suggested_values,
    # unexpected
    category: str
    status: str  # pass | fail | warning | missing
    rule_path: str  # the rule checked, e.g. "dmp.dataset[].distribution[].title"
    instance_path: str  # the concrete spot, e.g. "dmp.dataset[0].distribution[2].title"
    standard: str  # the standard that introduced the field
    message: str


def results_to_dicts(results: list[CheckResult]) -> list[dict[str, Any]]:
    """JSON-ready view of the results."""
    return [asdict(r) for r in results]


def has_failures(results: Iterable[CheckResult]) -> bool:
    """Whether any check is a real violation, which is the whole PASS/FAIL
    rule."""
    return any(r.status == "fail" for r in results)


# The four lists an envelope carries, and the order a reader shows them in,
# from what has to be fixed down to what is already right.
STATUSES = ("fail", "warning", "missing", "pass")


def envelope(model: Model, results: list[CheckResult], dmp: str) -> dict[str, Any]:
    """Everything one check produced, in one shape.

    The results are split by status, in the order of ``STATUSES``, and
    ``len(envelope[status])`` equals ``envelope["summary"][status]`` for each
    of the four.

    ``dmp`` names the file this is about, ``engine`` the version of this
    package that judged it, ``rules_versions`` the rules it judged against.

    No timestamp: the same document gives the same envelope.
    """
    rows = results_to_dicts(results)
    by_status = {
        status: [row for row in rows if row["status"] == status] for status in STATUSES
    }

    return {
        "dmp": str(dmp),
        "standards": list(model.standards),
        "rules_versions": dict(model.standard_versions),
        "verdict": "fail" if has_failures(results) else "pass",
        "engine": version("madmp"),
        "summary": {
            "total": len(rows),
            **{status: len(found) for status, found in by_status.items()},
        },
        **by_status,
    }


# Scalar type and format checks


def _matches(field: Field, value: Any) -> bool:
    """Whether a value is a string matching its field's code pattern."""
    return isinstance(value, str) and bool(re.match(field.pattern, value))


def _check_scalar_type(value: Any, field: Field) -> tuple[bool, str]:
    """Whether one value matches its field's declared scalar type, and what to
    say when it does not."""
    value_type = field.type
    if value_type == "string":
        return isinstance(value, str), "expected a string"
    if value_type == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        return ok, "expected a number"
    if value_type == "boolean":
        return isinstance(value, bool), "expected a boolean"
    if value_type == "date":
        if not isinstance(value, str):
            return False, "expected an ISO 8601 date string (YYYY-MM-DD)"
        # The pattern first, ``date.fromisoformat`` also accepting forms this
        # does not mean, YYYYMMDD and week dates among them. Then the parse,
        # which is what rejects a day the calendar does not have.
        if _DATE_RE.match(value):
            try:
                date.fromisoformat(value)
                return True, ""
            except ValueError:
                pass
        return False, f"{value!r} is not a valid ISO 8601 date (YYYY-MM-DD)"
    if value_type == "datetime":
        if not isinstance(value, str):
            return False, "expected an ISO 8601 datetime string"
        # The date and the time, YYYY-MM-DDTHH:MM at least: the parse alone
        # takes a date by itself for a datetime at midnight.
        if _DATETIME_RE.match(value):
            try:
                datetime.fromisoformat(value)
                return True, ""
            except ValueError:
                pass
        return False, (
            f"{value!r} is not a valid ISO 8601 datetime (YYYY-MM-DDTHH:MM, "
            f"seconds and a time zone optional)"
        )
    if value_type == "language":
        ok = _matches(field, value)
        return ok, f"{value!r} is not an ISO 639-3 language code (3 lowercase letters)"
    if value_type == "email":
        ok = isinstance(value, str) and bool(_EMAIL_RE.match(value))
        return ok, f"{value!r} is not a valid email address"
    if value_type == "currency":
        ok = _matches(field, value)
        return ok, f"{value!r} is not an ISO 4217 currency code (3 uppercase letters)"
    if value_type == "country_code":
        ok = _matches(field, value)
        return ok, f"{value!r} is not an ISO 3166-1 alpha-2 country code"
    if value_type == "url":
        ok = isinstance(value, str) and bool(_URL_RE.match(value))
        return ok, f"{value!r} is not a valid URL"
    raise ValueError(f"Unknown scalar type: {value_type}")


# Walking the model and the document together


def _tightening_note(field: Field, aspect: str) -> str:
    """A parenthesised provenance note when an extension tightened this
    aspect, empty otherwise."""
    for tightening in field.tightenings:
        if tightening.aspect == aspect:
            if aspect == "cardinality":
                return (
                    f" (required by {tightening.standard}, "
                    f"{tightening.before} in {field.origin})"
                )
            return f" (restricted by {tightening.standard})"
    return ""


def _unexpected_keys(
    container: dict,
    known: tuple[Field, ...],
    instance_path: str,
    rule_path: str,
    standard: str,
) -> Iterator[CheckResult]:
    """Every key of one concrete object that matches no declared field: the
    one check that reads the document's keys, every other reads the model's
    fields."""
    names = {child.name for child in known}
    for key in container:
        if key in names:
            continue
        yield CheckResult(
            "unexpected",
            "fail",
            f"{rule_path}.{key}",
            f"{instance_path}.{key}",
            standard,
            f"'{instance_path}.{key}' is not a field the merged rules declare. "
            f"Check the spelling, or whether it belongs to a standard this "
            f"project does not pin.",
        )


def _check_value(field: Field, value: Any, instance_path: str) -> Iterator[CheckResult]:
    """Checks on one present, non-list value of ``field``: its shape, and for a
    scalar its type and vocabularies. Recurses into an object's children."""

    def result(category: str, status: str, message: str) -> CheckResult:
        return CheckResult(
            category, status, field.dotted_path, instance_path, field.origin, message
        )

    if field.type == "object":
        if not isinstance(value, dict):
            yield result(
                "shape",
                "fail",
                f"'{instance_path}' should be an object ({{}}) but is "
                f"{type(value).__name__}.",
            )
            return
        yield result("shape", "pass", f"'{instance_path}' is an object, as expected.")
        yield from _unexpected_keys(
            value, field.children, instance_path, field.dotted_path, field.origin
        )
        for child in field.children:
            yield from _visit(child, value, instance_path)
        return

    if isinstance(value, (dict, list)):
        yield result(
            "shape",
            "fail",
            f"'{instance_path}' should be a scalar value but is "
            f"{'an object' if isinstance(value, dict) else 'a list'}.",
        )
        return
    yield result("shape", "pass", f"'{instance_path}' is a single value, as expected.")

    ok, problem = _check_scalar_type(value, field)
    yield result(
        "type",
        "pass" if ok else "fail",
        f"'{instance_path}' is a valid {field.type}."
        if ok
        else f"'{instance_path}': {problem}.",
    )

    if field.allowed_values is not None:
        if value in field.allowed_values:
            yield result(
                "allowed_values",
                "pass",
                f"'{instance_path}' = {value!r} is an allowed value.",
            )
        else:
            yield result(
                "allowed_values",
                "fail",
                f"'{instance_path}' = {value!r} is not one of the allowed values "
                f"{list(field.allowed_values)}"
                f"{_tightening_note(field, 'allowed_values')}.",
            )

    if field.suggested_values is not None:
        if value in field.suggested_values:
            yield result(
                "suggested_values",
                "pass",
                f"'{instance_path}' = {value!r} matches the suggested values.",
            )
        else:
            yield result(
                "suggested_values",
                "warning",
                f"'{instance_path}' = {value!r} is not one of the suggested values "
                f"{list(field.suggested_values)}"
                f"{_tightening_note(field, 'suggested_values')}.",
            )


def _visit(field: Field, container: dict, parent_path: str) -> Iterator[CheckResult]:
    """All checks for ``field`` inside one concrete parent object, recursing
    into descendants.

    An absent or empty field yields exactly one presence result and nothing
    underneath.
    """
    value = container.get(field.name)
    instance_path = f"{parent_path}.{field.name}"
    # The items of a list that hold something, at their index in the document.
    answered = (
        [(index, item) for index, item in enumerate(value) if item != ""]
        if field.is_list and isinstance(value, list)
        else None
    )

    def result(category: str, status: str, message: str) -> CheckResult:
        return CheckResult(
            category, status, field.dotted_path, instance_path, field.origin, message
        )

    if value is None or value == "" or answered == []:
        if field.is_required:
            what = "is missing" if value is None else "is empty"
            yield result(
                "presence",
                "fail",
                f"Required field '{instance_path}' (cardinality "
                f"{field.cardinality}) {what}"
                f"{_tightening_note(field, 'cardinality')}.",
            )
        else:
            yield result(
                "presence", "missing", f"Optional field '{instance_path}' is absent."
            )
        return

    yield result("presence", "pass", f"'{instance_path}' is present.")

    if field.is_list:
        if not isinstance(value, list):
            yield result(
                "shape",
                "fail",
                f"'{instance_path}' should be a list (cardinality "
                f"{field.cardinality}) but is {type(value).__name__}.",
            )
            return
        yield result(
            "shape",
            "pass",
            f"'{instance_path}' is a list of {len(answered)}, as expected.",
        )
        for index, item in answered:
            yield from _check_value(field, item, f"{instance_path}[{index}]")
        return

    if isinstance(value, list):
        yield result(
            "shape",
            "fail",
            f"'{instance_path}' should be a single value (cardinality "
            f"{field.cardinality}) but is a list.",
        )
        return
    yield from _check_value(field, value, instance_path)


def check_conformance(model: Model, document: Any) -> list[CheckResult]:
    """Check ``document``, a parsed DMP JSON, against ``model``.

    Always starts with one ``structure`` result: the document must be an
    object holding a ``dmp`` object. Without that, it is the only result.
    """
    dmp = document.get("dmp") if isinstance(document, dict) else None
    if not isinstance(dmp, dict):
        return [
            CheckResult(
                "structure",
                "fail",
                "dmp",
                "dmp",
                model.base_standard,
                "Document has no top-level 'dmp' object, nothing to check.",
            )
        ]

    results = [
        CheckResult(
            "structure",
            "pass",
            "dmp",
            "dmp",
            model.base_standard,
            "Top-level 'dmp' object found.",
        )
    ]
    results.extend(
        _unexpected_keys(dmp, model.fields, "dmp", "dmp", model.base_standard)
    )
    for field in model.fields:
        results.extend(_visit(field, dmp, "dmp"))
    return results
