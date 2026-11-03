"""What a check says about one concrete value, on a one-field standard built
by each test, then on the rules of the repository.
"""

import json
from collections import Counter
from dataclasses import replace

import pytest

from madmp.assessment import (
    CheckResult,
    check_conformance,
    has_failures,
    results_to_dicts,
)
from madmp.definitions import PROJECTS, load
from madmp.model import Model, Source, merge_rules, model_for
from madmp.paths import RULES_SCHEMA as SCHEMA_PATH
from tests import ROOT
from tests.unit._described import described

RULES_DIR = ROOT / "definitions" / "rules"
# The scalar types a field may declare: the meta-schema's enumeration, but
# ``object``.
SCALAR_TYPES = sorted(
    set(
        json.loads(SCHEMA_PATH.read_text())["$defs"]["field"]["properties"]["_type"][
            "enum"
        ]
    )
    - {"object"}
)
PROJECT_CONFIGS = sorted((ROOT / "definitions" / "projects").glob("*/*.yaml"))

STRING_1 = {"_cardinality": "1", "_type": "string"}
STRING_01 = {"_cardinality": "0..1", "_type": "string"}
STRING_1N = {"_cardinality": "1..n", "_type": "string"}
STRING_0N = {"_cardinality": "0..n", "_type": "string"}


def _model(tmp_path, dmp, name="base") -> Model:
    """A one-file standard at <standard>/<version>.json."""
    path = tmp_path / name / "1.0.0.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            described(
                {
                    "standard": name,
                    "version": "1.0.0",
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": dmp,
                }
            )
        )
    )
    return merge_rules([path])


def _check(tmp_path, dmp_rules, dmp_document, category=None) -> list[CheckResult]:
    """Every result, or only those of one category."""
    results = check_conformance(_model(tmp_path, dmp_rules), {"dmp": dmp_document})
    return [r for r in results if category is None or r.category == category]


def _statuses(results) -> dict[str, int]:
    return dict(Counter(r.status for r in results))


# A value each scalar type accepts, so a probe document is valid everywhere.
PROBE = {
    "string": "text",
    "number": 1,
    "boolean": True,
    "date": "2026-08-18",
    "datetime": "2026-08-18T09:00:00Z",
    "email": "albert@example.com",
    "url": "https://example.org/a",
    "currency": "EUR",
    "country_code": "ES",
    "language": "eng",
}


def _probe(model) -> dict:
    """A document answering every field the model declares, so that walking it
    reaches all of them. A vocabulary is answered with one of its own values,
    anything else with a value of its declared type."""

    def value(field):
        if field.type == "object":
            answer = {child.name: value(child) for child in field.children}
        elif field.allowed_values or field.suggested_values:
            answer = (field.allowed_values or field.suggested_values)[0]
        else:
            answer = PROBE[field.type]
        return [answer] if field.is_list else answer

    return {"dmp": {field.name: value(field) for field in model.fields}}


# The document's own shape


def test_a_document_with_no_dmp_object_says_only_that(tmp_path):
    results = check_conformance(_model(tmp_path, {"title": dict(STRING_1)}), {"foo": 1})
    assert len(results) == 1
    assert (results[0].category, results[0].status) == ("structure", "fail")


@pytest.mark.parametrize("document", [{"dmp": []}, {"dmp": "x"}, [], "x", None])
def test_anything_that_is_not_a_dmp_object_fails_the_same_way(tmp_path, document):
    """A list, a string, or no mapping at all: none raises."""
    results = check_conformance(_model(tmp_path, {"title": dict(STRING_1)}), document)
    assert [(r.category, r.status) for r in results] == [("structure", "fail")]


def test_a_document_with_a_dmp_object_starts_with_a_pass(tmp_path):
    results = check_conformance(
        _model(tmp_path, {"title": dict(STRING_1)}), {"dmp": {}}
    )
    assert (results[0].category, results[0].status) == ("structure", "pass")


# Presence


def test_a_required_field_that_is_absent_fails(tmp_path):
    results = _check(tmp_path, {"title": dict(STRING_1)}, {}, "presence")
    assert [(r.status, "missing" in r.message) for r in results] == [("fail", True)]


