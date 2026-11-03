"""What a rules field becomes in a package, every kind ``field_kind`` returns
tried on a field built for it."""

from dataclasses import replace

import pytest
import yaml

from madmp.definitions import PROJECTS, load
from madmp.model import Field, Model, Source, model_for
from madmp.packages.common import (
    COMPUTED_FIELDS,
    FIELD_KINDS,
    field_kind,
    needs_a_synthetic_escape,
    package_description,
    package_id,
    readme,
    standard_label,
    top_level_split,
    utc_timestamp,
)
from madmp.packages.km import build_km_bundle
from madmp.packages.template import build_template_bundle
from tests import ROOT

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"


def _glider_model():
    return model_for(load(PROJECTS, GLIDER_PROJECT)["rules"])


def _field(name="title", path=None, cardinality="0..1", type="string", **kw) -> Field:
    path = path or (name,)
    return Field(
        name=name,
        path=path,
        dotted_path=".".join(path),
        cardinality=cardinality,
        type=type,
        origin="rda_dcs",
        **kw,
    )


# What a field becomes


@pytest.mark.parametrize(
    "expected, field",
    [
        ("value", _field()),
        ("value_multi", _field(cardinality="0..n")),
        ("boolean", _field(type="boolean")),
        ("object_inline", _field(type="object", cardinality="1")),
        ("object_gated", _field(type="object", cardinality="0..1")),
        ("list", _field(type="object", cardinality="0..n")),
        ("options_strict", _field(allowed_values=("a", "b"))),
        ("options_strict_multi", _field(cardinality="1..n", allowed_values=("a",))),
        ("options_suggested", _field(suggested_values=("a", "b"))),
        (
            "options_suggested_multi",
            _field(cardinality="0..n", suggested_values=("a",)),
        ),
    ],
)
def test_every_kind_a_field_can_be(expected, field):
    assert field_kind(field, computed_fields=set()) == expected


_ONE_OF_EACH_KIND = {
    "computed": _field(name="dmp_id"),
    "value": _field(),
    "value_multi": _field(cardinality="0..n"),
    "boolean": _field(type="boolean"),
    "options_strict": _field(allowed_values=("a", "b")),
    "options_suggested": _field(suggested_values=("a", "b")),
    "options_strict_multi": _field(cardinality="0..n", allowed_values=("a",)),
    "options_suggested_multi": _field(cardinality="0..n", suggested_values=("a",)),
    "object_inline": _field(type="object", cardinality="1"),
    "object_gated": _field(type="object", cardinality="0..1"),
    "list": _field(type="object", cardinality="0..n"),
}


def test_the_kinds_are_declared_where_the_generators_read_them():
    """``FIELD_KINDS`` is the whole of what ``field_kind`` answers."""
    assert set(FIELD_KINDS) == set(_ONE_OF_EACH_KIND)
    for kind, field in _ONE_OF_EACH_KIND.items():
        assert field_kind(field, {"dmp_id"}) == kind


@pytest.mark.parametrize("kind", FIELD_KINDS)
def test_both_generators_know_what_to_do_with_every_kind(kind):
    """A field of each kind, through both generators, on a model of one
    field: neither raises, and each puts something in its package."""
    field = _ONE_OF_EACH_KIND[kind]
    if field.type == "object":
        field = replace(
            field, children=(_field(name="leaf", path=(*field.path, "leaf")),)
        )
    definition = yaml.safe_load(GLIDER_PROJECT.read_text())
    model = Model(
        fields=(field,),
        sources=(
            Source("synthetic", "1.0.0", "Synthetic", (("Spec", "https://x.org"),)),
        ),
    )
    km = build_km_bundle(definition, model, created_at="2026-01-01T00:00:00.000Z")
    assert km["packages"][0]["events"], "the KM emitted nothing at all"
    template = build_template_bundle(
        definition, model, created_at="2026-01-01T00:00:00.000Z"
    )
    assert template["files"][0]["content"]


def test_a_strict_vocabulary_wins_over_a_suggested_one():
    """Both set, the allowed list decides."""
    field = _field(allowed_values=("a",), suggested_values=("a", "b"))
    assert field_kind(field, set()) == "options_strict"


def test_only_a_suggested_vocabulary_naming_no_escape_of_its_own_gets_one():
    """A synthetic "Other" answer only where the vocabulary is suggested and
    names no escape itself, ``other`` or ``Other``."""
    assert needs_a_synthetic_escape(_field(suggested_values=("ror", "grid")))
    assert not needs_a_synthetic_escape(_field(suggested_values=("orcid", "other")))
    assert not needs_a_synthetic_escape(_field(suggested_values=("Doer", "Other")))
    # A closed vocabulary admits nothing else, whether or not it names one.
    assert not needs_a_synthetic_escape(_field(allowed_values=("url", "other")))
    assert not needs_a_synthetic_escape(_field(allowed_values=("a", "b")))
    assert not needs_a_synthetic_escape(_field())


