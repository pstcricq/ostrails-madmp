"""The Knowledge Model of a project version: ``build_km_bundle()`` walks the
model and emits DSW's event bundle, each entity under the UUID of its field's
path, the questions in the order a researcher reads them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from madmp.model import Field, Model
from madmp.packages.common import (
    field_kind,
    needs_a_synthetic_escape,
    package_description,
    package_id,
    readme,
    standard_label,
    top_level_split,
    utc_timestamp,
)
from madmp.packages.uuids import (
    answer_uuid,
    chapter_uuid,
    event_uuid,
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
)

# The DSW metamodel version the bundle declares. Its events follow
# kmp_schema_v20.json of https://github.com/ds-wizard/dsw-schemas, no field
# beyond those it defines.
METAMODEL_VERSION = 20

# A scalar field type, as the DSW ValueQuestion value type it is asked with.
VALUE_TYPE_MAP: dict[str, str] = {
    "string": "StringQuestionValueType",
    "number": "NumberQuestionValueType",
    "date": "DateQuestionValueType",
    "email": "EmailQuestionValueType",
    "url": "UrlQuestionValueType",
    "language": "StringQuestionValueType",
    "country_code": "StringQuestionValueType",
    "currency": "StringQuestionValueType",
    "datetime": "DateTimeQuestionValueType",
}

ORIGIN_COLORS = ["#9b59b6", "#e67e22", "#16a085", "#2c3e50", "#f39c12", "#7f8c8d"]

GENERAL_CHAPTER_TITLE = "DMP General Information"
GENERAL_CHAPTER_DESC = "General information about the Data Management Plan."


def validations_for(field: Field) -> list[dict[str, str]]:
    """What DSW checks a value against while it is typed: the field's
    pattern, when it has one."""
    return (
        []
        if field.pattern is None
        else [{"type": "RegexQuestionValidation", "value": field.pattern}]
    )


# How a boolean's two answers read: the value names the answer's uuid, the
# label is what a researcher sees.
BOOLEAN_LABELS = {"yes": "Yes", "no": "No"}


def humanize(key: str) -> str:
    """``"data_type"`` -> ``"Data Type"``."""
    return " ".join(w.capitalize() for w in key.split("_"))


def title_for(field: Field) -> str:
    """A question or chapter title, from the field's own key."""
    return humanize(field.name)


def path_annotation(path: tuple[str, ...]) -> list[dict[str, str]]:
    """The DSW annotation tracing an entity back to the rules field it
    fills."""
    return [{"key": "rules_path", "value": ".".join(path)}]


