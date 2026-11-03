"""Every DSW entity's UUID: ``uuid5`` over the path of the field it was
generated for, or over a fixed name for what no field produces. Frozen, the
published KMs and templates hold them.
"""

from __future__ import annotations

import uuid

FieldPath = tuple[str, ...]

# Changing it, or a part string passed to u() below, changes every UUID.
NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000000")


def u(*parts: str) -> str:
    """Derive a deterministic entity UUID from a sequence of name parts."""
    return str(uuid.uuid5(NAMESPACE, "::".join(parts)))


def question_uuid(path: FieldPath) -> str:
    """The question entity for a field."""
    return u(*path, "question")


def answer_uuid(path: FieldPath, value: str) -> str:
    """One answer/choice entity of an options question."""
    return u(*path, "answer", value)


def other_answer_uuid(path: FieldPath) -> str:
    """The synthetic "Other" answer of a suggested-values question,
    ``answer_uuid()`` of the value ``"other"``."""
    return u(*path, "answer", "other")


def other_followup_uuid(path: FieldPath) -> str:
    """The free-text follow-up question shown after "Other"."""
    return u(*path, "other-followup", "question")


def list_item_value_uuid(path: FieldPath) -> str:
    """The single item-template ValueQuestion of a "value_multi" field's
    synthetic ListQuestion."""
    return u(*path, "item-value", "question")


def gate_uuid(path: FieldPath) -> str:
    """The Yes/No gate question for a 0..1 object field."""
    return u(*path, "has-question")


def gate_yes_uuid(path: FieldPath) -> str:
    """Its Yes answer, the one that opens the object's own questions."""
    return u(*path, "has-answer", "yes")


def gate_no_uuid(path: FieldPath) -> str:
    """Its No answer, which leads nowhere."""
    return u(*path, "has-answer", "no")


def chapter_uuid(key: str) -> str:
    """A top-level chapter entity, keyed by its dmp field."""
    return u("chapter", key)


def root_uuid() -> str:
    """The KM's root entity."""
    return u("root")


def required_phase_uuid() -> str:
    """The KM's one phase, the one its required questions belong to."""
    return u("phase", "required")


def tag_uuid(name: str) -> str:
    """One of the KM's fixed tags: ``required``, ``optional``, ``cv``."""
    return u("tag", name)


def standard_tag_uuid(standard: str) -> str:
    """The tag of the questions a standard defines, keyed by its code name."""
    return u("tag", "origin", standard)


def event_uuid(entity_uuid: str) -> str:
    """The event that adds an entity to the KM."""
    return u(entity_uuid, "event")


def format_uuid(name: str) -> str:
    """One output format of a project's document template."""
    return u("template", "format", name)


def template_file_uuid(package_id: str, file_name: str) -> str:
    """The Jinja file of a document template, keyed by its package id, a new
    one at each version, and by its name."""
    return u("template", "file", package_id, file_name)
