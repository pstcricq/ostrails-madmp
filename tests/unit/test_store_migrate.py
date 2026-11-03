"""The migrations the package carries."""

from madmp.store.migrate import migrations


def test_the_package_carries_its_migrations():
    assert next(name for _, name, _ in migrations()) == "001_init.sql"
