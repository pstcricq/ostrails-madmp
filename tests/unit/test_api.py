"""The DMP API before the database: ``check_document()``, the settings, and a
write refused when the database cannot be reached.
"""

import copy
import json
from collections.abc import Callable
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from madmp.api import check_document
from madmp.api.app import Settings, app, from_environment
from madmp.api.service import _SPELLED_OUT
from madmp.errors import AssessmentError, RequestError
from madmp.store import Database
from tests import FIXTURES

METADATA = {
    "project": "glider",
    "project_version": "1.0.0",
    "rules": [{"rda_dcs": "1.0.0"}, {"ostrails": "1.0.0"}],
}
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


def _template(client, **dmp):
    return client.post("/templates", json=_document(**dmp), headers=_auth("template"))


# What a document goes through before the database


@pytest.mark.parametrize(
    "document, problem",
    [
        ({"metadata": METADATA}, "no dmp object"),
        ({"dmp": {}}, "no 'metadata' object"),
        ({"dmp": {}, "metadata": {**METADATA, "project_version": "1.0"}}, "not X.Y.Z"),
        ({"dmp": {}, "metadata": {**METADATA, "rules": []}}, "metadata.rules"),
        (
            {"dmp": {}, "metadata": {**METADATA, "project": "nope"}},
            "'nope' is not defined",
        ),
        (
            {"dmp": {}, "metadata": {**METADATA, "project_version": "9.9.9"}},
            "glider 9.9.9 is not defined",
        ),
    ],
)
def test_a_document_that_cannot_be_taken_is_refused(document, problem):
    with pytest.raises(RequestError, match=problem):
        check_document(document)


def test_a_document_that_does_not_hold_up_is_refused_with_what_to_fix():
    with pytest.raises(AssessmentError) as caught:
        check_document({"dmp": {}, "metadata": METADATA})
    message = str(caught.value)
    assert message.startswith(
        "Assessment failed against rda_dcs 1.0.0, ostrails 1.0.0."
    )
    assert "failure(s) to fix" in message and "checks passed" in message


def test_a_long_refusal_is_cut_and_says_so():
    dmp = {f"x{n}": n for n in range(_SPELLED_OUT + 5)}
    with pytest.raises(AssessmentError, match=r"\[\.\.\.\] \d+ more not shown"):
        check_document({"dmp": dmp, "metadata": METADATA})


def test_a_document_that_holds_up_passes_with_its_assessment():
    checked = check_document(_document())
    assert checked.project == "glider"
    assert checked.assessment["verdict"] == "pass"


# Startup


def test_every_unset_variable_is_named_at_once(monkeypatch):
    for name in ("TEMPLATE_WRITE_TOKEN", "DMP_READ_TOKEN", "DMP_WRITE_TOKEN", "DMP_DB"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="TEMPLATE_WRITE_TOKEN, DMP_READ_TOKEN"):
        from_environment()


def test_the_tokens_stay_out_of_repr():
    settings = Settings("t", "r", "w", Database("h", 5432, "d", "u", "p"))
    assert "'t'" not in repr(settings) and "'w'" not in repr(settings)


def test_an_unreachable_database_writes_nothing_and_says_so():
    unreachable = Database("127.0.0.1", 1, "dmp", "u", "p")
    settings = Settings(
        TOKENS["template"], TOKENS["read"], TOKENS["write"], unreachable
    )
    with served(settings, lambda settings: None) as client:
        answer = _template(client)
    assert answer.status_code == 503
    assert "nothing was written" in answer.text
