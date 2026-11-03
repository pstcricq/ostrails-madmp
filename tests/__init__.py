"""The tests: unit/ needs nothing but the repository, fixtures/ holds the
DMP documents they read."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
