"""The DMP API through TestClient, on the PostgreSQL of the tests: the
fixtures with the metadata of glider 1.0.0, and the documents each template
renders.
"""

import copy
import json
import re
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import jinja2
import pytest
from fastapi.testclient import TestClient

from madmp.api.app import MAX_BODY, Settings, app, check_schema
from madmp.definitions import PROJECTS, files, load
from madmp.model import model_for
from madmp.packages.build import build
from madmp.store import template_key, write_template
from tests import FIXTURES
from tests.integration.test_store_sync import glider_at

METADATA = {
    "project": "glider",
    "project_version": "1.0.0",
    "rules": [{"rda_dcs": "1.0.0"}, {"ostrails": "1.0.0"}],
}
TEMPLATE = "socib-glider-template"
PRODUCTION = "socib-glider-0001"
TOKENS = {"template": "t-secret", "read": "r-secret", "write": "w-secret"}


def _document(**dmp) -> dict:
    """The RDA DCS + OSTrails fixture, with the metadata of glider 1.0.0."""
    example = json.loads((FIXTURES / "rda_dcs-ostrails.json").read_text())
    return {"dmp": {**example["dmp"], **dmp}, "metadata": copy.deepcopy(METADATA)}


@contextmanager
def served(settings: Settings, prepare: Callable[[Settings], None]):
    """The API serving ``settings``, ``prepare`` run at startup, then
    ``app.state`` as it was."""
    build_was, prepare_was = app.state.build, app.state.prepare
    app.state.build, app.state.prepare = (lambda: settings), prepare
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.state.build, app.state.prepare = build_was, prepare_was


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKENS[token]}"}


@pytest.fixture
def client(database):
    """The API, served on the test database, its schema checked at startup."""
    settings = Settings(TOKENS["template"], TOKENS["read"], TOKENS["write"], database)
    with served(settings, check_schema) as client:
        yield client


def _template(client, **dmp):
    return client.post("/templates", json=_document(**dmp), headers=_auth("template"))


def _production(client, template_version=1, **dmp):
    body = {"from_template_version": template_version, **_document(**dmp)}
    return client.post("/productions", json=body, headers=_auth("write"))


def _production_version(client, based_on, key=PRODUCTION, **dmp):
    body = {"based_on": based_on, "from_template_version": 1, **_document(**dmp)}
    return client.post(
        f"/productions/{key}/versions", json=body, headers=_auth("write")
    )


# Startup


def test_a_database_behind_on_its_migrations_is_refused(conn, database):
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    settings = Settings("t", "r", "w", database)
    with (
        pytest.raises(RuntimeError, match="lacks 001_init.sql"),
        served(settings, check_schema),
    ):
        pass


def test_health_answers_once_started(client):
    assert client.get("/health").json() == {"status": "ok"}


# The template


def test_a_first_template_is_created(client):
    answer = _template(client)
    assert answer.status_code == 201
    body = answer.json()
    assert (body["key"], body["version"], body["action"]) == (TEMPLATE, 1, "created")
    assert body["message"].startswith(f"Stored as {TEMPLATE} version 1.")
    assert body["assessment"]["verdict"] == "pass"


def test_the_same_template_again_adds_nothing(client):
    _template(client)
    answer = _template(client)
    assert answer.status_code == 200
    assert answer.json()["action"] == "unchanged"


def test_a_changed_template_is_the_next_version(client):
    _template(client)
    answer = _template(client, title="renamed")
    assert (answer.status_code, answer.json()["version"]) == (201, 2)


@pytest.mark.parametrize("token", [None, "write", "read"])
def test_a_template_takes_the_template_token_alone(client, token):
    headers = {} if token is None else _auth(token)
    assert (
        client.post("/templates", json=_document(), headers=headers).status_code == 401
    )


def test_a_body_that_is_not_json_is_refused(client):
    answer = client.post("/templates", content=b"{", headers=_auth("template"))
    assert (answer.status_code, answer.text) == (400, "body is not valid JSON")


