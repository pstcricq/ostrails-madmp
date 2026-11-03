"""The rules files of the repository load, the schema then the coherence checks
reject what they check, every problem of a load is reported in one error, and a
file's path is checked against what it declares."""

import json

import pytest

from madmp.definitions import RULES, RulesFileError, load
from tests import ROOT
from tests.unit._described import described

RULES_DIR = ROOT / "definitions" / "rules"
REAL_FILES = ["rda_dcs/1.0.0.json", "ostrails/1.0.0.json"]


@pytest.mark.parametrize("filename", REAL_FILES)
def test_real_rules_file_loads(filename):
    doc = load(RULES, RULES_DIR / filename)
    assert isinstance(doc["standard"], str)
    assert "extends" not in doc or doc["extends"]["standard"] != doc["standard"]
    assert doc["dmp"]


def _write(tmp_path, doc):
    """Writes ``doc`` at <standard>/<version>.json, where it declares itself,
    or at unnamed/1.0.0.json for a doc missing the keys."""
    directory = str(doc.get("standard", "unnamed"))
    path = tmp_path / directory / f"{doc.get('version', '1.0.0')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(described(doc)))
    return path


def _minimal_doc(**dmp_fields):
    return {
        "standard": "test",
        "version": "1.0.0",
        "name": "Test standard",
        "references": [{"label": "Spec", "url": "https://example.org"}],
        "dmp": dmp_fields,
    }


def _load_problems(tmp_path, doc) -> str:
    with pytest.raises(RulesFileError) as excinfo:
        load(RULES, _write(tmp_path, doc))
    return str(excinfo.value)


def test_syntactically_broken_json_is_a_rules_file_error(tmp_path):
    path = tmp_path / "test" / "1.0.0.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"standard": "test", "dmp": {},}')
    with pytest.raises(RulesFileError, match="invalid JSON"):
        load(RULES, path)


def test_unreadable_path_is_a_rules_file_error(tmp_path):
    with pytest.raises(RulesFileError, match="cannot be read"):
        load(RULES, tmp_path / "absent" / "1.0.0.json")


def test_minimal_valid_doc_loads(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    assert load(RULES, _write(tmp_path, doc))["standard"] == "test"


def test_non_snake_case_standard_rejected(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    doc["standard"] = "RDA DCS"
    assert "standard" in _load_problems(tmp_path, doc)


def test_non_snake_case_field_name_rejected(tmp_path):
    doc = _minimal_doc(Title={"_cardinality": "1", "_type": "string"})
    assert "'Title'" in _load_problems(tmp_path, doc)


def test_missing_top_level_keys_rejected(tmp_path):
    problems = _load_problems(tmp_path, {"dmp": {}})
    assert "standard" in problems
    assert "version" in problems
    assert "name" in problems


def test_list_type_rejected(tmp_path):
    doc = _minimal_doc(dataset={"_cardinality": "1..n", "_type": "list"})
    assert "_type" in _load_problems(tmp_path, doc)


def test_empty_dmp_rejected(tmp_path):
    assert "dmp: {} should be non-empty" in _load_problems(tmp_path, _minimal_doc())


def test_duplicate_vocabulary_value_rejected(tmp_path):
    doc = _minimal_doc(
        mode={"_cardinality": "1", "_type": "string", "_allowed_values": ["rt", "rt"]}
    )
    assert "_allowed_values" in _load_problems(tmp_path, doc)


def test_empty_vocabulary_value_rejected(tmp_path):
    doc = _minimal_doc(
        mode={"_cardinality": "1", "_type": "string", "_suggested_values": [""]}
    )
    assert "_suggested_values" in _load_problems(tmp_path, doc)


def test_unknown_cardinality_rejected(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "2..n", "_type": "string"})
    assert "_cardinality" in _load_problems(tmp_path, doc)


def test_metadata_typo_rejected(tmp_path):
    doc = _minimal_doc(
        title={"_cardinality": "1", "_type": "string", "_descriptoin": "oops"}
    )
    assert "_descriptoin" in _load_problems(tmp_path, doc)


def test_missing_required_metadata_rejected(tmp_path):
    doc = _minimal_doc(title={"_type": "string"})
    assert "_cardinality" in _load_problems(tmp_path, doc)


def test_children_on_scalar_rejected(tmp_path):
    doc = _minimal_doc(
        title={
            "_cardinality": "1",
            "_type": "string",
            "identifier": {"_cardinality": "1", "_type": "string"},
        }
    )
    problems = _load_problems(tmp_path, doc)
    assert "dmp.title" in problems
    assert "only 'object' fields may have children" in problems


def test_childless_object_rejected(tmp_path):
    doc = _minimal_doc(cost={"_cardinality": "0..n", "_type": "object"})
    problems = _load_problems(tmp_path, doc)
    assert "dmp.cost" in problems
    assert "declares no child fields" in problems


def test_childless_object_rejected_deep_in_the_tree(tmp_path):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "1..n",
            "_type": "object",
            "distribution": {"_cardinality": "0..1", "_type": "object"},
        }
    )
    assert "dmp.dataset.distribution" in _load_problems(tmp_path, doc)


