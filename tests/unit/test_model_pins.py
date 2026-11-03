"""Pins resolved against the rules of the repository, and every way a pin can
name something that is not there, each message naming what does exist."""

import pytest
import yaml

from madmp.model import UnresolvedPinsError, pin_problems, resolve_pins
from tests import ROOT

RULES_DIR = ROOT / "definitions" / "rules"
GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"


# What a real project declares


def test_the_real_config_resolves():
    definition = yaml.safe_load(GLIDER_PROJECT.read_text())
    rules = resolve_pins(definition["rules"], RULES_DIR)
    assert [p.relative_to(ROOT).as_posix() for p in rules] == [
        "definitions/rules/rda_dcs/1.0.0.json",
        "definitions/rules/ostrails/1.0.0.json",
    ]


def test_pin_order_is_kept():
    pins = [{"ostrails": "1.0.0"}, {"rda_dcs": "1.0.0"}]
    assert [p.parent.name for p in resolve_pins(pins, RULES_DIR)] == [
        "ostrails",
        "rda_dcs",
    ]


def test_no_pins_is_refused():
    assert "not a non-empty list" in _problems(lambda: resolve_pins([], RULES_DIR))


# What a broken project says


def _problems(call) -> str:
    with pytest.raises(UnresolvedPinsError) as excinfo:
        call()
    return str(excinfo.value)


def test_unknown_standard_lists_the_ones_that_exist():
    problems = _problems(lambda: resolve_pins([{"rda_dc": "1.0.0"}], RULES_DIR))
    assert "unknown standard 'rda_dc'" in problems
    assert "ostrails, rda_dcs" in problems


def test_unknown_version_lists_the_ones_that_exist():
    problems = _problems(lambda: resolve_pins([{"ostrails": "2.0.0"}], RULES_DIR))
    assert "unknown version '2.0.0'" in problems
    assert "it has 1.0.0" in problems


def test_only_directories_holding_a_versioned_file_are_offered(tmp_path):
    """A directory with no rules file in it is not a standard."""
    (tmp_path / "ostrails" / "nested").mkdir(parents=True)
    (tmp_path / "ostrails" / "1.0.0.json").write_text("{}")
    (tmp_path / "junk").mkdir()
    problems = _problems(lambda: resolve_pins([{"nope": "1.0.0"}], tmp_path))
    assert "has ostrails." in problems


def test_every_unresolved_pin_reported_at_once():
    problems = _problems(
        lambda: resolve_pins(
            [{"rda_dcs": "1.0.0"}, {"nope": "1.0.0"}, {"ostrails": "9.9.9"}], RULES_DIR
        )
    )
    assert "3 unresolved pin(s)" not in problems
    assert "2 unresolved pin(s)" in problems
    assert "unknown standard 'nope'" in problems
    assert "unknown version '9.9.9'" in problems


@pytest.mark.parametrize(
    "pin",
    [
        {"ostrails": "../ostrails/1.0.0"},
        {"ostrails": ".."},
        {"ostrails": ""},
        {"../definitions/rules/ostrails": "1.0.0"},
    ],
)
def test_a_pin_part_may_not_be_a_path(pin):
    """Neither half's shape lets a separator through: the pin is refused
    before any path is built."""
    problems = _problems(lambda: resolve_pins([pin], RULES_DIR))
    assert "pin 1," in problems
    assert "unknown" not in problems


def test_an_empty_resource_tree_says_nothing_rather_than_an_empty_list(tmp_path):
    problems = _problems(lambda: resolve_pins([{"ostrails": "1.0.0"}], tmp_path))
    assert "has nothing" in problems


def test_a_resource_tree_that_does_not_exist_says_so(tmp_path):
    problems = _problems(
        lambda: resolve_pins([{"ostrails": "1.0.0"}], tmp_path / "gone")
    )
    assert "no such directory" in problems


def test_a_standard_with_no_versions_says_nothing(tmp_path):
    (tmp_path / "ostrails").mkdir()
    problems = _problems(lambda: resolve_pins([{"ostrails": "1.0.0"}], tmp_path))
    assert "it has nothing" in problems


# The shape of the pins, wherever they come from


@pytest.mark.parametrize(
    "pins, expected",
    [
        (None, "not a non-empty list"),
        ([], "not a non-empty list"),
        ({"rda_dcs": "1.0.0"}, "not a non-empty list"),
        ([{"rda_dcs": "1.0.0", "ostrails": "1.0.0"}], "not one {standard: version}"),
        (["rda_dcs"], "not one {standard: version}"),
        ([{"RDA": "1.0.0"}], "not a standard's identifier"),
        ([{"rda_dcs": 1.0}], "is not a version X.Y.Z, quoted"),
        ([{"rda_dcs": "1.0"}], "is not a version X.Y.Z, quoted"),
    ],
)
def test_a_malformed_pin_is_named(pins, expected):
    assert any(expected in problem for problem in pin_problems(pins))
    assert expected in _problems(lambda: resolve_pins(pins, RULES_DIR))


def test_well_formed_pins_have_no_problem():
    assert pin_problems([{"rda_dcs": "1.0.0"}, {"ostrails": "1.0.0"}]) == []


def test_every_malformed_pin_is_reported_at_once():
    problems = pin_problems([{"RDA": "1.0"}, "x"])
    assert len(problems) == 3