def test_a_body_too_large_is_refused(client):
    answer = client.post(
        "/templates", content=b" " * (MAX_BODY + 1), headers=_auth("template")
    )
    assert answer.status_code == 413


def test_a_document_that_does_not_hold_up_is_refused_in_plain_text(client):
    answer = client.post(
        "/templates", json={"dmp": {}, "metadata": METADATA}, headers=_auth("template")
    )
    assert answer.status_code == 422
    assert answer.headers["content-type"].startswith("text/plain")
    assert answer.text.startswith("Assessment failed")


def test_rules_other_than_the_project_version_s_are_refused(client):
    """The RDA DCS example holds up against the RDA DCS alone, but glider
    1.0.0 pins the OSTrails profile too."""
    example = json.loads((FIXTURES / "rda_dcs.json").read_text())
    document = {
        "dmp": example["dmp"],
        "metadata": {**METADATA, "rules": [{"rda_dcs": "1.0.0"}]},
    }
    answer = client.post("/templates", json=document, headers=_auth("template"))
    assert answer.status_code == 400
    assert "not produced from that version" in answer.text


def test_a_project_version_never_synced_is_refused(client, conn):
    conn.execute("DELETE FROM project_rules")
    conn.execute("DELETE FROM project_versions")
    answer = _template(client)
    assert (answer.status_code, "never synced" in answer.text) == (422, True)


# Production DMPs


def test_a_production_is_created_from_a_template_version(client):
    _template(client)
    answer = _production(client)
    assert answer.status_code == 201
    assert (answer.json()["key"], answer.json()["version"]) == (PRODUCTION, 1)


def test_a_production_needs_a_template_version_number(client):
    body = {"from_template_version": "1", **_document()}
    answer = client.post("/productions", json=body, headers=_auth("write"))
    assert (answer.status_code, "not a version number" in answer.text) == (400, True)


def test_a_production_needs_a_stored_template_version(client):
    answer = _production(client)
    assert (answer.status_code, "has no version 1" in answer.text) == (422, True)


def test_a_production_s_metadata_is_its_template_version_s(client, conn, tmp_path):
    """Template version 2 was produced from glider 1.1.0, a document saying
    1.0.0 was not filled from it."""
    _template(client)
    glider_at(conn, tmp_path, "1.1.0")
    write_template(
        conn,
        project="glider",
        project_version="1.1.0",
        document={"title": "next"},
        assessment={"verdict": "pass"},
        source="templates",
    )
    answer = _production(client, template_version=2)
    assert answer.status_code == 400
    assert "was produced from 1.1.0" in answer.text


@pytest.mark.parametrize("token", [None, "template", "read"])
def test_a_production_takes_the_write_token(client, token):
    _template(client)
    headers = {} if token is None else _auth(token)
    body = {"from_template_version": 1, **_document()}
    assert client.post("/productions", json=body, headers=headers).status_code == 401


def test_a_production_version_based_on_the_latest_is_the_next_one(client):
    _template(client)
    _production(client)
    answer = _production_version(client, based_on=1, title="changed")
    assert (answer.status_code, answer.json()["version"]) == (201, 2)


def test_the_same_production_content_adds_nothing(client):
    _template(client)
    _production(client)
    answer = _production_version(client, based_on=1)
    assert (answer.status_code, answer.json()["action"]) == (200, "unchanged")


def test_a_production_version_based_on_a_stale_one_is_a_conflict(client):
    _template(client)
    _production(client)
    _production_version(client, based_on=1, title="first")
    answer = _production_version(client, based_on=1, title="second")
    assert (answer.status_code, "based on version 1" in answer.text) == (409, True)


@pytest.mark.parametrize("key", [TEMPLATE, "socib-glider-9999", "Not_A_Key"])
def test_a_production_version_goes_to_a_production(client, key):
    _template(client)
    assert _production_version(client, based_on=1, key=key).status_code == 404


# Reading


@pytest.mark.parametrize("token", ["read", "write"])
def test_a_dmp_is_read_with_the_read_or_the_write_token(client, token):
    _template(client)
    answer = client.get(f"/dmps/{TEMPLATE}", headers=_auth(token))
    assert answer.status_code == 200
    body = answer.json()
    assert body["metadata"] == METADATA
    assert body["dmp"]["dmp_id"] == {"identifier": TEMPLATE, "type": "other"}
    assert (body["source"], body["assessment"]["verdict"]) == ("templates", "pass")