def test_a_required_field_that_is_empty_fails_and_says_so(tmp_path):
    """The empty string is an absence, not a value."""
    results = _check(tmp_path, {"title": dict(STRING_1)}, {"title": ""}, "presence")
    assert [(r.status, "is empty" in r.message) for r in results] == [("fail", True)]


def test_spaces_are_a_value_and_not_an_absence(tmp_path):
    results = _check(tmp_path, {"title": dict(STRING_1)}, {"title": "  "}, "presence")
    assert [r.status for r in results] == ["pass"]


def test_an_optional_field_that_is_absent_is_missing_and_never_fails(tmp_path):
    results = _check(tmp_path, {"note": dict(STRING_01)}, {}, "presence")
    assert [r.status for r in results] == ["missing"]
    assert not has_failures(results)


def test_an_empty_list_is_an_absence(tmp_path):
    required = _check(tmp_path, {"tag": dict(STRING_1N)}, {"tag": []}, "presence")
    optional = _check(tmp_path, {"tag": dict(STRING_0N)}, {"tag": []}, "presence")
    assert [r.status for r in required] == ["fail"]
    assert [r.status for r in optional] == ["missing"]


def test_an_absent_container_reports_once_and_says_nothing_underneath(tmp_path):
    """One result for the container, none for what it would have held."""
    rules = {
        "contact": {
            "_cardinality": "0..1",
            "_type": "object",
            "name": dict(STRING_1),
            "mbox": dict(STRING_1),
        }
    }
    results = _check(tmp_path, rules, {})
    assert [(r.category, r.status, r.instance_path) for r in results][1:] == [
        ("presence", "missing", "dmp.contact")
    ]


# Shape


def test_a_list_field_given_a_scalar_fails(tmp_path):
    results = _check(tmp_path, {"tag": dict(STRING_1N)}, {"tag": "one"}, "shape")
    assert [r.status for r in results] == ["fail"]
    assert "should be a list" in results[0].message


def test_a_single_field_given_a_list_fails(tmp_path):
    results = _check(tmp_path, {"title": dict(STRING_1)}, {"title": ["a"]}, "shape")
    assert [r.status for r in results] == ["fail"]
    assert "should be a single value" in results[0].message


def test_an_object_field_given_a_scalar_fails(tmp_path):
    rules = {"contact": {"_cardinality": "1", "_type": "object", "name": STRING_1}}
    results = _check(tmp_path, rules, {"contact": "Albert"}, "shape")
    assert [r.status for r in results] == ["fail"]
    assert "should be an object" in results[0].message


def test_a_scalar_field_given_an_object_fails(tmp_path):
    results = _check(tmp_path, {"title": dict(STRING_1)}, {"title": {"a": 1}}, "shape")
    assert [r.status for r in results] == ["fail"]
    assert "should be a scalar" in results[0].message


def test_a_list_reports_every_item_at_its_own_index(tmp_path):
    """One rule, several concrete spots: one ``rule_path``, one
    ``instance_path`` per item."""
    rules = {"tag": {"_cardinality": "1..n", "_type": "number"}}
    results = _check(tmp_path, rules, {"tag": [1, "two", 3]}, "type")
    assert [(r.instance_path, r.status) for r in results] == [
        ("dmp.tag[0]", "pass"),
        ("dmp.tag[1]", "fail"),
        ("dmp.tag[2]", "pass"),
    ]
    assert {r.rule_path for r in results} == {"dmp.tag[]"}


# Types


VALID = {
    "string": "text",
    "number": 42,
    "boolean": True,
    "date": "2026-08-18",
    "datetime": "2026-08-18T09:00:00Z",
    "email": "albert@example.com",
    "url": "https://example.com/a",
    "currency": "EUR",
    "country_code": "ES",
    "language": "eng",
}
INVALID = {
    "string": 1,
    "number": True,  # a bool is an int in Python and must not pass as a number
    "boolean": "yes",
    "date": "2026-02-31",  # the calendar has no such day
    "datetime": "not a time",
    "email": "albert.example.com",
    "url": "example.com",
    "currency": "eur",
    "country_code": "ESP",
    "language": "en",
}


@pytest.mark.parametrize("scalar_type", sorted(VALID))
def test_every_scalar_type_accepts_its_own_value(tmp_path, scalar_type):
    rules = {"field": {"_cardinality": "1", "_type": scalar_type}}
    results = _check(tmp_path, rules, {"field": VALID[scalar_type]}, "type")
    assert [r.status for r in results] == ["pass"]


