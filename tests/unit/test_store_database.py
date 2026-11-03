"""Where the DMP database is, named by the environment."""

import pytest

from madmp.errors import StoreError
from madmp.store import Database

DATABASE_ENVIRONMENT = {
    "DMP_HOST": "postgres",
    "DMP_PORT": "5432",
    "DMP_DB": "dmp",
    "DMP_USER": "dmp_app",
    "DMP_PASSWORD": "secret",
}


def test_the_database_is_named_by_the_environment(monkeypatch):
    for name, value in DATABASE_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    assert Database.from_environment() == Database(
        "postgres", 5432, "dmp", "dmp_app", "secret"
    )


def test_the_port_is_a_number(monkeypatch):
    for name, value in DATABASE_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DMP_PORT", "x")
    with pytest.raises(StoreError, match="not a port number"):
        Database.from_environment()


def test_every_unset_variable_is_named_at_once(monkeypatch):
    """Empty counts as unset."""
    for name in DATABASE_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DMP_DB", "")
    with pytest.raises(StoreError) as caught:
        Database.from_environment()
    assert str(caught.value) == (
        "not set: DMP_HOST, DMP_PORT, DMP_DB, DMP_USER, DMP_PASSWORD"
    )


def test_the_password_stays_out_of_repr():
    assert "secret" not in repr(Database("postgres", 5432, "dmp", "dmp_app", "secret"))