def test_vocabulary_on_object_rejected(tmp_path):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "1..n",
            "_type": "object",
            "_allowed_values": ["a"],
            "title": {"_cardinality": "1", "_type": "string"},
        }
    )
    assert "_allowed_values on an 'object' field" in _load_problems(tmp_path, doc)


def test_both_vocabularies_on_one_field_rejected(tmp_path):
    doc = _minimal_doc(
        language={
            "_cardinality": "1",
            "_type": "string",
            "_allowed_values": ["eng"],
            "_suggested_values": ["spa"],
        }
    )
    problems = _load_problems(tmp_path, doc)
    assert "dmp.language" in problems
    assert "either closed or recommended" in problems


def test_one_vocabulary_at_a_time_accepted(tmp_path):
    for vocab_key in ("_allowed_values", "_suggested_values"):
        doc = _minimal_doc(
            language={"_cardinality": "1", "_type": "string", vocab_key: ["eng"]}
        )
        assert load(RULES, _write(tmp_path, doc))["standard"] == "test"


def test_chapter_description_on_top_level_object_accepted(tmp_path):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "1..n",
            "_type": "object",
            "_chapter_description": "The datasets of this DMP.",
            "title": {"_cardinality": "1", "_type": "string"},
        }
    )
    assert load(RULES, _write(tmp_path, doc))["standard"] == "test"


def test_chapter_description_on_top_level_scalar_rejected(tmp_path):
    doc = _minimal_doc(
        title={
            "_cardinality": "1",
            "_type": "string",
            "_chapter_description": "Not a chapter.",
        }
    )
    problems = _load_problems(tmp_path, doc)
    assert "dmp.title" in problems
    assert "is not an object" in problems


def test_chapter_description_below_top_level_rejected(tmp_path):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "1..n",
            "_type": "object",
            "distribution": {
                "_cardinality": "0..n",
                "_type": "object",
                "_chapter_description": "A nested object is never a chapter.",
                "title": {"_cardinality": "1", "_type": "string"},
            },
        }
    )
    problems = _load_problems(tmp_path, doc)
    assert "dmp.dataset.distribution" in problems
    assert "not a top-level field" in problems


def test_all_problems_reported_at_once(tmp_path):
    doc = _minimal_doc(
        title={"_cardinality": "2..n", "_type": "string"},
        dataset={"_cardinality": "1..n", "_type": "list"},
    )
    problems = _load_problems(tmp_path, doc)
    assert "dataset" in problems
    assert "title" in problems


def test_coherence_waits_for_a_schema_valid_document(tmp_path):
    """A document wrong against the schema and the coherence checks reports
    the schema alone."""
    doc = _minimal_doc(
        title={
            "_cardinality": "2..n",
            "_type": "string",
            "child": {"_cardinality": "1", "_type": "string"},
        }
    )
    problems = _load_problems(tmp_path, doc)
    assert "_cardinality" in problems
    assert "only 'object' fields may have children" not in problems


def test_coherence_checked_deep_in_the_tree(tmp_path):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "1..n",
            "_type": "object",
            "distribution": {
                "_cardinality": "0..n",
                "_type": "object",
                "format": {
                    "_cardinality": "0..n",
                    "_type": "string",
                    "oops": {"_cardinality": "1", "_type": "string"},
                },
            },
        }
    )
    assert "dmp.dataset.distribution.format" in _load_problems(tmp_path, doc)


# Placement: a file must declare the standard and the version its path names


def _placed(tmp_path, directory, filename, standard, version):
    """One rules file at <directory>/<filename>.json, declaring whatever
    ``standard`` and ``version`` say, so it can be made to contradict its path."""
    path = tmp_path / directory / f"{filename}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            described(
                {
                    "standard": standard,
                    "version": version,
                    "extends": {"standard": "base", "versions": ["1.0.0"]},
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": {"title": {"_cardinality": "1", "_type": "string"}},
                }
            )
        )
    )
    return path


def test_a_correctly_placed_file_loads(tmp_path):
    path = _placed(tmp_path, "rda_dcs", "1.0.0", "rda_dcs", "1.0.0")
    assert load(RULES, path)["standard"] == "rda_dcs"


def test_a_file_declaring_another_standard_rejected(tmp_path):
    path = _placed(tmp_path, "ostrails", "9.9.9", "other", "9.9.9")
    with pytest.raises(RulesFileError) as excinfo:
        load(RULES, path)
    assert "'other'" in str(excinfo.value)
    assert "'ostrails'" in str(excinfo.value)


