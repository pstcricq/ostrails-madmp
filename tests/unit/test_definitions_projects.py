"""Every project version of the repository loads, and what the schema and the
path refuse, every problem of a load in one error.
"""

import pytest
import yaml

from madmp.definitions import PROJECTS, ProjectFileError, files, load
from tests import ROOT

PROJECTS_DIR = ROOT / "definitions" / "projects"
REAL_CONFIGS = files(PROJECTS)


@pytest.mark.parametrize(
    "path", REAL_CONFIGS, ids=lambda p: f"{p.parent.name}/{p.stem}"
)
def test_real_config_loads(path):
    definition = load(PROJECTS, path)
    assert definition["id"]
    assert definition["rules"]


def test_at_least_one_real_config_exists():
    assert REAL_CONFIGS


def _valid_config(**overrides):
    definition = {
        "id": "test-project",
        "organizationId": "example",
        "name": "Test Project",
        "version": "1.0.0",
        "author": "Someone",
        "license": "CC BY 4.0",
        "rules": [{"rda_dcs": "1.0.0"}],
    }
    definition.update(overrides)
    return definition


def _write(tmp_path, definition, directory=None, filename=None):
    """Writes ``definition`` at <id>/<version>.yaml, where it declares itself,
    or at <directory>/<filename>.yaml when given."""
    folder = directory if directory is not None else definition.get("id", "x")
    stem = filename if filename is not None else definition.get("version", "x")
    path = tmp_path / folder / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(definition))
    return path


def _load_problems(tmp_path, definition, directory=None, filename=None) -> str:
    with pytest.raises(ProjectFileError) as excinfo:
        load(PROJECTS, _write(tmp_path, definition, directory, filename))
    return str(excinfo.value)


def test_valid_config_loads(tmp_path):
    assert load(PROJECTS, _write(tmp_path, _valid_config()))["id"] == "test-project"


def test_syntactically_broken_yaml_is_a_config_file_error(tmp_path):
    path = tmp_path / "test-project.yaml"
    path.write_text("id: [oops\nname: Test\n")
    with pytest.raises(ProjectFileError, match="invalid YAML"):
        load(PROJECTS, path)


def test_unreadable_path_is_a_config_file_error(tmp_path):
    with pytest.raises(ProjectFileError, match="cannot be read"):
        load(PROJECTS, tmp_path / "absent.yaml")


def test_empty_file_rejected(tmp_path):
    path = tmp_path / "test-project.yaml"
    path.write_text("")
    with pytest.raises(ProjectFileError, match=r"\(root\)"):
        load(PROJECTS, path)


def test_missing_required_field_rejected(tmp_path):
    definition = _valid_config()
    del definition["rules"]
    assert "rules" in _load_problems(tmp_path, definition)


@pytest.mark.parametrize("key", ["description", "references", "extra"])
def test_unknown_field_rejected(tmp_path, key):
    assert key in _load_problems(tmp_path, _valid_config(**{key: "x"}))


def test_wrong_type_rejected(tmp_path):
    assert "string" in _load_problems(tmp_path, _valid_config(name=3))


def test_empty_rules_rejected(tmp_path):
    assert "rules" in _load_problems(tmp_path, _valid_config(rules=[]))


def test_bare_standard_name_rejected(tmp_path):
    assert "rules" in _load_problems(tmp_path, _valid_config(rules=["rda_dcs"]))


def test_pinned_standard_not_snake_case_rejected(tmp_path):
    problems = _load_problems(tmp_path, _valid_config(rules=[{"RDA DCS": "1.0.0"}]))
    assert "rules.0" in problems
    assert "RDA DCS" in problems


def test_empty_pinned_version_rejected(tmp_path):
    problems = _load_problems(tmp_path, _valid_config(rules=[{"rda_dcs": ""}]))
    assert "rules.0.rda_dcs" in problems


def test_several_extensions_accepted(tmp_path):
    """The pins keep the order they were written in."""
    pins = [{"rda_dcs": "1.0.0"}, {"ostrails": "1.0.0"}, {"other": "2.0.0"}]
    loaded = load(PROJECTS, _write(tmp_path, _valid_config(rules=pins)))
    assert loaded["rules"] == pins


def test_id_pattern_rejected(tmp_path):
    assert "id" in _load_problems(tmp_path, _valid_config(id="Test Project"))


def test_empty_human_name_rejected(tmp_path):
    assert "name" in _load_problems(tmp_path, _valid_config(name=""))


@pytest.mark.parametrize("version", ["1.0", "v1.0.2", "1.0.2-beta", "latest"])
def test_non_semver_version_rejected(tmp_path, version):
    assert "version" in _load_problems(tmp_path, _valid_config(version=version))


def test_organization_id_outside_its_character_set_rejected(tmp_path):
    problems = _load_problems(tmp_path, _valid_config(organizationId="Example Org"))
    assert "organizationId" in problems


def test_dotted_organization_id_accepted(tmp_path):
    definition = _valid_config(organizationId="org.example")
    assert (
        load(PROJECTS, _write(tmp_path, definition))["organizationId"] == "org.example"
    )


def test_directory_disagreeing_with_id_rejected(tmp_path):
    problems = _load_problems(tmp_path, _valid_config(), directory="elsewhere")
    assert "id 'test-project'" in problems
    assert "'elsewhere'" in problems


def test_filename_disagreeing_with_version_rejected(tmp_path):
    problems = _load_problems(tmp_path, _valid_config(), filename="1.1.0")
    assert "version '1.0.0'" in problems
    assert "'1.1.0'" in problems


def test_versions_are_listed_oldest_first(tmp_path):
    """By number, not by text: 1.10.0 comes after 1.9.0."""
    for version in ("1.10.0", "1.9.0", "1.0.0"):
        _write(tmp_path, _valid_config(version=version))
    _write(tmp_path, _valid_config(id="another"))
    listed = [f"{p.parent.name}/{p.stem}" for p in files(PROJECTS, tmp_path)]
    assert listed == [
        "another/1.0.0",
        "test-project/1.0.0",
        "test-project/1.9.0",
        "test-project/1.10.0",
    ]


def test_every_problem_reported_at_once(tmp_path):
    definition = _valid_config(name=3, id="Test Project")
    del definition["license"]
    problems = _load_problems(tmp_path, definition)
    assert "license" in problems
    assert "string" in problems
    assert "id" in problems


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0-rc1", ""])
def test_a_pin_names_a_version_x_y_z(tmp_path, version):
    problems = _load_problems(tmp_path, _valid_config(rules=[{"rda_dcs": version}]))
    assert "rules" in problems


@pytest.mark.parametrize(
    "organization", ["example.", ".example", "exa..mple", "EXAMPLE"]
)
def test_an_organization_is_parts_joined_by_single_dots(tmp_path, organization):
    problems = _load_problems(tmp_path, _valid_config(organizationId=organization))
    assert "organizationId" in problems
