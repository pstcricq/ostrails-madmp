"""The administrator made sure of, against an instance written for the tests."""

import pytest

from madmp.dsw import admin
from madmp.dsw.admin import DEMO_ACCOUNTS, DEMO_ADMIN, DEMO_PASSWORD
from madmp.dsw.client import DswClient, Instance
from madmp.errors import DswError, PublishError

API = "http://dsw/wizard-api"
ADMIN = Instance(API, "madmp-admin@example.com", "s3cret")


class _Dsw:
    """An instance's accounts, ``email -> password``, and what was done."""

    def __init__(self, accounts):
        self.accounts = dict(accounts)
        self.created, self.deleted = [], []

    def login(self, instance):
        if self.accounts.get(instance.user) != instance.password:
            raise DswError(400, "POST /tokens: refused")
        return _Client(self)


class _Client(DswClient):
    def __init__(self, dsw):
        super().__init__(API, "a-token")
        self.dsw = dsw

    def post(self, path, payload):
        assert path == "/users" and payload["role"] == "admin"
        self.dsw.accounts[payload["email"]] = payload["password"]
        self.dsw.created.append(payload["email"])

    def list_all(self, endpoint, collection):
        return [{"email": email, "uuid": email} for email in self.dsw.accounts]

    def delete(self, path):
        email = path.removeprefix("/users/")
        self.dsw.deleted.append(email)
        del self.dsw.accounts[email]


@pytest.fixture
def dsw(monkeypatch):
    def made(accounts):
        instance = _Dsw(accounts)
        monkeypatch.setattr(admin, "login", instance.login)
        return instance

    return made


NEW = {email: DEMO_PASSWORD for email in DEMO_ACCOUNTS}


def test_a_new_instance_gets_its_administrator_and_loses_its_demos(dsw):
    instance = dsw(NEW)
    lines = admin.admin(ADMIN)
    assert instance.created == [ADMIN.user]
    assert sorted(instance.deleted) == sorted(DEMO_ACCOUNTS)
    assert lines[0] == f"Administrator {ADMIN.user} created."
    assert lines[1].startswith("Demo accounts deleted:")


def test_an_administrator_that_logs_in_is_left_as_it_is(dsw):
    instance = dsw({ADMIN.user: ADMIN.password})
    assert admin.admin(ADMIN) == [f"Administrator {ADMIN.user} logs in."]
    assert instance.created == [] and instance.deleted == []


def test_a_demo_account_whose_password_changed_is_left(dsw):
    instance = dsw({ADMIN.user: ADMIN.password, DEMO_ADMIN: "changed"})
    admin.admin(ADMIN)
    assert instance.deleted == []


def test_no_administrator_and_no_demo_left_is_refused(dsw):
    dsw({DEMO_ADMIN: "changed"})
    with pytest.raises(PublishError) as caught:
        admin.admin(ADMIN)
    assert "create it by hand" in str(caught.value)


def test_the_account_published_as_is_never_deleted(dsw):
    """DSW_USER may be one of the demo accounts: it is kept."""
    instance = dsw(NEW)
    admin.admin(Instance(API, DEMO_ADMIN, DEMO_PASSWORD))
    assert DEMO_ADMIN not in instance.deleted
    assert sorted(instance.deleted) == sorted(set(DEMO_ACCOUNTS) - {DEMO_ADMIN})
