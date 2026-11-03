"""The KM bundle, checked against the DSW metamodel, the UUID convention and
the mapping of ``field_kind``, and against one invariant: no event references a
parent nobody emitted."""

import pytest

from madmp.definitions import PROJECTS, load
from madmp.model import model_for
from madmp.packages.common import field_kind, standard_label
from madmp.packages.km import (
    METAMODEL_VERSION,
    VALUE_TYPE_MAP,
    build_km_bundle,
    humanize,
)
from madmp.packages.uuids import (
    answer_uuid,
    chapter_uuid,
    gate_uuid,
    gate_yes_uuid,
    list_item_value_uuid,
    other_answer_uuid,
    other_followup_uuid,
    question_uuid,
)
from tests import ROOT

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"
NIL = "00000000-0000-0000-0000-000000000000"

# Paths chosen for the kind of entity they become, not for their content.
GATED = ("dataset", "distribution", "host")
SUGGESTED = ("contact", "affiliation", "affiliation_id", "type")
MULTI_VALUE = ("dataset", "data_quality_assurance")
# Two vocabularies that spell the escape value themselves: RDA DCS writes it
# ``other``, DataCite writes it ``Other``.
OWN_OTHER = ("dataset", "creator", "creator_id", "type")
OWN_OTHER_MULTI = ("contributor", "role")


@pytest.fixture(scope="module")
def definition():
    return load(PROJECTS, GLIDER_PROJECT)


@pytest.fixture(scope="module")
def model(definition):
    return model_for(definition["rules"])


@pytest.fixture(scope="module")
def events(definition, model):
    return build_km_bundle(definition, model, created_at="2026-01-01T00:00:00.000Z")[
        "packages"
    ][0]["events"]


@pytest.fixture(scope="module")
def by_entity(events):
    return {e["entityUuid"]: e for e in events}


def _children_of(events, parent_uuid):
    return [e for e in events if e["parentUuid"] == parent_uuid]


# The bundle DSW is handed


def test_the_bundle_names_the_project_and_the_metamodel(definition, model, events):
    bundle = build_km_bundle(definition, model, created_at="2026-01-01T00:00:00.000Z")
    package = bundle["packages"][0]
    assert bundle["id"] == f"socib:glider:{definition['version']}"
    assert bundle["kmId"] == "glider"
    assert bundle["metamodelVersion"] == METAMODEL_VERSION
    assert package["id"] == bundle["id"]
    assert package["phase"] == "ReleasedKnowledgeModelPackagePhase"
    assert package["events"] == events


def test_the_description_is_plain_text(definition, model):
    package = build_km_bundle(definition, model)["packages"][0]
    assert "**" not in package["description"] and "](" not in package["description"]
    assert "**" in package["readme"]


def test_two_runs_of_one_project_are_the_same_bundle(definition, model):
    """Everything but the injected timestamp is derived from the project."""
    stamp = "2026-01-01T00:00:00.000Z"
    assert build_km_bundle(definition, model, created_at=stamp) == build_km_bundle(
        definition, model, created_at=stamp
    )


def test_every_event_carries_the_fields_its_metamodel_defines_and_no_others(events):
    """Each ``Add*EventContent`` of DSW's ``kmp_schema_v20.json``, its fields
    written out here: an event carries those and no others."""
    metamodel = {
        "AddKnowledgeModelEvent": {"annotations", "eventType"},
        "AddPhaseEvent": {"annotations", "description", "eventType", "title"},
        "AddTagEvent": {"annotations", "color", "description", "eventType", "name"},
        "AddChapterEvent": {"annotations", "eventType", "text", "title"},
        "AddAnswerEvent": {
            "advice",
            "annotations",
            "eventType",
            "label",
            "metricMeasures",
        },
        "AddChoiceEvent": {"annotations", "eventType", "label"},
    }
    question = {
        "annotations",
        "eventType",
        "questionType",
        "requiredPhaseUuid",
        "tagUuids",
        "text",
        "title",
    }
    questions = {
        "ValueQuestion": question | {"validations", "valueType"},
        "OptionsQuestion": question,
        "ListQuestion": question,
        "MultiChoiceQuestion": question,
    }

    for event in events:
        assert set(event) == {
            "uuid",
            "entityUuid",
            "parentUuid",
            "createdAt",
            "content",
        }
        content = event["content"]
        kind = content["eventType"]
        expected = (
            questions[content["questionType"]]
            if kind == "AddQuestionEvent"
            else metamodel[kind]
        )
        assert set(content) == expected, f"{kind} {content.get('questionType') or ''}"