def test_computed_applies_to_top_level_fields_only():
    """A nested field named ``dmp_id`` is a question like any other."""
    assert field_kind(_field(name="dmp_id"), {"dmp_id"}) == "computed"
    nested = _field(name="dmp_id", path=("project", "dmp_id"))
    assert field_kind(nested, {"dmp_id"}) == "value"


def test_computed_beats_every_other_kind():
    field = _field(name="created", type="object", cardinality="0..n")
    assert field_kind(field, {"created"}) == "computed"


# Which fields the template fills instead of asking


def test_the_dates_and_the_identifier_are_always_computed():
    assert COMPUTED_FIELDS == {"dmp_id", "created", "modified"}


# The chapter split


def test_objects_become_chapters_and_scalars_stay_general():
    general, chapters = top_level_split(_glider_model())
    assert {f.type for f in chapters} == {"object"}
    assert "object" not in {f.type for f in general}


def test_nothing_is_dropped_by_the_split():
    """A split, not a filter."""
    model = _glider_model()
    general, chapters = top_level_split(model)
    assert len(general) + len(chapters) == len(model.fields)


# How a standard is written, and how it is shown


def test_a_standard_is_shown_in_upper_case():
    assert standard_label("rda_dcs") == "RDA_DCS"
    assert standard_label("ostrails") == "OSTRAILS"


# The rest


def test_the_package_id_is_the_three_fields_dsw_reads():
    """Three fields, in the order DSW reads them, on a definition where all
    three differ. The project of the repository agrees on the two that do not
    change."""
    assert package_id({"organizationId": "o", "id": "p", "version": "9"}) == "o:p:9"
    definition = yaml.safe_load(GLIDER_PROJECT.read_text())
    assert package_id(definition) == f"socib:glider:{definition['version']}"


def test_a_readme_opens_with_the_project_and_ends_with_its_rules():
    """Title and description, the package's own body, its compatibility facts
    then the rules versions, the project's author, and the rules' own
    references, base first."""
    definition = load(PROJECTS, GLIDER_PROJECT)
    model = model_for(definition["rules"])
    lines = readme(
        definition,
        model,
        "Knowledge Model",
        ["## Body", "", "what the package holds"],
        ["Compatible with everything"],
    ).splitlines()
    assert lines[:7] == [
        f"# {definition['name']} : Knowledge Model",
        "",
        package_description(model),
        "",
        "## Body",
        "",
        "what the package holds",
    ]
    compatibility = lines.index("## Compatibility")
    assert lines[compatibility + 2 : compatibility + 4] == [
        "- Compatible with everything",
        "- Rules: RDA_DCS 1.0.0, OSTRAILS 1.0.0",
    ]
    assert f"Developed by: **{definition['author']}**" in lines
    references = lines[lines.index("## References") + 2 :]
    assert references == [
        f"- [{label}]({url})"
        for source in model.sources
        for label, url in source.references
    ]


# What a package says it is


def _model_of(*names: str) -> Model:
    return Model(
        fields=(),
        sources=tuple(
            Source(f"s{i}", "1.0.0", name, ()) for i, name in enumerate(names)
        ),
    )


@pytest.mark.parametrize(
    "names, opening",
    [
        (["A"], "Implements the A in DS Wizard."),
        (["A", "B"], "Implements the A, extended with the B, in DS Wizard."),
        (["A", "B", "C"], "Implements the A, extended with the B and the C, in DS"),
        (
            ["A", "B", "C", "D"],
            "Implements the A, extended with the B, the C and the D, in DS",
        ),
    ],
)
def test_the_description_names_every_standard_base_first(names, opening):
    assert package_description(_model_of(*names)).startswith(opening)


def test_the_glider_description_names_its_two_standards_in_plain_text():
    assert package_description(_glider_model()) == (
        "Implements the RDA DMP Common Standard v1.2 (maDMP), extended with "
        "the OSTrails Application Profile, in DS Wizard. Every field of the "
        "standards is asked to the researcher."
    )


def test_both_packages_set_their_compatibility_facts_the_same_way():
    """Both READMEs get their compatibility facts marked the same way, the
    rules versions last."""
    definition = load(PROJECTS, GLIDER_PROJECT)
    model = model_for(definition["rules"])
    stamp = "2026-01-01T00:00:00.000Z"
    readmes = (
        build_km_bundle(definition, model, created_at=stamp)["packages"][0]["readme"],
        build_template_bundle(definition, model, created_at=stamp)["readme"],
    )
    for text in readmes:
        facts = text.split("## Compatibility\n\n", 1)[1].split("\n\n", 1)[0]
        assert all(line.startswith("- ") for line in facts.splitlines()), facts
        assert facts.splitlines()[-1] == "- Rules: RDA_DCS 1.0.0, OSTRAILS 1.0.0"


def test_the_timestamp_is_the_shape_dsw_expects():
    stamp = utc_timestamp()
    assert len(stamp) == 24 and stamp.endswith(".000Z") and stamp[10] == "T"
