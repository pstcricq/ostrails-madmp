"""model_for: the pins of a project of the repository come back as the model
of the versions they name, and pins that do not all resolve come back as no
model at all."""

import pytest

from madmp.definitions import PROJECTS, load
from madmp.errors import RulesSetError
from madmp.model import UnresolvedPinsError, model_for
from tests import ROOT

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"
GLIDER_PINS = load(PROJECTS, GLIDER_PROJECT)["rules"]


# What real pins come back as


def test_the_real_pins_merge():
    assert model_for(GLIDER_PINS).standards == ("rda_dcs", "ostrails")


def test_the_model_carries_the_versions_the_pins_name():
    """The versions the pins named, in the order they named them."""
    pinned = [version for pin in GLIDER_PINS for version in pin.values()]
    assert [version for _, version in model_for(GLIDER_PINS).standard_versions] == (
        pinned
    )


# All of it, or none of it


def test_a_missing_rules_version_stops_the_merge():
    with pytest.raises(UnresolvedPinsError, match="unknown version '9.9.9'"):
        model_for([{"rda_dcs": "1.0.0"}, {"ostrails": "9.9.9"}])


def test_each_step_keeps_its_own_error():
    """An extension alone has no base: the merge's own error."""
    with pytest.raises(RulesSetError):
        model_for([{"ostrails": "1.0.0"}])


def test_the_rules_root_is_a_parameter(tmp_path):
    with pytest.raises(UnresolvedPinsError, match="no such directory"):
        model_for(GLIDER_PINS, rules_dir=tmp_path / "gone")
