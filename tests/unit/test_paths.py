"""The definitions are in ``definitions/`` at the root of the repository."""

from madmp import paths
from tests import ROOT


def test_the_definitions_are_at_the_root_of_the_repository():
    assert paths.DEFINITIONS_DIR == ROOT / "definitions"
    assert paths.RULES_DIR == ROOT / "definitions" / "rules"
    assert paths.PROJECTS_DIR == ROOT / "definitions" / "projects"
    for directory in (paths.RULES_DIR, paths.PROJECTS_DIR):
        assert directory.is_dir()
    for schema in (paths.RULES_SCHEMA, paths.PROJECT_SCHEMA):
        assert schema.is_file()