@pytest.mark.parametrize("token", [None, "template"])
def test_reading_takes_a_read_or_write_token(client, token):
    _template(client)
    headers = {} if token is None else _auth(token)
    assert client.get(f"/dmps/{TEMPLATE}", headers=headers).status_code == 401


def test_the_versions_are_listed_then_read_one_by_one(client):
    _template(client)
    _template(client, title="renamed")
    listed = client.get(f"/dmps/{TEMPLATE}/versions", headers=_auth("read")).json()
    assert [v["version"] for v in listed["versions"]] == [1, 2]
    first = client.get(f"/dmps/{TEMPLATE}/versions/1", headers=_auth("read")).json()
    assert first["dmp"]["title"] == "title"


@pytest.mark.parametrize(
    "path",
    [f"/dmps/{TEMPLATE}", f"/dmps/{TEMPLATE}/versions", f"/dmps/{TEMPLATE}/versions/1"],
)
def test_an_unknown_dmp_is_not_found(client, path):
    assert client.get(path, headers=_auth("read")).status_code == 404


# The whole way


def test_a_template_then_a_production_written_twice(client):
    """A template written, read back, filled into a production, which is
    changed once, then refused when changed again from the version before."""
    _template(client)
    template = client.get(f"/dmps/{TEMPLATE}", headers=_auth("write")).json()
    body = {
        "from_template_version": template["version"],
        "dmp": {**template["dmp"], "title": "mission 1"},
        "metadata": template["metadata"],
    }
    created = client.post("/productions", json=body, headers=_auth("write")).json()
    key = created["key"]
    body = {**body, "based_on": 1, "dmp": {**body["dmp"], "title": "mission 1, v2"}}
    assert (
        client.post(
            f"/productions/{key}/versions", json=body, headers=_auth("write")
        ).status_code
        == 201
    )
    stale = client.post(
        f"/productions/{key}/versions", json=body, headers=_auth("write")
    )
    assert stale.status_code == 409
    latest = client.get(f"/dmps/{key}", headers=_auth("read")).json()
    assert (latest["version"], latest["dmp"]["title"]) == (2, "mission 1, v2")
    assert latest["from_template_version"] == 1


# A document rendered from a template

# The values tried, in this order, for a value question with patterns.
CANDIDATES = (
    "eng",
    "ES",
    "EUR",
    "2026-01-01",
    "0000-0002-1825-0097",
    "10.1234/madmp",
    "https://example.org/madmp",
    "1",
)

# A value of each DSW value type, for a value question without patterns. A
# string one is written as "madmp <rules path>".
TYPED = {
    "EmailQuestionValueType": "data.centre@example.org",
    "UrlQuestionValueType": "https://example.org/madmp",
    "DateQuestionValueType": "2026-01-01",
    "DateTimeQuestionValueType": "2026-01-01T00:00:00Z",
    "NumberQuestionValueType": "1",
}


