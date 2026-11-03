"""The rules files of the repository merge into one Model, and the merge
accepts and records every tightening and refuses every loosening, reshaping or
widening."""

import json
from itertools import permutations

import pytest

from madmp.definitions import PROJECTS, load
from madmp.model import (
    Model,
    RulesConflictError,
    RulesSetError,
    Source,
    merge_rules,
    model_for,
)
from tests import ROOT
from tests.unit._described import described

RULES_DIR = ROOT / "definitions" / "rules"
REAL_FILES = [
    RULES_DIR / "rda_dcs" / "1.0.0.json",
    RULES_DIR / "ostrails" / "1.0.0.json",
]


# The real files


def test_real_files_merge():
    model = merge_rules(REAL_FILES)
    assert model.base_standard == "rda_dcs"
    assert model.extension_standards == ("ostrails",)


def test_real_files_input_order_does_not_matter():
    shuffled = merge_rules([REAL_FILES[1], REAL_FILES[0]])
    assert shuffled.base_standard == "rda_dcs"


def test_real_files_origins():
    model = merge_rules(REAL_FILES)
    by_path = {f.dotted_path: f for f in model.walk()}
    # A base field, an extension's own new field, and a structural parent the
    # extension redeclares to reach its own leaves (base origin must win).
    assert by_path["dmp.title"].origin == "rda_dcs"
    assert by_path["dmp.dataset[].methodology"].origin == "ostrails"
    assert by_path["dmp.dataset[]"].origin == "rda_dcs"


def test_real_files_walk_covers_every_field():
    model = merge_rules(REAL_FILES)
    fields = list(model.walk())
    assert len(fields) > 100
    assert all(f.dotted_path.startswith("dmp.") for f in fields)


# Synthetic bases/extensions for the merge semantics


def _doc(tmp_path, name, extends, dmp, version="1.0.0", base="base"):
    # At <standard>/<version>.json, where the document says it is.
    path = tmp_path / name / f"{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            described(
                {
                    "standard": name,
                    "version": version,
                    **(
                        {"extends": {"standard": base, "versions": ["1.0.0"]}}
                        if extends
                        else {}
                    ),
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": dmp,
                }
            )
        )
    )
    return path


def _merge(tmp_path, base_dmp, ext_dmp) -> Model:
    return merge_rules(
        [_doc(tmp_path, "base", False, base_dmp), _doc(tmp_path, "ext", True, ext_dmp)]
    )


def _merge_conflicts(tmp_path, base_dmp, ext_dmp) -> str:
    with pytest.raises(RulesConflictError) as excinfo:
        _merge(tmp_path, base_dmp, ext_dmp)
    return str(excinfo.value)


STRING_1 = {"_cardinality": "1", "_type": "string"}
STRING_01 = {"_cardinality": "0..1", "_type": "string"}


def test_new_extension_field_stamped_with_its_origin(tmp_path):
    model = _merge(
        tmp_path,
        {"title": dict(STRING_1)},
        {
            "extra": {
                "_cardinality": "0..1",
                "_type": "object",
                "_description": "Added by ext.",
                "name": {**STRING_1, "_description": "Added by ext."},
            }
        },
    )
    by_path = {f.dotted_path: f for f in model.walk()}
    assert by_path["dmp.title"].origin == "base"
    assert by_path["dmp.extra"].origin == "ext"
    assert by_path["dmp.extra.name"].origin == "ext"  # whole subtree stamped


def test_identical_redeclaration_merges_silently(tmp_path):
    model = _merge(tmp_path, {"title": dict(STRING_1)}, {"title": dict(STRING_1)})
    (title,) = model.walk()
    assert title.origin == "base"
    assert title.tightenings == ()


def test_cardinality_tightening_accepted_and_recorded(tmp_path):
    model = _merge(tmp_path, {"title": dict(STRING_01)}, {"title": dict(STRING_1)})
    (title,) = model.walk()
    assert title.cardinality == "1"
    assert title.is_required
    (tightening,) = title.tightenings
    assert (tightening.standard, tightening.aspect) == ("ext", "cardinality")
    assert (tightening.before, tightening.after) == ("0..1", "1")


