"""Every problem of one attempt in one error, with or without a subject, named
by its subclass."""

import pytest

from madmp.errors import ProblemsError


class _Conflict(ProblemsError):
    noun = "rules conflict"


def test_without_a_subject():
    error = ProblemsError(["a: bad", "b: worse"])
    assert str(error) == "2 problem(s):\n  - a: bad\n  - b: worse"
    assert error.subject is None


def test_with_a_subject():
    error = ProblemsError(["bad"], subject="definitions/rules/test/1.0.0.json")
    assert str(error).startswith("definitions/rules/test/1.0.0.json: 1 problem(s):")
    assert error.subject == "definitions/rules/test/1.0.0.json"


def test_a_subclass_names_its_own_problems():
    assert str(_Conflict(["dmp.title: widens"])).startswith("1 rules conflict(s):")


def test_a_path_subject_is_stringified():
    from pathlib import Path

    assert ProblemsError(["bad"], subject=Path("a/b.json")).subject == "a/b.json"


def test_problems_are_copied_not_aliased():
    accumulated = ["first"]
    error = ProblemsError(accumulated)
    accumulated.append("added afterwards")
    assert error.problems == ["first"]


def test_catchable_as_a_value_error():
    with pytest.raises(ValueError):
        raise _Conflict(["anything"])
