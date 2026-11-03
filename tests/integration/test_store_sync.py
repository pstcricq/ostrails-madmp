"""The definitions synced into the DMP database: what is missing added, what
is there left, a changed version refused.
"""

import pytest
import yaml

from madmp.errors import StoreError
from madmp.paths import PROJECTS_DIR, RULES_DIR
from madmp.store import sync

GLIDER_PINS = [("rda_dcs", "1.0.0"), ("ostrails", "1.0.0")]


def _pins(conn, project, version):
    rows = conn.execute(
        "SELECT standard, rules_version FROM project_rules "
        "WHERE project_id = %s AND version = %s ORDER BY position",
        (project, version),
    )
    return rows.fetchall()


def glider_at(conn, tmp_path, version, rules=None, reorder=False):
    """glider at another version synced alone, as a new YAML would be."""
    projects = tmp_path / "projects"
    (projects / "glider").mkdir(parents=True, exist_ok=True)
    definition = yaml.safe_load((PROJECTS_DIR / "glider" / "1.0.0.yaml").read_text())
    definition["version"] = version
    if rules is not None:
        definition["rules"] = rules
    if reorder:
        definition = dict(reversed(definition.items()))
    text = yaml.safe_dump(definition, sort_keys=False)
    (projects / "glider" / f"{version}.yaml").write_text(text)
    return sync(conn, RULES_DIR, projects)


def test_the_repository_s_definitions_are_synced(conn):
    """Synced before each test: every rules file, every project at its
    version, and its pins in order, the base first."""
    rules = conn.execute("SELECT standard, version FROM rules ORDER BY 1").fetchall()
    assert rules == [("ostrails", "1.0.0"), ("rda_dcs", "1.0.0")]
    projects = conn.execute("SELECT project_id, version FROM project_versions")
    assert projects.fetchall() == [("glider", "1.0.0")]
    assert _pins(conn, "glider", "1.0.0") == GLIDER_PINS


def test_syncing_again_adds_nothing(conn):
    assert sync(conn) == []


def test_the_same_content_written_otherwise_is_the_same_version(conn, tmp_path):
    """Compared by content: the order of the keys does not count."""
    assert glider_at(conn, tmp_path, "1.0.0", reorder=True) == []


def test_a_new_project_version_is_added_beside_the_first(conn, tmp_path):
    assert glider_at(conn, tmp_path, "1.1.0") == ["projects glider 1.1.0"]
    assert _pins(conn, "glider", "1.1.0") == GLIDER_PINS
    assert _pins(conn, "glider", "1.0.0") == GLIDER_PINS


def test_a_version_synced_with_another_content_is_refused(conn, tmp_path):
    """Nothing of the sync is written."""
    with pytest.raises(StoreError, match="projects glider 1.0.0"):
        glider_at(conn, tmp_path, "1.0.0", rules=[{"rda_dcs": "1.0.0"}])
    assert _pins(conn, "glider", "1.0.0") == GLIDER_PINS


def test_pins_naming_no_rules_file_are_refused(conn, tmp_path):
    with pytest.raises(StoreError, match="pins ostrails 9.9.9"):
        glider_at(
            conn, tmp_path, "3.0.0", rules=[{"rda_dcs": "1.0.0"}, {"ostrails": "9.9.9"}]
        )
    assert _pins(conn, "glider", "3.0.0") == []


def test_a_file_gone_from_git_stays_in_the_database(conn, tmp_path):
    """Nothing is ever removed."""
    (tmp_path / "projects").mkdir()
    assert sync(conn, RULES_DIR, tmp_path / "projects") == []
    assert _pins(conn, "glider", "1.0.0") == GLIDER_PINS