# The invariant that holds for any project


def test_no_event_references_a_parent_nobody_emitted(events):
    """Every parent is emitted before its children."""
    emitted = {NIL}
    for event in events:
        assert event["parentUuid"] in emitted, event["content"]
        emitted.add(event["entityUuid"])


def test_every_entity_is_emitted_once(events):
    uuids = [e["entityUuid"] for e in events]
    assert len(set(uuids)) == len(uuids)


def test_every_type_asked_as_a_value_has_a_dsw_value_type(definition, model):
    """Every type a ValueQuestion asks has a DSW value type. A boolean is a
    Yes/No OptionsQuestion, a vocabulary its answers."""
    computed = {"dmp_id", "created", "modified"}
    missing = {
        field.type
        for field in model.walk()
        if field_kind(field, computed) in ("value", "value_multi")
        and field.type not in VALUE_TYPE_MAP
    }
    assert missing == set()


# The chapters


def test_the_general_chapter_comes_first_and_the_others_follow_in_order(events):
    chapters = [e for e in events if e["content"]["eventType"] == "AddChapterEvent"]
    titles = [e["content"]["title"] for e in chapters]
    assert titles[0] == "1. DMP General Information"
    assert [t.split(".")[0] for t in titles] == [
        str(i) for i in range(1, len(titles) + 1)
    ]


def test_every_top_level_object_becomes_a_chapter_unless_it_is_computed(
    definition, model, by_entity
):
    """``dmp_id``, a computed top-level object, gets no chapter."""
    computed = {"dmp_id", "created", "modified"}
    for field in model.fields:
        if field.type != "object":
            continue
        if field_kind(field, computed) == "computed":
            assert chapter_uuid(field.name) not in by_entity
            continue
        assert by_entity[chapter_uuid(field.name)]["content"]["title"].endswith(
            humanize(field.name)
        )


def test_a_computed_field_becomes_neither_chapter_nor_question(
    definition, model, by_entity
):
    """``dmp_id``, ``created`` and ``modified`` are filled by the template."""
    for name in ("dmp_id", "created", "modified"):
        assert question_uuid((name,)) not in by_entity
        assert chapter_uuid(name) not in by_entity


def test_the_readme_lists_every_chapter(definition, model, events):
    readme = build_km_bundle(definition, model)["packages"][0]["readme"]
    chapters = [e for e in events if e["content"]["eventType"] == "AddChapterEvent"]
    rows = [line for line in readme.splitlines() if line.startswith("| ")]
    assert len(rows) == len(chapters) + 1  # + the header row


# The questions, kind by kind


def test_an_optional_object_is_asked_behind_a_yes_no_gate(events, by_entity):
    """Its children hang under the Yes answer."""
    gate = by_entity[gate_uuid(GATED)]
    assert gate["content"]["questionType"] == "OptionsQuestion"
    labels = [e["content"]["label"] for e in _children_of(events, gate_uuid(GATED))]
    assert labels == ["Yes", "No"]
    assert _children_of(events, gate_yes_uuid(GATED)) != []


def test_a_suggested_vocabulary_gets_an_other_answer_and_a_follow_up(events, by_entity):
    """One naming no escape of its own gets an "Other" answer opening a
    free-text follow-up."""
    answers = _children_of(events, question_uuid(SUGGESTED))
    labels = [a["content"]["label"] for a in answers]
    assert labels == ["ror", "grid", "isni", "Other"]
    follow_up = by_entity[other_followup_uuid(SUGGESTED)]
    assert follow_up["parentUuid"] == other_answer_uuid(SUGGESTED)
    assert follow_up["content"]["valueType"] == "StringQuestionValueType"


