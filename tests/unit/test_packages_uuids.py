"""The frozen UUIDs of the glider KM and template: a change to the namespace or
to a part string fails these tests.
"""

import uuid

import pytest

from madmp.packages.uuids import (
    NAMESPACE,
    answer_uuid,
    chapter_uuid,
    event_uuid,
    format_uuid,
    gate_no_uuid,
    gate_uuid,
    gate_yes_uuid,
    list_item_value_uuid,
    other_answer_uuid,
    other_followup_uuid,
    question_uuid,
    required_phase_uuid,
    root_uuid,
    standard_tag_uuid,
    tag_uuid,
    template_file_uuid,
    u,
)

# A path per entity kind, whose UUID the glider KM holds.
GATED = ("dataset", "distribution", "host")
SUGGESTED = ("contact", "affiliation", "affiliation_id", "type")
ACCESS = ("dataset", "distribution", "data_access")
QUALITY = ("dataset", "data_quality_assurance")

PUBLISHED = [
    (chapter_uuid("dataset"), "73b95adf-5c95-5cc5-863b-cd8e1e52bdca"),
    (question_uuid(("alternate_identifier",)), "16b224c2-88ad-5be5-8018-0618671980a1"),
    (answer_uuid(ACCESS, "open"), "3849ea1c-53f3-537c-b3e8-24058ebe2c2b"),
    (other_answer_uuid(SUGGESTED), "1e9e14f1-7732-5bf4-9e18-82fa76c9944e"),
    (other_followup_uuid(SUGGESTED), "362df3a0-42dd-5bcd-8ac2-cbd23c1711b1"),
    (list_item_value_uuid(QUALITY), "d0a4d863-4f56-5361-9800-2c6c873eb0d3"),
    (gate_uuid(GATED), "508156e9-39c3-5229-9964-973b299a4b33"),
    (gate_yes_uuid(GATED), "507995df-3bec-59c6-be59-e2061a24ae03"),
    (gate_no_uuid(GATED), "02e5ce05-a749-5bfa-be34-c7166e5f8c2d"),
    (root_uuid(), "f747f052-a4de-5301-8b87-1a4d6daf9f16"),
    (required_phase_uuid(), "0a0ca5ae-18df-51bc-8708-f9183c77480c"),
    (tag_uuid("required"), "e31f152b-1670-5e1f-85ec-decf00e57e3b"),
    (tag_uuid("optional"), "6da1e9c5-a645-5a8a-b543-f8a19bd96bf9"),
    (tag_uuid("cv"), "83088ed3-a963-5fd1-a2d3-1b411ac49a1c"),
    (standard_tag_uuid("rda_dcs"), "7ce81720-6787-57d7-9831-24c3160607a4"),
    (event_uuid(chapter_uuid("dataset")), "2b79c3cf-8513-549f-b006-d627114abf66"),
    (format_uuid("JSON"), "327ec5f0-ca47-50b2-9f86-9524ed97267d"),
    (
        template_file_uuid("socib:glider:1.0.0", "glider.json.j2"),
        "1cf4f59f-9e8a-5c0a-973a-3cc01ba6ee1a",
    ),
]


# The frozen values


@pytest.mark.parametrize("derived, published", PUBLISHED)
def test_every_kind_derives_what_is_already_published(derived, published):
    assert derived == published


def test_the_namespace_is_the_nil_uuid():
    assert NAMESPACE == uuid.UUID("00000000-0000-0000-0000-000000000000")


# What the convention guarantees


def test_one_path_gives_every_kind_a_distinct_identity():
    """A gate question, its two answers and the question itself share a path
    and not a UUID."""
    derived = [
        question_uuid(GATED),
        gate_uuid(GATED),
        gate_yes_uuid(GATED),
        gate_no_uuid(GATED),
        other_followup_uuid(GATED),
        list_item_value_uuid(GATED),
        chapter_uuid("host"),
    ]
    assert len(set(derived)) == len(derived)


def test_the_path_is_what_distinguishes_two_questions():
    """One field name under two parents is two questions."""
    assert question_uuid(("dataset", "title")) != question_uuid(("project", "title"))


# What it does not guarantee, and that is frozen too


def test_the_other_answer_is_the_answer_named_other():
    """A vocabulary listing ``other`` gives its answer the identity of the
    synthetic "Other"."""
    assert other_answer_uuid(SUGGESTED) == answer_uuid(SUGGESTED, "other")


def test_the_parts_are_joined_and_not_escaped():
    """``u`` joins on "::"; no field name carries it."""
    assert u("dataset::title") == u("dataset", "title")
