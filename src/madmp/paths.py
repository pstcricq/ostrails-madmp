"""Where the definitions this package reads live: ``definitions/`` at the root
of the repository, two levels above ``src/madmp/``.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFINITIONS_DIR = ROOT / "definitions"
RULES_DIR = DEFINITIONS_DIR / "rules"
RULES_SCHEMA = RULES_DIR / "rules.schema.json"