def test_a_file_declaring_another_version_rejected(tmp_path):
    path = _placed(tmp_path, "rda_dcs", "1.1.0", "rda_dcs", "1.0.0")
    with pytest.raises(RulesFileError) as excinfo:
        load(RULES, path)
    assert "'1.0.0'" in str(excinfo.value)
    assert "'1.1.0'" in str(excinfo.value)


def test_a_file_wrong_on_both_counts_reports_both(tmp_path):
    path = _placed(tmp_path, "ostrails", "9.9.9", "other", "1.0.0")
    with pytest.raises(RulesFileError) as excinfo:
        load(RULES, path)
    assert excinfo.value.problems == [
        (
            "declares standard 'other' but sits in directory 'ostrails', "
            "the two must agree."
        ),
        "declares version '1.0.0' but is named '9.9.9', the two must agree.",
    ]


def test_a_valid_file_elsewhere_than_its_path_says_is_refused(tmp_path):
    path = _placed(tmp_path, "somewhere", "scratch", "rda_dcs", "1.0.0")
    with pytest.raises(RulesFileError, match="must agree"):
        load(RULES, path)


def test_a_misplaced_and_incoherent_file_reports_both_layers(tmp_path):
    path = tmp_path / "ostrails" / "1.0.0.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            described(
                {
                    "standard": "other",
                    "version": "1.0.0",
                    "extends": {"standard": "base", "versions": ["1.0.0"]},
                    "name": "Test standard",
                    "references": [{"label": "Spec", "url": "https://example.org"}],
                    "dmp": {
                        "title": {
                            "_cardinality": "1",
                            "_type": "string",
                            "child": {"_cardinality": "1", "_type": "string"},
                        }
                    },
                }
            )
        )
    )
    with pytest.raises(RulesFileError) as excinfo:
        load(RULES, path)
    problems = str(excinfo.value)
    assert "only 'object' fields may have children" in problems
    assert "sits in directory 'ostrails'" in problems


# How a standard names itself


@pytest.mark.parametrize("key", ["name", "references"])
def test_a_standard_names_itself_and_says_where_it_is_documented(tmp_path, key):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    del doc[key]
    assert key in _load_problems(tmp_path, doc)


def test_a_standard_has_at_least_one_reference(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    doc["references"] = []
    assert "references" in _load_problems(tmp_path, doc)


def test_a_reference_is_a_label_and_a_web_address(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    doc["references"] = [{"label": "Spec", "url": "doi:10.1/x"}]
    assert "url" in _load_problems(tmp_path, doc)


# What an extension extends


def test_the_base_has_no_extends(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    assert "extends" not in load(RULES, _write(tmp_path, doc))


def test_an_extension_does_not_extend_itself(tmp_path):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    doc["extends"] = {"standard": "test", "versions": ["1.0.0"]}
    assert "its own standard" in _load_problems(tmp_path, doc)


@pytest.mark.parametrize(
    "extends",
    [
        True,
        {"standard": "base"},
        {"standard": "base", "versions": []},
        {"standard": "base", "versions": ["1.0.0", "1.0.0"]},
        {"standard": "base", "versions": ["1.0.0"], "other": 1},
    ],
)
def test_extends_names_a_standard_and_its_versions(tmp_path, extends):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    doc["extends"] = extends
    assert "extends" in _load_problems(tmp_path, doc)


# What a researcher reads


def test_every_field_of_the_base_is_described(tmp_path):
    doc = _minimal_doc(
        title={"_cardinality": "1", "_type": "string", "_description": "Asked."},
        contact={
            "_cardinality": "1",
            "_type": "object",
            "_description": "Asked.",
            "mbox": {"_cardinality": "1", "_type": "email"},
        },
    )
    path = tmp_path / "test" / "1.0.0.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(doc))
    with pytest.raises(RulesFileError) as excinfo:
        load(RULES, path)
    assert "dmp.contact.mbox: no _description" in str(excinfo.value)
    assert "dmp.title" not in str(excinfo.value)


def test_an_extension_may_redeclare_a_parent_without_a_description(tmp_path):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "0..n",
            "_type": "object",
            "issued": {"_cardinality": "1", "_type": "date", "_description": "New."},
        }
    )
    doc["extends"] = {"standard": "base", "versions": ["1.0.0"]}
    assert load(RULES, _write(tmp_path, doc))["extends"]["standard"] == "base"


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "latest"])
def test_a_rules_version_is_x_y_z(tmp_path, version):
    doc = _minimal_doc(title={"_cardinality": "1", "_type": "string"})
    doc["version"] = version
    assert "version" in _load_problems(tmp_path, doc)


@pytest.mark.parametrize("key", ["_description", "_chapter_description"])
@pytest.mark.parametrize("text", ["", "   "])
def test_a_description_is_never_blank(tmp_path, key, text):
    doc = _minimal_doc(
        dataset={
            "_cardinality": "1",
            "_type": "object",
            key: text,
            "title": {"_cardinality": "1", "_type": "string", "_description": "x"},
        }
    )
    assert key in _load_problems(tmp_path, doc)