def test_cardinality_loosening_rejected(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path, {"title": dict(STRING_1)}, {"title": dict(STRING_01)}
    )
    assert "loosens" in conflicts


def test_cardinality_reshaping_rejected(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path,
        {"keyword": {"_cardinality": "0..n", "_type": "string"}},
        {"keyword": dict(STRING_1)},
    )
    assert "shape" in conflicts


def test_type_disagreement_rejected(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path,
        {"issued": {"_cardinality": "1", "_type": "date"}},
        {"issued": {"_cardinality": "1", "_type": "string"}},
    )
    assert "_type" in conflicts


def test_vocabulary_subset_accepted_and_recorded(tmp_path):
    model = _merge(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt", "dm"]}},
        {"mode": {**STRING_1, "_allowed_values": ["rt"]}},
    )
    (mode,) = model.walk()
    assert mode.allowed_values == ("rt",)
    (tightening,) = mode.tightenings
    assert tightening.aspect == "allowed_values"
    assert tightening.before == ["rt", "dt", "dm"]


def test_vocabulary_widening_rejected(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["rt", "track"]}},
    )
    assert "widens" in conflicts
    assert "track" in conflicts


def test_extension_may_close_an_open_field(tmp_path):
    model = _merge(
        tmp_path,
        {"language": dict(STRING_01)},
        {"language": {**STRING_01, "_suggested_values": ["eng", "spa", "cat"]}},
    )
    (language,) = model.walk()
    assert language.suggested_values == ("eng", "spa", "cat")
    (tightening,) = language.tightenings
    assert tightening.before is None


def test_a_suggested_vocabulary_may_be_closed_over_its_own_values(tmp_path):
    """The field comes out closed, holding one vocabulary and not two."""
    model = _merge(
        tmp_path,
        {"mode": {**STRING_1, "_suggested_values": ["rt", "dt", "dm"]}},
        {"mode": {**STRING_1, "_allowed_values": ["dm", "rt"]}},
    )
    (mode,) = model.walk()
    assert mode.allowed_values == ("rt", "dm")
    assert mode.suggested_values is None
    # Two records: the recommendation dropped, the field closed.
    dropped, closed = mode.tightenings
    assert (dropped.aspect, dropped.after) == ("suggested_values", None)
    assert (closed.aspect, closed.before) == ("allowed_values", None)


