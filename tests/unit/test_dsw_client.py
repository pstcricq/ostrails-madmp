"""Where the instance is and the account, read from the environment, and what a
call that never became a response raises."""

import json
import urllib.error
import urllib.request

import pytest

from madmp.dsw.client import DswClient, Instance, from_environment, login
from madmp.errors import DswError, PublishError

VALUES = {
    "DSW_API_URL": "http://dsw/wizard-api",
    "DSW_USER": "a@b.c",
    "DSW_PASSWORD": "pw",
}


@pytest.fixture
def no_env(monkeypatch):
    """Every name this module reads, unset."""
    for name in VALUES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_the_instance_is_read_from_the_environment(no_env):
    for name, value in VALUES.items():
        no_env.setenv(name, value)
    assert from_environment() == Instance("http://dsw/wizard-api", "a@b.c", "pw")


def test_every_missing_value_is_named_at_once(no_env):
    no_env.setenv("DSW_USER", "a@b.c")
    with pytest.raises(PublishError) as caught:
        from_environment()
    assert len(caught.value.problems) == 2
    assert "DSW_API_URL" in str(caught.value) and "DSW_PASSWORD" in str(caught.value)


def test_the_password_stays_out_of_repr():
    assert "pw" not in repr(Instance("http://dsw/wizard-api", "a@b.c", "pw"))


class _Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_a_login_gives_a_client_carrying_its_token(monkeypatch):
    sent = []

    def answer(request, timeout=None):
        sent.append((request.full_url, json.loads(request.data)))
        return _Response({"token": "a-token"})

    monkeypatch.setattr(urllib.request, "urlopen", answer)
    dsw = login(Instance("http://dsw/wizard-api/", "a@b.c", "pw"))
    assert (dsw.api_url, dsw.token) == ("http://dsw/wizard-api", "a-token")
    assert sent == [
        ("http://dsw/wizard-api/tokens", {"email": "a@b.c", "password": "pw"})
    ]


def test_an_instance_that_cannot_be_reached_is_a_dsw_error(monkeypatch):
    """Never a response, so no status."""

    def unreachable(request, timeout=None):
        raise urllib.error.URLError("nodename nor servname provided")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    with pytest.raises(DswError) as caught:
        DswClient("https://dsw.example/wizard-api", "token").get("/packages")
    assert caught.value.status is None
    assert str(caught.value).startswith("DSW unreachable: GET /packages")


def test_a_listing_is_read_page_after_page():
    class Pages(DswClient):
        def get(self, path):
            page = int(path.split("page=")[1]) if "page=" in path else 0
            return {"_embedded": {"items": [page]}, "page": {"totalPages": 3}}

    assert Pages("http://dsw", "t").list_all("/items", "items") == [0, 1, 2]


def test_a_download_follows_the_link_without_the_token(monkeypatch):
    """The link carries its own signature, which no message repeats."""
    fetched = []

    class Linked(DswClient):
        def get(self, path):
            return {"url": "http://s3:9000/bucket/file?X-Amz-Signature=secret"}

    def answer(request, timeout=None):
        fetched.append(request)
        raise urllib.error.HTTPError(request, 403, "Forbidden", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", answer)
    with pytest.raises(DswError) as caught:
        Linked("http://dsw/wizard-api", "a-token").download("/x/bundle")
    assert fetched == ["http://s3:9000/bucket/file?X-Amz-Signature=secret"]
    assert str(caught.value) == "DSW API error 403: GET http://s3:9000/bucket/file"