class _Replies:
    """The replies to every required question of a KM, as DSW holds them: a
    path of entity uuids joined with dots, and its value, a string, or the
    uuids of the items or the choices.

    Each required question gets a reply of its kind: the first answer of an
    options question, the first choice of a multi-choice one, one item of a
    list, then a value of its type for a value question, the first of
    ``CANDIDATES`` its patterns accept when it has some, ``title`` for the
    title.
    """

    def __init__(self, events: list[dict[str, Any]], title: str):
        self.children: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            self.children.setdefault(event["parentUuid"], []).append(event)
        self.title = title
        self.replies: dict[str, Any] = {}
        root = next(
            e["entityUuid"]
            for e in events
            if e["content"]["eventType"] == "AddKnowledgeModelEvent"
        )
        for chapter in self.entities(root, "AddChapterEvent"):
            for question in self.children.get(chapter["entityUuid"], []):
                self.reply(question, chapter["entityUuid"])

    def entities(self, parent: str, event_type: str) -> list[dict[str, Any]]:
        return [
            e
            for e in self.children.get(parent, [])
            if e["content"]["eventType"] == event_type
        ]

    def value(self, question: dict[str, Any]) -> str:
        """A value the question takes."""
        content = question["content"]
        annotations = content.get("annotations") or []
        path = annotations[0]["value"] if annotations else ""
        if path == "title":
            return self.title
        patterns = [
            v["value"]
            for v in content.get("validations") or []
            if v["type"] == "RegexQuestionValidation"
        ]
        if patterns:
            for candidate in CANDIDATES:
                if all(re.fullmatch(p, candidate) for p in patterns):
                    return candidate
            pytest.fail(f"{path}: no value of CANDIDATES matches {patterns}")
        return TYPED.get(content.get("valueType"), f"madmp {path}")

    def reply(self, question: dict[str, Any], prefix: str) -> None:
        """Reply to a required question under ``prefix``, then to the
        required questions its reply opens."""
        content = question["content"]
        if not content.get("requiredPhaseUuid"):
            return
        entity = question["entityUuid"]
        path = f"{prefix}.{entity}"
        kind = content["questionType"]
        if kind == "ValueQuestion":
            self.replies[path] = self.value(question)
        elif kind == "OptionsQuestion":
            answer = next(
                a
                for a in self.entities(entity, "AddAnswerEvent")
                if a["content"]["label"] != "Other"
            )
            self.replies[path] = answer["entityUuid"]
            for child in self.children.get(answer["entityUuid"], []):
                self.reply(child, f"{path}.{answer['entityUuid']}")
        elif kind == "MultiChoiceQuestion":
            choice = self.entities(entity, "AddChoiceEvent")[0]
            self.replies[path] = [choice["entityUuid"]]
        elif kind == "ListQuestion":
            item = str(uuid.uuid4())
            self.replies[path] = [item]
            children = self.children.get(entity, [])
            # A list of one value: its only question, not required itself.
            if len(children) == 1 and not children[0]["content"].get(
                "requiredPhaseUuid"
            ):
                self.replies[f"{path}.{item}.{children[0]['entityUuid']}"] = self.value(
                    children[0]
                )
            for child in children:
                self.reply(child, f"{path}.{item}")


class _Ctx:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


def _rendered(body: str, replies: dict[str, Any]) -> dict:
    """The document a template body renders, DSW's three reply filters stubbed:
    ``reply_path`` joins a chain of uuids with dots, ``reply_str_value`` and
    ``reply_items`` give the reply as it is held."""
    env = jinja2.Environment()
    env.filters["reply_path"] = lambda parts: ".".join(str(p) for p in parts)
    env.filters["reply_str_value"] = lambda reply: reply
    env.filters["reply_items"] = lambda reply: reply
    ctx = _Ctx(
        project=_Ctx(
            replies=replies,
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-02T00:00:00Z",
            uuid="1111",
        ),
        config=_Ctx(clientUrl="https://dsw.example"),
    )
    return json.loads(env.from_string(body).render(ctx=ctx))


@pytest.mark.parametrize(
    "path", files(PROJECTS), ids=lambda p: f"{p.parent.name}-{p.stem}"
)
def test_a_document_rendered_from_a_template_is_stored(client, path: Path):
    """Each project version's template, its required questions answered,
    renders a document the API stores as the project's template DMP, every
    check passed."""
    definition = load(PROJECTS, path)
    packages = build(definition, model_for(definition["rules"]))
    title = "madmp rendered"
    replies = _Replies(packages.km["packages"][0]["events"], title).replies
    document = _rendered(packages.template["files"][0]["content"], replies)

    written = client.post("/templates", json=document, headers=_auth("template"))
    assert written.status_code == 201, written.text

    key = template_key(definition["organizationId"], definition["id"])
    stored = client.get(f"/dmps/{key}", headers=_auth("read")).json()
    assert stored["dmp"]["title"] == title
    assert stored["project_version"] == definition["version"]
    assert stored["assessment"]["fail"] == []