def test_a_vocabulary_that_names_its_own_escape_keeps_it_and_gets_no_second(
    events, by_entity
):
    """A field whose vocabulary names ``other`` is asked like a closed
    vocabulary, its own value in its own spelling and nothing beside it."""
    labels = [
        a["content"]["label"] for a in _children_of(events, question_uuid(OWN_OTHER))
    ]
    assert labels == ["orcid", "isni", "openid", "other"]
    assert other_followup_uuid(OWN_OTHER) not in by_entity


def test_a_multi_choice_vocabulary_keeps_the_escape_it_names(events, by_entity):
    """DataCite's contributorType keeps its ``Other``."""
    labels = [
        a["content"]["label"]
        for a in _children_of(events, question_uuid(OWN_OTHER_MULTI))
    ]
    assert labels[-1] == "Other"
    assert other_followup_uuid(OWN_OTHER_MULTI) not in by_entity


def test_a_repeated_scalar_becomes_a_list_of_one_value_question(events, by_entity):
    """A ListQuestion with a single item template."""
    question = by_entity[question_uuid(MULTI_VALUE)]
    assert question["content"]["questionType"] == "ListQuestion"
    item = by_entity[list_item_value_uuid(MULTI_VALUE)]
    assert item["parentUuid"] == question_uuid(MULTI_VALUE)
    assert item["content"]["questionType"] == "ValueQuestion"


def test_every_question_carries_the_path_it_fills(definition, model, by_entity):
    for field in model.walk():
        event = by_entity.get(question_uuid(field.path))
        if event is None:
            continue
        assert event["content"]["annotations"][0] == {
            "key": "rules_path",
            "value": ".".join(field.path),
        }


def test_no_question_is_asked_without_saying_what_it_fills(events):
    """Every question, the item template of a repeated scalar included,
    carries its path. A chapter may have none, the general one."""
    for event in events:
        if event["content"]["eventType"] != "AddQuestionEvent":
            continue
        keys = [a["key"] for a in event["content"]["annotations"]]
        assert "rules_path" in keys, event["content"]["title"]


# Tags and phases, the two things a researcher navigates by


def test_one_tag_per_standard_shown_the_way_a_standard_is_shown(
    definition, model, events
):
    """Beside the three fixed tags, one per standard, ``rda_dcs`` shown
    ``RDA_DCS``."""
    tags = [e for e in events if e["content"]["eventType"] == "AddTagEvent"]
    names = [t["content"]["name"] for t in tags]
    assert names == [
        "REQUIRED",
        "OPTIONAL",
        "CONTROLLED VOCABULARY",
        *(standard_label(s) for s in model.standards),
    ]


def test_only_required_fields_join_the_required_phase(definition, model, by_entity):
    computed = {"dmp_id", "created", "modified"}
    for field in model.walk():
        event = by_entity.get(question_uuid(field.path))
        if event is None or field_kind(field, computed) == "computed":
            continue
        if "requiredPhaseUuid" not in event["content"]:
            continue
        assert (event["content"]["requiredPhaseUuid"] is not None) == field.is_required


# What DSW checks while the researcher types


def test_a_code_type_is_checked_with_the_assessments_pattern(events, model):
    """A language, a currency or a country code is a string question with the
    field's pattern."""
    patterns = {
        event["content"]["title"]: event["content"]["validations"]
        for event in events
        if event["content"].get("validations")
    }
    by_type = {field.type: field.pattern for field in model.walk()}
    assert patterns["Language"] == [
        {"type": "RegexQuestionValidation", "value": by_type["language"]}
    ]
    assert patterns["Currency Code"] == [
        {"type": "RegexQuestionValidation", "value": by_type["currency"]}
    ]


def test_other_value_questions_carry_no_validation(events):
    """DSW's own value types check a date, an email and a URL."""
    for event in events:
        content = event["content"]
        if content.get("valueType") == "DateQuestionValueType":
            assert content["validations"] == []


def test_a_boolean_reads_yes_and_no(by_entity):
    """Capitalised answers, the value behind each unchanged."""
    path = ("dataset", "is_reused")
    labels = {
        value: by_entity[answer_uuid(path, value)]["content"]["label"]
        for value in ("yes", "no")
    }
    assert labels == {"yes": "Yes", "no": "No"}