@pytest.mark.parametrize("scalar_type", sorted(INVALID))
def test_every_scalar_type_refuses_what_it_is_not(tmp_path, scalar_type):
    rules = {"field": {"_cardinality": "1", "_type": scalar_type}}
    results = _check(tmp_path, rules, {"field": INVALID[scalar_type]}, "type")
    assert [r.status for r in results] == ["fail"]


def test_a_date_must_be_written_the_one_way(tmp_path):
    """YYYY-MM-DD only, a calendar day."""
    rules = {"field": {"_cardinality": "1", "_type": "date"}}
    assert [
        r.status for r in _check(tmp_path, rules, {"field": "20260818"}, "type")
    ] == ["fail"]


# Vocabularies


def test_a_value_outside_a_closed_vocabulary_fails(tmp_path):
    rules = {
        "kind": {"_cardinality": "1", "_type": "string", "_allowed_values": ["a", "b"]}
    }
    inside = _check(tmp_path, rules, {"kind": "a"}, "allowed_values")
    outside = _check(tmp_path, rules, {"kind": "c"}, "allowed_values")
    assert [r.status for r in inside] == ["pass"]
    assert [r.status for r in outside] == ["fail"]


def test_a_value_outside_a_suggested_vocabulary_only_warns(tmp_path):
    rules = {
        "kind": {
            "_cardinality": "1",
            "_type": "string",
            "_suggested_values": ["a", "b"],
        }
    }
    results = _check(tmp_path, rules, {"kind": "other"}, "suggested_values")
    assert [r.status for r in results] == ["warning"]
    assert not has_failures(results)


# Unexpected keys


def test_a_key_no_rule_declares_fails(tmp_path):
    results = _check(tmp_path, {"title": dict(STRING_1)}, {"title": "t", "who": "x"})
    unexpected = [r for r in results if r.category == "unexpected"]
    assert [(r.status, r.instance_path) for r in unexpected] == [("fail", "dmp.who")]


def test_an_unexpected_key_is_caught_inside_an_object_too(tmp_path):
    rules = {"contact": {"_cardinality": "1", "_type": "object", "name": STRING_1}}
    results = _check(tmp_path, rules, {"contact": {"name": "Albert", "fax": "x"}})
    unexpected = [r for r in results if r.category == "unexpected"]
    assert [r.instance_path for r in unexpected] == ["dmp.contact.fax"]


# Where a constraint came from


def test_a_tightened_field_names_the_standard_that_tightened_it(tmp_path):
    base = tmp_path / "base" / "1.0.0.json"
    base.parent.mkdir(parents=True)
    base.write_text(
        json.dumps(
            described(
                {
                    "standard": "base",
                    "version": "1.0.0",
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": {"title": dict(STRING_01)},
                }
            )
        )
    )
    ext = tmp_path / "ext" / "1.0.0.json"
    ext.parent.mkdir(parents=True)
    ext.write_text(
        json.dumps(
            described(
                {
                    "standard": "ext",
                    "version": "1.0.0",
                    "extends": {"standard": "base", "versions": ["1.0.0"]},
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": {"title": dict(STRING_1)},
                }
            )
        )
    )
    results = check_conformance(merge_rules([base, ext]), {"dmp": {}})
    presence = next(r for r in results if r.category == "presence")
    assert presence.status == "fail"
    assert "required by ext" in presence.message
    assert "0..1 in base" in presence.message


# The single PASS/FAIL rule, and the shape the results travel in


def test_only_a_failure_fails_the_document(tmp_path):
    """Warnings and absences are reported and do not decide."""
    rules = {
        "note": dict(STRING_01),
        "kind": {"_cardinality": "1", "_type": "string", "_suggested_values": ["a"]},
    }
    results = _check(tmp_path, rules, {"kind": "free text"})
    assert _statuses(results)["warning"] == 1
    assert _statuses(results)["missing"] == 1
    assert not has_failures(results)


def test_the_results_are_json(tmp_path):
    results = _check(tmp_path, {"title": dict(STRING_1)}, {"title": "t"})
    dicts = results_to_dicts(results)
    assert json.loads(json.dumps(dicts)) == dicts
    assert set(dicts[0]) == {
        "category",
        "status",
        "rule_path",
        "instance_path",
        "standard",
        "message",
    }


