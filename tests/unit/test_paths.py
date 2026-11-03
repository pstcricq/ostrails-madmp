"""The definitions are in ``definitions/`` at the root of the repository."""

from madmp import paths
from tests import ROOT


def test_the_definitions_are_at_the_root_of_the_repository():
    assert paths.DEFINITIONS_DIR == ROOT / "definitions"
    assert paths.RULES_DIR == ROOT / "definitions" / "rules"
    assert paths.RULES_DIR.is_dir()
    assert paths.RULES_SCHEMA.is_file()