def test_closing_a_suggested_vocabulary_outside_it_rejected(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path,
        {"mode": {**STRING_1, "_suggested_values": ["rt", "dt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["track"]}},
    )
    assert "does not recommend" in conflicts
    assert "track" in conflicts


def test_a_closed_vocabulary_may_not_be_offered_back_as_suggested(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt"]}},
        {"mode": {**STRING_1, "_suggested_values": ["rt", "dt"]}},
    )
    assert "_suggested_values where base closed" in conflicts


def test_reordering_a_vocabulary_is_not_a_tightening(tmp_path):
    """Same values, another order: a redeclaration."""
    model = _merge(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt", "dm"]}},
        {"mode": {**STRING_1, "_allowed_values": ["dm", "dt", "rt"]}},
    )
    (mode,) = model.walk()
    assert mode.allowed_values == ("rt", "dt", "dm")
    assert mode.tightenings == ()


def test_a_restriction_keeps_the_base_order(tmp_path):
    """The order stays the base standard's, whatever order the subset is
    written in."""
    model = _merge(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt", "dm"]}},
        {"mode": {**STRING_1, "_allowed_values": ["dm", "rt"]}},
    )
    (mode,) = model.walk()
    assert mode.allowed_values == ("rt", "dm")


def test_an_extension_may_repeat_a_description_word_for_word(tmp_path):
    model = _merge(
        tmp_path,
        {"title": {**STRING_1, "_description": "Base says."}},
        {"title": {**STRING_1, "_description": "Base says."}},
    )
    by_path = {f.dotted_path: f for f in model.walk()}
    assert by_path["dmp.title"].description == "Base says."


def test_two_files_describing_one_field_differently_is_a_conflict(tmp_path):
    with pytest.raises(RulesConflictError) as raised:
        _merge(
            tmp_path,
            {"title": {**STRING_1, "_description": "Base says."}},
            {"title": {**STRING_1, "_description": "Ext says."}},
        )
    (problem,) = raised.value.problems
    assert "dmp.title" in problem and "_description" in problem
    assert "base" in problem and "ext" in problem


# Several extensions: each is judged against the base, and what they require
# combines.


def _merge_three(tmp_path, base_dmp, first_dmp, second_dmp) -> Model:
    return merge_rules(
        [
            _doc(tmp_path, "base", False, base_dmp),
            _doc(tmp_path, "ext_one", True, first_dmp),
            _doc(tmp_path, "ext_two", True, second_dmp),
        ]
    )


def _merge_three_conflicts(tmp_path, base_dmp, first_dmp, second_dmp) -> str:
    with pytest.raises(RulesConflictError) as excinfo:
        _merge_three(tmp_path, base_dmp, first_dmp, second_dmp)
    return str(excinfo.value)


def test_an_extension_may_restate_the_base_another_extension_tightened(tmp_path):
    """ext_two repeats what the base says, after ext_one required the
    field."""
    model = _merge_three(
        tmp_path,
        {"title": dict(STRING_01)},
        {"title": dict(STRING_1)},
        {"title": dict(STRING_01)},
    )
    (title,) = model.walk()
    assert title.cardinality == "1"


def test_extension_order_does_not_change_the_verdict(tmp_path):
    """The same files in the other order: same model, not a conflict."""
    one = {"title": dict(STRING_1)}
    two = {"title": dict(STRING_01)}
    swapped = _merge_three(tmp_path, {"title": dict(STRING_01)}, two, one)
    (title,) = swapped.walk()
    assert title.cardinality == "1"


def test_restrictions_from_two_extensions_combine(tmp_path):
    """Both restrict the base vocabulary: the field holds their
    intersection, in the base's order."""
    model = _merge_three(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt", "dm"]}},
        {"mode": {**STRING_1, "_allowed_values": ["dm", "rt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["dt", "dm"]}},
    )
    (mode,) = model.walk()
    assert mode.allowed_values == ("dm",)


def test_irreconcilable_restrictions_rejected(tmp_path):
    """An empty intersection is one conflict, naming both standards."""
    conflicts = _merge_three_conflicts(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["rt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["dt"]}},
    )
    assert "no value satisfies both" in conflicts
    assert "ext_one" in conflicts and "ext_two" in conflicts


def test_a_vocabulary_restated_from_the_base_is_a_no_op(tmp_path):
    """ext_two repeats the base vocabulary, ext_one's restriction stands."""
    model = _merge_three(
        tmp_path,
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["rt"]}},
        {"mode": {**STRING_1, "_allowed_values": ["rt", "dt"]}},
    )
    (mode,) = model.walk()
    assert mode.allowed_values == ("rt",)


def test_every_order_of_three_extensions_gives_the_same_model(tmp_path):
    """Every permutation: a cardinality tightened by one and restated by
    another, and vocabularies restricted from both sides."""
    base = _doc(
        tmp_path,
        "base",
        False,
        {
            "title": dict(STRING_01),
            "mode": {**STRING_1, "_allowed_values": list("abcd")},
        },
    )
    extensions = [
        _doc(tmp_path, "one", True, {"title": dict(STRING_1)}),
        _doc(
            tmp_path,
            "two",
            True,
            {"mode": {**STRING_1, "_allowed_values": list("abc")}},
        ),
        _doc(
            tmp_path,
            "three",
            True,
            {
                "title": dict(STRING_01),
                "mode": {**STRING_1, "_allowed_values": list("bcd")},
            },
        ),
    ]
    models = {
        tuple(
            (f.dotted_path, f.cardinality, f.allowed_values)
            for f in merge_rules([base, *order]).walk()
        )
        for order in permutations(extensions)
    }
    assert len(models) == 1
    assert models.pop() == (
        ("dmp.title", "1", None),
        ("dmp.mode", "1", ("b", "c")),
    )


def test_all_conflicts_reported_at_once(tmp_path):
    conflicts = _merge_conflicts(
        tmp_path,
        {"title": dict(STRING_1), "issued": {"_cardinality": "1", "_type": "date"}},
        {
            "title": dict(STRING_01),
            "issued": {"_cardinality": "1", "_type": "string"},
        },
    )
    assert "dmp.title" in conflicts
    assert "dmp.issued" in conflicts


# Ill-formed sets of files


def test_two_bases_rejected(tmp_path):
    with pytest.raises(RulesSetError, match="exactly one base"):
        merge_rules(
            [
                _doc(tmp_path, "a", False, {"title": dict(STRING_1)}),
                _doc(tmp_path, "b", False, {"title": dict(STRING_1)}),
            ]
        )


def test_no_base_rejected(tmp_path):
    with pytest.raises(RulesSetError, match="exactly one base"):
        merge_rules([_doc(tmp_path, "a", True, {"title": dict(STRING_1)})])


def test_duplicate_standard_names_rejected(tmp_path):
    first = _doc(tmp_path, "a", False, {"title": dict(STRING_1)})
    # Same standard at another version: two files, one name, distinct paths.
    duplicate = _doc(tmp_path, "a", True, {"title": dict(STRING_1)}, version="2.0.0")
    with pytest.raises(RulesSetError, match="unique"):
        merge_rules([first, duplicate])


def test_every_problem_with_the_set_is_reported_at_once(tmp_path):
    """A duplicate standard and a missing base, reported together."""
    files = [
        _doc(tmp_path, "a", True, {"title": dict(STRING_1)}),
        _doc(tmp_path, "a", True, {"title": dict(STRING_1)}, version="2.0.0"),
    ]
    with pytest.raises(RulesSetError) as excinfo:
        merge_rules(files)
    assert len(excinfo.value.problems) == 2
    assert "unique" in excinfo.value.problems[0]
    assert "exactly one base" in excinfo.value.problems[1]


# Versions


def test_versioned_paths_merge_and_stamp_their_versions(tmp_path):
    root = tmp_path / "standards"
    for standard, version, extends in (
        ("rda_dcs", "1.0.0", False),
        ("ostrails", "2.1.0", True),
    ):
        path = root / standard / f"{version}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                described(
                    {
                        "standard": standard,
                        "version": version,
                        **(
                            {"extends": {"standard": "rda_dcs", "versions": ["1.0.0"]}}
                            if extends
                            else {}
                        ),
                        "name": "Test standard",
                        "references": [{"label": "Spec", "url": "https://example.org"}],
                        "dmp": {"title": dict(STRING_1)},
                    }
                )
            )
        )
    model = merge_rules(
        [root / "rda_dcs" / "1.0.0.json", root / "ostrails" / "2.1.0.json"]
    )
    assert model.standard_versions == (("rda_dcs", "1.0.0"), ("ostrails", "2.1.0"))


def test_model_stamps_the_declared_version_not_the_filename(tmp_path):
    # The version the document declares.
    path = _doc(tmp_path, "base", False, {"title": dict(STRING_1)}, version="3.2.1")
    assert merge_rules([path]).standard_versions == (("base", "3.2.1"),)


def test_real_files_merge_from_their_versioned_paths():
    model = merge_rules(REAL_FILES)
    assert model.standard_versions == (
        ("rda_dcs", "1.0.0"),
        ("ostrails", "1.0.0"),
    )


# Field properties


def test_dotted_path_marks_every_list_ancestor(tmp_path):
    model = _merge(
        tmp_path,
        {
            "dataset": {
                "_cardinality": "1..n",
                "_type": "object",
                "distribution": {
                    "_cardinality": "0..n",
                    "_type": "object",
                    "title": dict(STRING_1),
                },
            }
        },
        # The extension redeclares a whole base branch identically, down to
        # a leaf: the walk is unchanged.
        {
            "dataset": {
                "_cardinality": "1..n",
                "_type": "object",
                "distribution": {
                    "_cardinality": "0..n",
                    "_type": "object",
                    "title": dict(STRING_1),
                },
            }
        },
    )
    paths = [f.dotted_path for f in model.walk()]
    assert paths == [
        "dmp.dataset[]",
        "dmp.dataset[].distribution[]",
        "dmp.dataset[].distribution[].title",
    ]


# Model properties, and the record of tightenings


def test_is_list_reads_the_cardinality():
    model = merge_rules(REAL_FILES)
    by_path = {f.dotted_path: f for f in model.walk()}
    assert by_path["dmp.dataset[]"].is_list
    assert not by_path["dmp.title"].is_list


def test_standards_is_the_base_then_its_extensions():
    assert merge_rules(REAL_FILES).standards == ("rda_dcs", "ostrails")


def test_an_identical_vocabulary_records_no_tightening(tmp_path):
    """Redeclaring a vocabulary unchanged leaves no Tightening."""
    vocabulary = {**STRING_1, "_allowed_values": ["rt", "dt"]}
    model = _merge(tmp_path, {"mode": dict(vocabulary)}, {"mode": dict(vocabulary)})
    (mode,) = model.walk()
    assert mode.allowed_values == ("rt", "dt")
    assert mode.tightenings == ()


def test_a_vocabulary_tightening_is_recorded_under_its_aspect_name(tmp_path):
    model = _merge(
        tmp_path,
        {"mode": {**STRING_1, "_suggested_values": ["rt", "dt"]}},
        {"mode": {**STRING_1, "_suggested_values": ["rt"]}},
    )
    (tightening,) = next(model.walk()).tightenings
    assert tightening.aspect == "suggested_values"


def test_the_model_keeps_each_standard_name_and_references_base_first():
    glider = RULES_DIR.parent / "projects" / "glider" / "1.0.0.yaml"
    sources = model_for(load(PROJECTS, glider)["rules"]).sources
    assert [s.standard for s in sources] == ["rda_dcs", "ostrails"]
    assert sources[0] == Source(
        standard="rda_dcs",
        version="1.0.0",
        name="RDA DMP Common Standard v1.2 (maDMP)",
        references=(
            (
                "RDA DMP Common Standard specification",
                "https://github.com/RDA-DMP-Common/RDA-DMP-Common-Standard",
            ),
            ("RDA DCS DOI", "http://doi.org/10.15497/rda00039"),
        ),
    )


# What an extension extends


def test_an_extension_of_another_standard_is_refused(tmp_path):
    files = [
        _doc(tmp_path, "base", False, {"title": dict(STRING_1)}),
        _doc(tmp_path, "ext", True, {"title": dict(STRING_1)}, base="other"),
    ]
    with pytest.raises(RulesSetError, match="extends 'other', the base here is"):
        merge_rules(files)


def test_an_extension_written_for_another_version_of_the_base_is_refused(tmp_path):
    files = [
        _doc(tmp_path, "base", False, {"title": dict(STRING_1)}, version="2.0.0"),
        _doc(tmp_path, "ext", True, {"title": dict(STRING_1)}),
    ]
    with pytest.raises(RulesSetError) as excinfo:
        merge_rules(files)
    assert "extends base 1.0.0, the base here is base 2.0.0" in str(excinfo.value)


def test_a_field_an_extension_introduces_is_described(tmp_path):
    """A field an extension introduces needs a description, a redeclared
    parent none."""
    with pytest.raises(RulesSetError) as excinfo:
        _merge(
            tmp_path,
            {"dataset": {"_cardinality": "0..n", "_type": "object", "title": STRING_1}},
            {
                "dataset": {
                    "_cardinality": "0..n",
                    "_type": "object",
                    "issued": {"_cardinality": "0..1", "_type": "date"},
                }
            },
        )
    assert str(excinfo.value).count("no _description") == 1
    assert "dmp.dataset[].issued: no _description, introduced by ext" in str(
        excinfo.value
    )


def test_a_code_type_carries_its_pattern_and_nothing_else_does():
    glider = RULES_DIR.parent / "projects" / "glider" / "1.0.0.yaml"
    fields = {
        f.dotted_path: f for f in model_for(load(PROJECTS, glider)["rules"]).walk()
    }
    assert fields["dmp.language"].pattern == r"^[a-z]{3}$"
    assert fields["dmp.title"].pattern is None