# Against the real rules


@pytest.mark.parametrize("definition", PROJECT_CONFIGS, ids=lambda p: p.stem)
def test_every_project_pins_rules_the_engine_can_check(definition):
    """Every type the rules a project pins declare is one the engine
    checks."""
    model = model_for(load(PROJECTS, definition)["rules"])
    declared = {field.type for field in model.walk() if field.type != "object"}
    assert declared <= set(SCALAR_TYPES)


@pytest.mark.parametrize("definition", PROJECT_CONFIGS, ids=lambda p: p.stem)
def test_every_project_is_walked_whole(definition):
    """Every field the merged rules of each project declare is reported, and
    reported once."""
    model = model_for(load(PROJECTS, definition)["rules"])
    results = check_conformance(model, _probe(model))
    reported = {r.rule_path for r in results if r.category == "presence"}
    assert reported == {field.dotted_path for field in model.walk()}
    assert not [r for r in results if r.category == "unexpected"]


def test_an_empty_document_reports_the_top_level_and_stops_there():
    """Nothing is answered: each top-level field says so once, nothing below
    it is reported."""
    model = model_for(load(PROJECTS, PROJECT_CONFIGS[0])["rules"])
    results = check_conformance(model, {"dmp": {}})
    assert len(results) == len(model.fields) + 1
    assert has_failures(results)


def test_a_field_reports_the_standard_that_introduced_it():
    model = model_for(load(PROJECTS, PROJECT_CONFIGS[0])["rules"])
    document = {"dmp": {"dataset": [{"methodology": "towed"}]}}
    by_path = {
        r.rule_path: r
        for r in check_conformance(model, document)
        if r.category == "presence"
    }
    assert by_path["dmp.title"].standard == "rda_dcs"
    assert by_path["dmp.dataset[].methodology"].standard == "ostrails"


# What the engine can be handed


@pytest.mark.parametrize("scalar_type", SCALAR_TYPES)
def test_the_engine_handles_every_type_the_meta_schema_allows(tmp_path, scalar_type):
    """Every type of the meta-schema's enumeration reaches a verdict, an
    unknown type raising."""
    rules = {"field": {"_cardinality": "1", "_type": scalar_type}}
    results = _check(tmp_path, rules, {"field": "probe"}, "type")
    assert [r.status for r in results] in (["pass"], ["fail"])


def test_a_type_the_engine_does_not_know_raises(tmp_path):
    field = _model(tmp_path, {"field": dict(STRING_1)}).fields[0]
    stand_in = Model(
        fields=(replace(field, type="colour"),),
        sources=(Source("base", "1.0.0", "Base", ()),),
    )
    with pytest.raises(ValueError, match="Unknown scalar type: colour"):
        check_conformance(stand_in, {"dmp": {"field": "x"}})


# Empty items of a list


def test_a_list_of_empty_strings_is_absent(tmp_path):
    presence = _check(
        tmp_path, {"keyword": dict(STRING_1N)}, {"keyword": ["", ""]}, "presence"
    )
    assert [r.status for r in presence] == ["fail"]
    assert "is empty" in presence[0].message


def test_empty_items_are_left_out_and_the_others_keep_their_index(tmp_path):
    results = _check(tmp_path, {"keyword": dict(STRING_0N)}, {"keyword": ["a", "", 3]})
    types = [r for r in results if r.category == "type"]
    assert [(r.instance_path, r.status) for r in types] == [
        ("dmp.keyword[0]", "pass"),
        ("dmp.keyword[2]", "fail"),
    ]


# A datetime is a date and a time


@pytest.mark.parametrize(
    "value, ok",
    [
        ("2026-08-18T09:00:00Z", True),
        ("2026-08-18T09:00", True),
        ("2026-08-18T09:00:00.123+02:00", True),
        ("2026-08-18", False),
        ("20260818T090000", False),
        ("2026-02-30T09:00:00", False),
    ],
)
def test_a_datetime_carries_a_time(tmp_path, value, ok):
    (result,) = _check(
        tmp_path,
        {"created": {"_cardinality": "1", "_type": "datetime"}},
        {"created": value},
        "type",
    )
    assert (result.status == "pass") is ok
