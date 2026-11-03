"""The document template against its KM, both built from one project: every
UUID it reads is one the KM emits, and its body renders a JSON document.
"""

import itertools
import json
import re
from pathlib import Path

import jinja2
import pytest
import yaml

from madmp.definitions import PROJECTS, load
from madmp.model import merge_rules, model_for, resolve_pins
from madmp.packages.km import build_km_bundle
from madmp.packages.template import (
    FORMATS,
    TEMPLATE_METAMODEL_VERSION,
    build_template_bundle,
    q,
)
from madmp.packages.uuids import (
    answer_uuid,
    chapter_uuid,
    other_answer_uuid,
    other_followup_uuid,
    question_uuid,
)
from tests import ROOT
from tests.unit._described import described

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"
STAMP = "2026-01-01T00:00:00.000Z"

# The suggested-vocabulary field whose "Other" sentinel must stay out of AL.
SUGGESTED = ("contact", "affiliation", "affiliation_id", "type")

# A vocabulary that names its own escape value, the way RDA DCS does on every
# identifier type.
OWN_ESCAPE = {
    "id_type": {
        "_cardinality": "1",
        "_type": "string",
        "_suggested_values": ["orcid", "isni", "other"],
    }
}

# An object every standard is entitled to declare: nothing about it is
# required, so the template is handed no key it may emit unconditionally.
ANCHORLESS = {
    "contact": {
        "_cardinality": "1",
        "_type": "object",
        "name": {"_cardinality": "0..1", "_type": "string"},
        "mbox": {"_cardinality": "0..1", "_type": "email"},
    }
}

# A boolean a standard made mandatory, ``0..1`` -> ``1``.
REQUIRED_BOOLEAN = {
    "is_reused": {"_cardinality": "1", "_type": "boolean"},
    "title": {"_cardinality": "1", "_type": "string"},
}

# A vocabulary spelling its values the way an institution's name is spelt.
# The apostrophe closes the Jinja literal ``AL`` holds the label in.
AWKWARD_VOCABULARY = {
    "funder": {
        "_cardinality": "1",
        "_type": "string",
        "_allowed_values": ["Institut d'Optique", 'the "big" one', "back\\slash"],
    }
}

# The same, as a multi-choice: its labels reach the document through a
# different expression.
AWKWARD_MULTI = {
    "keyword": {
        "_cardinality": "0..n",
        "_type": "string",
        "_suggested_values": ["Institut d'Optique", 'the "big" one'],
    }
}

# What a researcher can type in a text field. Each of these ends the JSON
# string it sits in, or, for the tab, is a control character JSON does not
# allow there.
TYPED_BY_HAND = [
    'a "quoted" answer',
    "back\\slash",
    "two\nlines",
    "a\ttab",
    "a\r\nwindows line",
]


@pytest.fixture(scope="module")
def definition():
    return load(PROJECTS, GLIDER_PROJECT)


@pytest.fixture(scope="module")
def model(definition):
    return model_for(definition["rules"])


@pytest.fixture(scope="module")
def bundle(definition, model):
    return build_template_bundle(definition, model, created_at=STAMP)


@pytest.fixture(scope="module")
def body(bundle):
    return bundle["files"][0]["content"]


