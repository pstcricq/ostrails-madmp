"""What the submission service says, read from the environment, and when it is
written, against an instance written for the tests."""

import pytest

from madmp.definitions import PROJECTS, load
from madmp.dsw.client import DswClient
from madmp.dsw.submission import (
    SERVICE_ID,
    SUBMISSION_FORMAT_UUID,
    Webhook,
    from_environment,
    installed_service,
    submission,
    submission_service,
)
from madmp.errors import PublishError
from madmp.model import model_for
from madmp.packages.build import build
from tests import ROOT

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"
STAMP = "2026-01-01T00:00:00.000Z"
WEBHOOK = Webhook("http://dmp-api:8081/templates", "s3cret")


@pytest.fixture
def definition():
    return load(PROJECTS, GLIDER_PROJECT)


def _packages(definition):
    packages = build(definition, model_for(definition["rules"]), created_at=STAMP)
    return packages.km, packages.template


# Where the service sends a document


def test_the_webhook_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("SUBMISSION_URL", "http://dmp-api:8081/templates")
    monkeypatch.setenv("TEMPLATE_WRITE_TOKEN", "s3cret")
    assert from_environment() == WEBHOOK


def test_every_missing_value_is_named_at_once(monkeypatch):
    for name in ("SUBMISSION_URL", "TEMPLATE_WRITE_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(PublishError) as caught:
        from_environment()
    assert len(caught.value.problems) == 2


def test_the_token_stays_out_of_repr():
    assert "s3cret" not in repr(WEBHOOK)


# What the submission service says

# What the instance stamps on a service of its own accord, and hands back on
# the next read.
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def as_dsw_returns_it(service: dict) -> dict:
    """The same service in the shape ``GET /tenants/current/config`` gives it
    back: a tenant uuid on the service and on each format, the service id
    inside each format, two time stamps."""
    return {
        **service,
        "tenantUuid": TENANT,
        "createdAt": "2026-07-01T10:00:00.000Z",
        "updatedAt": "2026-07-01T10:00:00.000Z",
        "supportedFormats": [
            {**fmt, "tenantUuid": TENANT, "serviceId": service["id"]}
            for fmt in service["supportedFormats"]
        ],
    }


def test_the_service_posts_to_the_webhook_with_its_secret():
    service = submission_service(["tpl"], WEBHOOK)
    assert service["id"] == SERVICE_ID
    assert service["name"] == "Assess and store the maDMP"
    assert service["description"].startswith("Checks this maDMP")
    assert service["request"]["url"] == "http://dmp-api:8081/templates"
    assert service["request"]["method"] == "POST"
    assert service["request"]["headers"] == {"Authorization": "Bearer s3cret"}


def test_the_service_supports_the_json_format_of_each_template():
    service = submission_service(["b", "a"], WEBHOOK)
    assert service["supportedFormats"] == [
        {"templateUuid": "a", "formatUuid": SUBMISSION_FORMAT_UUID},
        {"templateUuid": "b", "formatUuid": SUBMISSION_FORMAT_UUID},
    ]


def test_the_format_it_names_is_one_the_template_carries(definition):
    _, template = _packages(definition)
    assert SUBMISSION_FORMAT_UUID in {fmt["uuid"] for fmt in template["formats"]}


def test_what_the_instance_stamped_is_not_a_difference():
    service = submission_service(["b", "a"], WEBHOOK)
    returned = as_dsw_returns_it(service)
    returned["supportedFormats"].reverse()
    assert installed_service(service) == service
    assert installed_service(returned) == service


# Writing it: only when it would say something else


class _Tenant(DswClient):
    """An instance reduced to what ``submission`` reads, published templates and
    a tenant configuration it may rewrite."""

    def __init__(self, templates, services, enabled=True):
        super().__init__("http://dsw/wizard-api", "a-token")
        self.templates = templates
        self.tenant = {
            "organization": {"name": "Example"},
            "submission": {"enabled": enabled, "services": list(services)},
        }
        self.puts = []

    def get(self, path):
        if path.startswith("/document-templates/all"):
            return self.templates
        return self.tenant

    def put(self, path, payload):
        self.puts.append(payload)


def _template(version, uuid):
    return {
        "organizationId": "socib",
        "templateId": "glider",
        "version": version,
        "uuid": uuid,
    }


def test_a_service_that_already_says_this_is_not_written_again(definition):
    current = as_dsw_returns_it(submission_service(["tpl"], WEBHOOK))
    client = _Tenant([_template("1.0.0", "tpl")], [current])
    line = submission(client, [definition], WEBHOOK)
    assert client.puts == []
    assert "unchanged" in line


@pytest.mark.parametrize(
    "existing, enabled",
    [
        pytest.param([], True, id="no service yet"),
        pytest.param(
            [{"id": SERVICE_ID, "request": {"url": "http://old"}}],
            True,
            id="a service saying something else",
        ),
        pytest.param(None, False, id="the right service, submissions turned off"),
    ],
)
def test_anything_else_is_written(definition, existing, enabled):
    services = (
        [as_dsw_returns_it(submission_service(["tpl"], WEBHOOK))]
        if existing is None
        else existing
    )
    client = _Tenant([_template("1.0.0", "tpl")], services, enabled=enabled)
    submission(client, [definition], WEBHOOK)
    assert len(client.puts) == 1
    written = client.puts[0]["submission"]
    assert written["enabled"] is True
    assert [s["id"] for s in written["services"]] == [SERVICE_ID]


def test_the_tenant_s_other_services_are_left_untouched(definition):
    other = {"id": "elsewhere", "request": {"url": "http://elsewhere"}}
    client = _Tenant([_template("1.0.0", "tpl")], [other])
    submission(client, [definition], WEBHOOK)
    services = client.puts[0]["submission"]["services"]
    assert services[0] == other
    assert [s["id"] for s in services] == ["elsewhere", SERVICE_ID]


def test_the_service_names_every_version_the_instance_holds(definition):
    """Every version the instance holds is named, one it does not hold left
    out."""
    older = {**definition, "version": "0.9.0"}
    newer = {**definition, "version": "2.0.0"}
    client = _Tenant([_template("0.9.0", "old"), _template("1.0.0", "tpl")], [])
    line = submission(client, [older, definition, newer], WEBHOOK)
    formats = client.puts[0]["submission"]["services"][0]["supportedFormats"]
    assert [f["templateUuid"] for f in formats] == ["old", "tpl"]
    assert "socib:glider:2.0.0" not in line


def test_the_formats_the_service_supports_already_are_kept(definition):
    """A format added by hand, and one of a template the repository no longer
    has, stay beside the one added; the request is written over."""
    by_hand = {"templateUuid": "by-hand", "formatUuid": "another-format"}
    gone = {"templateUuid": "gone", "formatUuid": SUBMISSION_FORMAT_UUID}
    current = as_dsw_returns_it(
        {
            **submission_service([], Webhook("http://old", "old")),
            "supportedFormats": [by_hand, gone],
        }
    )
    client = _Tenant([_template("1.0.0", "tpl")], [current])
    submission(client, [definition], WEBHOOK)
    written = client.puts[0]["submission"]["services"][0]
    assert written["supportedFormats"] == [
        by_hand,
        gone,
        {"templateUuid": "tpl", "formatUuid": SUBMISSION_FORMAT_UUID},
    ]
    assert written["request"]["url"] == "http://dmp-api:8081/templates"


def test_a_format_already_there_is_not_added_twice():
    service = submission_service(
        ["tpl"],
        WEBHOOK,
        [{"templateUuid": "tpl", "formatUuid": SUBMISSION_FORMAT_UUID}],
    )
    assert service["supportedFormats"] == [
        {"templateUuid": "tpl", "formatUuid": SUBMISSION_FORMAT_UUID}
    ]
