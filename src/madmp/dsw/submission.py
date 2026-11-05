"""The submission service of a DS Wizard instance, which sends a submitted
document to SUBMISSION_URL with TEMPLATE_WRITE_TOKEN. Its formats gain those
of the repository's templates the instance holds, the others kept, and the
tenant's configuration is written only when the service differs.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from madmp.dsw.client import DswClient
from madmp.dsw.publish import published_templates
from madmp.errors import PublishError
from madmp.packages.common import SUBMISSION_FORMAT, package_id
from madmp.packages.uuids import format_uuid

# The submission service, as the Submit menu shows it.
SERVICE_ID = "madmp"
SERVICE_NAME = "Assess and store the maDMP"
SERVICE_DESCRIPTION = (
    "Checks this maDMP against the rules its template was built from, the "
    "standards named in its metadata, then stores it as the next version of "
    "the project's DMP. A maDMP that does not hold up is refused, with the "
    "fields to fix."
)

# The format a submitted document is rendered in, the one the template names.
SUBMISSION_FORMAT_UUID = format_uuid(SUBMISSION_FORMAT)

# What a write carries, at each of the two levels of a service.
_WRITTEN_SERVICE_FIELDS = ("id", "name", "description", "props", "request")
_WRITTEN_FORMAT_FIELDS = ("templateUuid", "formatUuid")

# What each value says, for the message that names a missing one.
_VALUES = {
    "SUBMISSION_URL": "says where DSW sends a submitted document",
    "TEMPLATE_WRITE_TOKEN": "is the secret DSW sends with it",
}


@dataclass(frozen=True)
class Webhook:
    """Where the submission service sends a document, and the secret it sends
    with it, ``Authorization: Bearer <token>``. The token is kept out of
    ``repr``."""

    url: str
    token: str = field(repr=False)


def from_environment() -> Webhook:
    """The webhook, or every missing name at once."""
    values = {name: os.environ.get(name) for name in _VALUES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise PublishError(
            [f"{name} is not set, it {_VALUES[name]}." for name in missing]
        )
    return Webhook(values["SUBMISSION_URL"], values["TEMPLATE_WRITE_TOKEN"])


def submission_service(
    template_uuids: list[str],
    webhook: Webhook,
    kept: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """The submission service, in the shape a write takes, for the templates
    of these uuids, the formats ``kept`` beside them. The fields the instance
    assigns, a tenant uuid on the service and on each format, the service id
    inside a format, two time stamps, are left out."""
    ours = [
        {"templateUuid": template_uuid, "formatUuid": SUBMISSION_FORMAT_UUID}
        for template_uuid in template_uuids
    ]
    formats = {(f["templateUuid"], f["formatUuid"]): f for f in [*kept, *ours]}
    return {
        "id": SERVICE_ID,
        "name": SERVICE_NAME,
        "description": SERVICE_DESCRIPTION,
        "props": [],
        "request": {
            "headers": {"Authorization": f"Bearer {webhook.token}"},
            "method": "POST",
            "multipart": {"enabled": False, "fileName": ""},
            "url": webhook.url,
        },
        # Each once, sorted, as installed_service() reads them back.
        "supportedFormats": [
            formats[key] for key in sorted(formats, key=_format_order)
        ],
    }


def installed_service(service: dict[str, Any]) -> dict[str, Any]:
    """A service the instance returned, reduced to what a write carries, its
    formats sorted."""
    formats = [
        {name: fmt.get(name) for name in _WRITTEN_FORMAT_FIELDS}
        for fmt in service.get("supportedFormats") or []
    ]
    return {
        **{name: service.get(name) for name in _WRITTEN_SERVICE_FIELDS},
        "supportedFormats": sorted(
            formats,
            key=lambda fmt: _format_order((fmt["templateUuid"], fmt["formatUuid"])),
        ),
    }


def _format_order(key: tuple[str | None, str | None]) -> tuple[str, str]:
    """A format's place in the list: its template, then its format."""
    return key[0] or "", key[1] or ""


def submission(
    client: DswClient, definitions: list[dict[str, Any]], webhook: Webhook
) -> str:
    """Create or refresh the submission service for the templates of
    ``definitions`` the instance holds, beside the formats it supports
    already, and say what it took. The tenant's other services are left as
    they are. Written only when the service says something else, or when
    submissions are turned off."""
    published: dict[str, str] = {}
    for organization, project in dict.fromkeys(
        (d["organizationId"], d["id"]) for d in definitions
    ):
        published.update(published_templates(client, organization, project))
    held = [package_id(d) for d in definitions if package_id(d) in published]
    tenant = client.get("/tenants/current/config")
    submission = tenant.setdefault("submission", {})
    services = submission.setdefault("services", [])
    current = next((s for s in services if s.get("id") == SERVICE_ID), None)
    kept = [] if current is None else installed_service(current)["supportedFormats"]
    service = submission_service([published[pid] for pid in held], webhook, kept)
    templates = ", ".join(held) or "none"
    if (
        current is not None
        and installed_service(current) == service
        and submission.get("enabled")
    ):
        return f"Submission service {SERVICE_ID!r} unchanged (templates {templates})."
    submission["enabled"] = True
    services[:] = [s for s in services if s.get("id") != SERVICE_ID] + [service]
    client.put("/tenants/current/config", tenant)
    return (
        f"Submission service {SERVICE_ID!r} -> {webhook.url} (templates {templates})."
    )