def _uuids_in(text: str) -> set[str]:
    return set(re.findall(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", text))


class _Ctx:
    """The bits of DSW's render context the template reaches for."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


# The one list item every list question is given, standing in for a UUID DSW
# would mint at runtime. It is not an entity of the KM.
ITEM = "item-0"


class _AnyValue(str):
    """A reply that equals whatever it is compared against: every gate
    opens, and a render walks the whole tree."""

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__


class _Answered:
    """Replies that answer every path asked of them, whatever it is: every
    conditional block opens. ``value`` is what every one of them answers, one
    render putting the same string through every route text takes to the
    document.
    """

    def __init__(self, value: str = "answered") -> None:
        self.value = value

    def __contains__(self, path: str) -> bool:
        return True

    def __getitem__(self, path: str) -> _AnyValue:
        return _AnyValue(self.value)


def _render(
    body: str,
    replies,
    chains: list[list[str]] | None = None,
    items=lambda reply: [ITEM],
) -> dict:
    """The template run by Jinja itself, and the document it produced.

    DSW's three reply filters are stubbed: ``reply_path`` joins a chain of
    UUIDs into one key, ``reply_str_value`` hands back the stored reply, and
    ``reply_items`` gives a list question one item to iterate.

    ``chains`` collects every path the template asks ``reply_path`` for, each
    flattened to its UUIDs, a chain built on another chain arriving already
    joined since that is what the filter returned the first time.

    ``items`` overrides the ``reply_items`` stub. The default hands back one
    item that is not an entity of anything, which is what a list question
    stores. A multi-choice stores the UUIDs of the answers that were chosen,
    and the one test that needs a real label to come back out says so.
    """
    env = jinja2.Environment()

    def reply_path(parts) -> str:
        flat = [uuid_ for part in parts for uuid_ in str(part).split(".")]
        if chains is not None:
            chains.append(flat)
        return ".".join(flat)

    env.filters["reply_path"] = reply_path
    env.filters["reply_str_value"] = lambda reply: reply
    env.filters["reply_items"] = items
    ctx = _Ctx(
        project=_Ctx(
            replies=replies,
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-02T00:00:00Z",
            uuid="1111",
        ),
        config=_Ctx(clientUrl="https://dsw.example"),
    )
    return json.loads(env.from_string(body).render(ctx=ctx))


def _body_from_rules(tmp_path: Path, dmp: dict) -> str:
    """A template built from a rules tree of one's own, on the real
    definition."""
    path = tmp_path / "synthetic" / "1.0.0.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            described(
                {
                    "standard": "synthetic",
                    "version": "1.0.0",
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": dmp,
                }
            )
        )
    )
    definition = yaml.safe_load(GLIDER_PROJECT.read_text())
    bundle = build_template_bundle(definition, merge_rules([path]), created_at=STAMP)
    return bundle["files"][0]["content"]


# What binds the template to its KM


def test_every_uuid_the_template_reads_is_an_entity_the_km_emits(
    definition, model, body
):
    """Every UUID the template reads is one the KM emits."""
    km_entities = {
        event["entityUuid"]
        for event in build_km_bundle(definition, model, created_at=STAMP)["packages"][
            0
        ]["events"]
    }
    assert _uuids_in(body) - km_entities == set()


def test_the_template_reads_every_question_where_the_km_hangs_it(
    definition, model, body
):
    """Every reply path the template assembles, collected by rendering it, is
    the chain of parents the KM hangs the question under, in both directions:
    every chapter and question the KM asks is read, nothing else is. The list
    item DSW mints at runtime drops out of the chain."""
    chains: list[list[str]] = []
    _render(body, _Answered(), chains)
    events = build_km_bundle(definition, model, created_at=STAMP)["packages"][0][
        "events"
    ]
    parent = {event["entityUuid"]: event["parentUuid"] for event in events}
    asked = {
        event["entityUuid"]
        for event in events
        if event["content"]["eventType"] in ("AddQuestionEvent", "AddChapterEvent")
    }

    read = {entity for chain in chains for entity in chain if entity != ITEM}
    assert asked - read == set(), "the KM asks questions the template never reads"
    assert read - set(parent) == set(), "the template reads what the KM never emitted"

    for chain in chains:
        steps = [entity for entity in chain if entity != ITEM]
        for anchor, entity in itertools.pairwise(steps):
            assert parent[entity] == anchor, (
                f"{entity} is read under {anchor}, the KM hangs it on {parent[entity]}"
            )


def test_the_template_is_allowed_to_render_exactly_its_own_km(
    definition, model, bundle
):
    km = build_km_bundle(definition, model, created_at=STAMP)
    assert bundle["id"] == km["id"]
    assert bundle["templateId"] == km["kmId"]
    assert bundle["allowedPackages"] == [
        {
            "kmId": km["kmId"],
            "maxVersion": definition["version"],
            "minVersion": definition["version"],
            "orgId": definition["organizationId"],
        }
    ]


def test_the_answer_table_translates_what_the_km_stores(definition, model, body):
    """Every key of AL is a KM answer."""
    km_entities = {
        event["entityUuid"]
        for event in build_km_bundle(definition, model, created_at=STAMP)["packages"][
            0
        ]["events"]
    }
    al = body.split("{%- set AL = ", 1)[1].split(" -%}", 1)[0]
    assert _uuids_in(al) <= km_entities


def test_a_vocabulary_that_names_its_own_escape_can_render_that_value(tmp_path):
    """Picking the declared ``other`` puts the word in the document."""
    body = _body_from_rules(tmp_path, OWN_ESCAPE)
    asked = f"{chapter_uuid('general')}.{question_uuid(('id_type',))}"
    chosen = answer_uuid(("id_type",), "other")
    assert _render(body, {asked: chosen})["dmp"]["id_type"] == "other"


def test_the_other_sentinel_is_kept_out_of_the_answer_table(body):
    """The synthetic "Other" has no label in AL."""
    al = body.split("{%- set AL = ", 1)[1].split(" -%}", 1)[0]
    assert other_answer_uuid(SUGGESTED) not in al


# What the template must be


def test_the_body_is_jinja_that_parses(body):
    jinja2.Environment().parse(body)


def test_an_unanswered_project_still_renders_valid_json(body):
    """Nothing answered: every conditional block stays shut."""
    document = _render(body, {})
    assert set(document) == {"dmp", "metadata"}
    assert document["dmp"]["dmp_id"] == {
        "identifier": "https://dsw.example/projects/1111",
        "type": "url",
    }


def test_an_answered_project_still_renders_valid_json(body):
    """Everything answered: every block open."""
    document = _render(body, _Answered())
    assert document["dmp"]["title"] == "answered"
    assert document["dmp"]["dataset"][0]["title"] == "answered"


def test_an_object_whose_every_key_is_optional_still_renders_valid_json(tmp_path):
    """``cost { type?, unit? }``, filled and unfilled."""
    body = _body_from_rules(tmp_path, ANCHORLESS)
    answered = f"{chapter_uuid('contact')}.{question_uuid(('contact', 'mbox'))}"

    assert _render(body, {answered: "marie@example.org"})["dmp"]["contact"] == {
        "mbox": "marie@example.org"
    }
    assert _render(body, {})["dmp"]["contact"] == {}


# Nothing that reaches the document can end the string it sits in


@pytest.mark.parametrize("typed", TYPED_BY_HAND, ids=lambda t: repr(t))
def test_anything_a_researcher_can_type_still_renders_valid_json(body, typed):
    """Every path answered with the same string walks every route text
    takes: a plain value, a vocabulary label, and the free text behind a
    synthetic "Other"."""
    document = _render(body, _Answered(typed))
    assert document["dmp"]["title"] == typed
    assert document["dmp"]["dataset"][0]["dataset_id"]["type"] == typed


def test_a_vocabulary_label_with_an_apostrophe_still_gives_a_template(tmp_path):
    """``Institut d'Optique``, a label inside the Jinja literal of AL."""
    body = _body_from_rules(tmp_path, AWKWARD_VOCABULARY)
    jinja2.Environment().parse(body)

    asked = f"{chapter_uuid('general')}.{question_uuid(('funder',))}"
    for label in AWKWARD_VOCABULARY["funder"]["_allowed_values"]:
        chosen = answer_uuid(("funder",), label)
        assert _render(body, {asked: chosen})["dmp"]["funder"] == label


def test_a_multi_choice_array_carries_its_labels_and_its_free_text_intact(tmp_path):
    """A label emitted inside an array, and the free text beside a
    multi-choice, appended to it. ``reply_items`` gives back the UUIDs of the
    answers chosen."""
    body = _body_from_rules(tmp_path, AWKWARD_MULTI)
    labels = AWKWARD_MULTI["keyword"]["_suggested_values"]
    asked = f"{chapter_uuid('general')}.{question_uuid(('keyword',))}"
    typed = f"{chapter_uuid('general')}.{other_followup_uuid(('keyword',))}"
    replies = {
        asked: [answer_uuid(("keyword",), label) for label in labels],
        typed: 'a "manual" keyword',
    }

    document = _render(body, replies, items=lambda reply: reply)
    assert document["dmp"]["keyword"] == [*labels, 'a "manual" keyword']


def test_a_required_boolean_nobody_answered_is_null_and_never_false(tmp_path):
    """A required key is emitted answered or not: ``""`` for a scalar,
    ``null`` for a boolean, never ``false``."""
    body = _body_from_rules(tmp_path, REQUIRED_BOOLEAN)
    asked = f"{chapter_uuid('general')}.{question_uuid(('is_reused',))}"

    unanswered = _render(body, {})["dmp"]
    said_no = _render(body, {asked: answer_uuid(("is_reused",), "no")})["dmp"]
    said_yes = _render(body, {asked: answer_uuid(("is_reused",), "yes")})["dmp"]

    assert unanswered["is_reused"] is None
    assert said_no["is_reused"] is False
    assert said_yes["is_reused"] is True
    assert unanswered["is_reused"] is not said_no["is_reused"]
    # Still emitted at all: the key is what says the field is missing.
    assert "is_reused" in unanswered


def test_an_optional_boolean_is_absent_until_it_is_answered(tmp_path):
    """An unanswered optional key renders nothing at all."""
    optional = dict(
        REQUIRED_BOOLEAN, is_reused={"_cardinality": "0..1", "_type": "boolean"}
    )
    body = _body_from_rules(tmp_path, optional)
    asked = f"{chapter_uuid('general')}.{question_uuid(('is_reused',))}"

    assert "is_reused" not in _render(body, {})["dmp"]
    assert (
        _render(body, {asked: answer_uuid(("is_reused",), "no")})["dmp"]["is_reused"]
        is False
    )


def test_a_uuid_is_quoted_the_same_way_it_always_was():
    assert q(chapter_uuid("general")) == f"'{chapter_uuid('general')}'"


def test_only_an_available_format_becomes_a_dsw_format(bundle):
    """FORMATS declares every format, available or not, for the README table
    and the bundle."""
    assert len(bundle["formats"]) == len([f for f in FORMATS if f["available"]])
    assert bundle["formats"][0]["steps"][0]["options"]["extension"] == "json"
    assert TEMPLATE_METAMODEL_VERSION in bundle["readme"]
    assert all(fmt["name"] in bundle["readme"] for fmt in FORMATS)


# What is computed rather than asked


def test_the_metadata_block_says_what_the_model_merged(definition, model, body):
    """The rules versions read off the merged model, in pin shape, base
    standard first."""
    metadata = _render(body, {})["metadata"]
    assert metadata == {
        "project": definition["id"],
        "project_version": definition["version"],
        "rules": [{name: version} for name, version in model.standard_versions],
    }


def test_the_metadata_block_carries_no_jinja(body):
    """Constants, resolved when the template is generated."""
    # From the last ``"metadata":``, the root one. RDA DCS declares a
    # ``dmp.dataset[].metadata`` too, emitted higher up in the same body.
    start = body.rindex('\n  "metadata": ')
    block = body[start : body.rindex("}\n{% endautoescape %}")]
    assert "{{" not in block
    assert "{%" not in block


def test_the_metadata_block_does_not_depend_on_the_replies(body):
    """Answered or not, the same block."""
    assert _render(body, {})["metadata"] == _render(body, _Answered())["metadata"]


def test_a_computed_field_is_rendered_from_the_project_and_not_from_a_reply(body):
    assert '"created": "{{ ctx.project.createdAt }}"' in body
    assert '"modified": "{{ ctx.project.updatedAt }}"' in body
    assert "{{ ctx.config.clientUrl }}/projects/{{ ctx.project.uuid }}" in body


# The file UUID, derived rather than drawn


def test_two_runs_of_one_project_give_the_same_bundle(definition, model):
    """The file UUID included, derived from the package id."""
    assert build_template_bundle(
        definition, model, created_at=STAMP
    ) == build_template_bundle(definition, model, created_at=STAMP)


def test_bumping_the_project_version_gives_the_file_a_new_uuid(
    definition, model, bundle
):
    definition = dict(definition, version="2.0.0")
    other = build_template_bundle(definition, model, created_at=STAMP)
    assert other["files"][0]["uuid"] != bundle["files"][0]["uuid"]
    assert other["id"] == "socib:glider:2.0.0"


def test_a_different_project_gives_the_file_a_different_uuid(definition, model, bundle):
    definition = dict(definition, id="other-project")
    other = build_template_bundle(definition, model, created_at=STAMP)
    assert other["files"][0]["uuid"] != bundle["files"][0]["uuid"]


# The readme states what the template was built from


def test_the_readme_names_the_base_standard_and_its_extensions(bundle):
    assert "RDA_DCS, extended with OSTRAILS" in bundle["readme"]
    assert "- Rules: RDA_DCS 1.0.0, OSTRAILS 1.0.0" in bundle["readme"]


def test_a_project_on_the_base_standard_alone_says_so(definition):
    model = merge_rules(
        resolve_pins([{"rda_dcs": "1.0.0"}], ROOT / "definitions" / "rules")
    )
    bundle = build_template_bundle(definition, model, created_at=STAMP)
    assert (
        "Structured around the `dmp` root object, covering RDA_DCS." in bundle["readme"]
    )