class KmBuilder:
    """Accumulates the DSW events of one KM generation run."""

    def __init__(self, definition: dict[str, Any], model: Model, created_at: str):
        self.definition = definition
        self.model = model
        self.created_at = created_at
        self.events: list[dict[str, Any]] = []
        self.chapters_toc: list[tuple[str, str]] = []
        self.km_uuid = root_uuid()
        self.phase_uuid = required_phase_uuid()
        self.tag_required = tag_uuid("required")
        self.tag_optional = tag_uuid("optional")
        self.tag_cv = tag_uuid("cv")
        self.tag_origin = {
            origin: standard_tag_uuid(origin) for origin in model.standards
        }

    def emit(self, entity_uuid: str, parent_uuid: str, content: dict[str, Any]) -> None:
        self.events.append(
            {
                "uuid": event_uuid(entity_uuid),
                "entityUuid": entity_uuid,
                "parentUuid": parent_uuid,
                "createdAt": self.created_at,
                "content": content,
            }
        )

    # Root, phase, tags

    def emit_root(self) -> None:
        self.emit(
            self.km_uuid,
            "00000000-0000-0000-0000-000000000000",
            {"eventType": "AddKnowledgeModelEvent", "annotations": []},
        )
        self.emit(
            self.phase_uuid,
            self.km_uuid,
            {
                "eventType": "AddPhaseEvent",
                "annotations": [],
                "title": "Required fields",
                "description": (
                    "Fields the merged rules mark as required (cardinality 1 "
                    "or 1..n). Which standard imposes it is shown by the "
                    "question's own standard tag."
                ),
            },
        )
        for tag, name, color, description in [
            (
                self.tag_required,
                "REQUIRED",
                "#e74c3c",
                (
                    "Required field. The standard tag beside it says which "
                    "standard requires it."
                ),
            ),
            (self.tag_optional, "OPTIONAL", "#95a5a6", "Optional field."),
            (
                self.tag_cv,
                "CONTROLLED VOCABULARY",
                "#3498db",
                "Value taken from a controlled vocabulary.",
            ),
        ]:
            self.emit(
                tag,
                self.km_uuid,
                {
                    "eventType": "AddTagEvent",
                    "annotations": [],
                    "name": name,
                    "color": color,
                    "description": description,
                },
            )
        # One tag per standard, from each file's own ``standard``: its uuid
        # from the code name, the name shown from ``standard_label``.
        for i, origin in enumerate(self.model.standards):
            label = standard_label(origin)
            self.emit(
                self.tag_origin[origin],
                self.km_uuid,
                {
                    "eventType": "AddTagEvent",
                    "annotations": [],
                    "name": label,
                    "color": ORIGIN_COLORS[i % len(ORIGIN_COLORS)],
                    "description": f"Field defined by the {label} standard.",
                },
            )

    def tags_for(self, field: Field) -> list[str]:
        tags = [self.tag_required if field.is_required else self.tag_optional]
        origin_tag = self.tag_origin.get(field.origin)
        if origin_tag is not None:
            tags.append(origin_tag)
        if field.allowed_values is not None or field.suggested_values is not None:
            tags.append(self.tag_cv)
        return tags

    def required_phase_for(self, field: Field) -> str | None:
        return self.phase_uuid if field.is_required else None

    # Question emitters

    def emit_value_question(self, field: Field, parent_uuid: str) -> None:
        self.emit(
            question_uuid(field.path),
            parent_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "ValueQuestion",
                "annotations": path_annotation(field.path),
                "title": title_for(field),
                "text": field.description,
                "requiredPhaseUuid": self.required_phase_for(field),
                "tagUuids": self.tags_for(field),
                "valueType": VALUE_TYPE_MAP[field.type],
                "validations": validations_for(field),
            },
        )

    def emit_options_question(
        self,
        field: Field,
        parent_uuid: str,
        values: list[str],
        escape: bool,
        labels: dict[str, str] | None = None,
    ) -> None:
        """An ``OptionsQuestion`` with one answer per value, plus, when
        ``escape``, an extra "Other" answer opening a free-text follow-up.
        ``labels`` says how a value reads, the value itself by default."""
        q_uuid = question_uuid(field.path)
        self.emit(
            q_uuid,
            parent_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "OptionsQuestion",
                "annotations": path_annotation(field.path),
                "title": title_for(field),
                "text": field.description,
                "requiredPhaseUuid": self.required_phase_for(field),
                "tagUuids": self.tags_for(field),
            },
        )
        for value in values:
            self.emit(
                answer_uuid(field.path, value),
                q_uuid,
                {
                    "eventType": "AddAnswerEvent",
                    "annotations": [],
                    "label": (labels or {}).get(value, value),
                    "advice": None,
                    "metricMeasures": [],
                },
            )
        if escape:
            other_uuid = other_answer_uuid(field.path)
            self.emit(
                other_uuid,
                q_uuid,
                {
                    "eventType": "AddAnswerEvent",
                    "annotations": [],
                    "label": "Other",
                    "advice": None,
                    "metricMeasures": [],
                },
            )
            self.emit(
                other_followup_uuid(field.path),
                other_uuid,
                {
                    "eventType": "AddQuestionEvent",
                    "questionType": "ValueQuestion",
                    "annotations": path_annotation(field.path + ("other",)),
                    "title": f"{title_for(field)} (specify)",
                    "text": (
                        "Suggested values are not exhaustive: enter the value manually."
                    ),
                    "requiredPhaseUuid": self.required_phase_for(field),
                    "tagUuids": [
                        self.tag_required if field.is_required else self.tag_optional
                    ],
                    "valueType": "StringQuestionValueType",
                    "validations": [],
                },
            )

    def emit_multi_choice_question(
        self, field: Field, parent_uuid: str, values: list[str]
    ) -> None:
        q_uuid = question_uuid(field.path)
        self.emit(
            q_uuid,
            parent_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "MultiChoiceQuestion",
                "annotations": path_annotation(field.path),
                "title": title_for(field),
                "text": field.description,
                "requiredPhaseUuid": self.required_phase_for(field),
                "tagUuids": self.tags_for(field),
            },
        )
        for value in values:
            self.emit(
                answer_uuid(field.path, value),
                q_uuid,
                {"eventType": "AddChoiceEvent", "annotations": [], "label": value},
            )

    def emit_other_followup(self, field: Field, parent_uuid: str) -> None:
        """A free-text follow-up beside a suggested MultiChoiceQuestion, the
        manual entry next to the choices."""
        self.emit(
            other_followup_uuid(field.path),
            parent_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "ValueQuestion",
                "annotations": path_annotation(field.path + ("other",)),
                "title": f"{title_for(field)} (specify)",
                "text": (
                    "Suggested values are not exhaustive: enter an additional "
                    "value manually."
                ),
                "requiredPhaseUuid": None,
                "tagUuids": [self.tag_optional],
                "valueType": "StringQuestionValueType",
                "validations": [],
            },
        )

    def emit_multi_value_question(self, field: Field, parent_uuid: str) -> None:
        """A ListQuestion whose single item template is a ValueQuestion: a
        scalar asked as many times as its cardinality allows."""
        q_uuid = question_uuid(field.path)
        self.emit(
            q_uuid,
            parent_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "ListQuestion",
                "annotations": path_annotation(field.path),
                "title": title_for(field),
                "text": field.description,
                "requiredPhaseUuid": self.required_phase_for(field),
                "tagUuids": self.tags_for(field),
            },
        )
        self.emit(
            list_item_value_uuid(field.path),
            q_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "ValueQuestion",
                # The same path as the ListQuestion above it: the list holds
                # the items, this question the value of each.
                "annotations": path_annotation(field.path),
                "title": title_for(field),
                "text": field.description,
                "requiredPhaseUuid": None,
                "tagUuids": [],
                "valueType": VALUE_TYPE_MAP[field.type],
                "validations": validations_for(field),
            },
        )

    def emit_gate(
        self, field: Field, parent_uuid: str, on_yes: Callable[[str], None]
    ) -> None:
        """A Yes/No gate question for a ``0..1`` object: ``on_yes`` emits the
        field's children under the "Yes" answer."""
        gate_q_uuid = gate_uuid(field.path)
        self.emit(
            gate_q_uuid,
            parent_uuid,
            {
                "eventType": "AddQuestionEvent",
                "questionType": "OptionsQuestion",
                "annotations": path_annotation(field.path),
                "title": f"Specify {title_for(field).lower()}?",
                "text": "**Optional.** Answer Yes to provide these details.",
                "requiredPhaseUuid": None,
                "tagUuids": [self.tag_optional],
            },
        )
        yes_uuid = gate_yes_uuid(field.path)
        for a_uuid, label in [(yes_uuid, "Yes"), (gate_no_uuid(field.path), "No")]:
            self.emit(
                a_uuid,
                gate_q_uuid,
                {
                    "eventType": "AddAnswerEvent",
                    "annotations": [],
                    "label": label,
                    "advice": None,
                    "metricMeasures": [],
                },
            )
        on_yes(yes_uuid)

    def process_field(self, field: Field, parent_uuid: str) -> None:
        """Emit the question(s) for one field and its descendants, by the
        field's kind."""
        kind = field_kind(field)
        if kind == "computed":
            return
        if kind == "list":
            q_uuid = question_uuid(field.path)
            self.emit(
                q_uuid,
                parent_uuid,
                {
                    "eventType": "AddQuestionEvent",
                    "questionType": "ListQuestion",
                    "annotations": path_annotation(field.path),
                    "title": title_for(field),
                    "text": field.description,
                    "requiredPhaseUuid": self.required_phase_for(field),
                    "tagUuids": self.tags_for(field),
                },
            )
            for child in field.children:
                self.process_field(child, q_uuid)
        elif kind == "object_gated":
            self.emit_gate(
                field,
                parent_uuid,
                lambda yes_uuid: [
                    self.process_field(child, yes_uuid) for child in field.children
                ],
            )
        elif kind == "object_inline":
            for child in field.children:
                self.process_field(child, parent_uuid)
        elif kind == "options_strict":
            self.emit_options_question(
                field, parent_uuid, list(field.allowed_values), escape=False
            )
        elif kind == "options_suggested":
            self.emit_options_question(
                field,
                parent_uuid,
                list(field.suggested_values),
                escape=needs_a_synthetic_escape(field),
            )
        elif kind == "options_strict_multi":
            self.emit_multi_choice_question(
                field, parent_uuid, list(field.allowed_values)
            )
        elif kind == "options_suggested_multi":
            self.emit_multi_choice_question(
                field, parent_uuid, list(field.suggested_values)
            )
            if needs_a_synthetic_escape(field):
                self.emit_other_followup(field, parent_uuid)
        elif kind == "value_multi":
            self.emit_multi_value_question(field, parent_uuid)
        elif kind == "boolean":
            self.emit_options_question(
                field,
                parent_uuid,
                list(BOOLEAN_LABELS),
                escape=False,
                labels=BOOLEAN_LABELS,
            )
        elif kind == "value":
            self.emit_value_question(field, parent_uuid)
        else:
            # Any other kind is refused.
            raise ValueError(f"{field.dotted_path}: no DSW entity for kind {kind!r}")

    def emit_chapters(self, general: list[Field], chapters: list[Field]) -> None:
        general_uuid = chapter_uuid("general")
        self.chapters_toc.append((GENERAL_CHAPTER_TITLE, GENERAL_CHAPTER_DESC))
        self.emit(
            general_uuid,
            self.km_uuid,
            {
                "eventType": "AddChapterEvent",
                "annotations": [],
                "title": f"1. {GENERAL_CHAPTER_TITLE}",
                "text": GENERAL_CHAPTER_DESC,
            },
        )
        for field in general:
            self.process_field(field, general_uuid)

        # A computed top-level field gets no chapter.
        chapters = [f for f in chapters if field_kind(f) != "computed"]
        for idx, field in enumerate(chapters, start=2):
            chapter_title = humanize(field.name)
            description = field.chapter_description or (
                f"Auto-generated chapter for `dmp.{field.name}`."
            )
            self.emit(
                chapter_uuid(field.name),
                self.km_uuid,
                {
                    "eventType": "AddChapterEvent",
                    "annotations": path_annotation((field.name,)),
                    "title": f"{idx}. {chapter_title}",
                    "text": description,
                },
            )
            self.chapters_toc.append((chapter_title, description))
            self.process_field(field, chapter_uuid(field.name))

    def build_readme(self) -> str:
        body = [
            "## Structure",
            "",
            (
                f"The KM is organised into {len(self.chapters_toc)} chapters "
                f"that directly mirror the rules structure:"
            ),
            "",
            "| # | Chapter | Description |",
            "|---|---------|--------------|",
        ]
        for idx, (title, description) in enumerate(self.chapters_toc, start=1):
            body.append(f"| {idx} | {title} | {description} |")
        return readme(
            self.definition,
            self.model,
            "Knowledge Model",
            body,
            [f"Requires DS Wizard with metamodel version {METAMODEL_VERSION}"],
        )


