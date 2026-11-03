"""Pins to a model: ``model_for()`` resolves the pins to their rules files,
then merges them."""

from __future__ import annotations

from pathlib import Path

from madmp.model.merge import Model, merge_rules
from madmp.model.pins import Pin, resolve_pins
from madmp.paths import RULES_DIR


def model_for(pins: list[Pin], rules_dir: str | Path = RULES_DIR) -> Model:
    """The model the rules files ``pins`` names merge into, from
    ``rules_dir``, this repository's tree by default.

    Raises whatever its steps raise, unchanged, each naming its own kind of
    problem: ``UnresolvedPinsError``, ``RulesFileError``, ``RulesSetError`` or
    ``RulesConflictError``.
    """
    return merge_rules(resolve_pins(pins, rules_dir))