def build_km_bundle(
    definition: dict[str, Any], model: Model, created_at: str | None = None
) -> dict[str, Any]:
    """The full DSW ``KnowledgeModelPackageBundle`` payload for one project
    version, its ``definition`` and the ``model`` its pins merge into, ready
    for the ``knowledge-model-packages/bundle`` endpoint.

    ``created_at`` defaults to now. Given, two runs give the same bundle.
    """
    created_at = created_at or utc_timestamp()
    pid = package_id(definition)
    builder = KmBuilder(definition, model, created_at)
    builder.emit_root()

    general, chapters = top_level_split(model)
    builder.emit_chapters(general, chapters)

    return {
        "id": pid,
        "kmId": definition["id"],
        "metamodelVersion": METAMODEL_VERSION,
        "name": definition["name"],
        "organizationId": definition["organizationId"],
        "version": definition["version"],
        "packages": [
            {
                "createdAt": created_at,
                "description": package_description(model),
                "events": builder.events,
                "forkOfPackageId": None,
                "id": pid,
                "kmId": definition["id"],
                "license": definition["license"],
                "mergeCheckpointPackageId": None,
                "metamodelVersion": METAMODEL_VERSION,
                "name": definition["name"],
                "nonEditable": False,
                "organizationId": definition["organizationId"],
                "phase": "ReleasedKnowledgeModelPackagePhase",
                "previousPackageId": None,
                "readme": builder.build_readme(),
                "version": definition["version"],
            }
        ],
    }
