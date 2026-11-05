"""Each project version's KM and document template, built in memory and
uploaded when the instance lacks them, oldest first. One the instance holds is
compared without its ``createdAt`` stamps: the same is skipped, another
content refused.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from madmp.dsw.client import DswClient
from madmp.errors import PublishError
from madmp.packages.common import package_id

# Where a template bundle holds the template, the zip the endpoint takes and
# gives back.
TEMPLATE_ENTRY = "template/template.json"

# What the instance holds


def published_ids(items: list[dict[str, Any]], id_key: str) -> dict[str, str]:
    """A listing as ``package_id -> uuid``: the API routes a package by its
    uuid, and its listings spell the id out in three fields."""
    return {
        f"{item['organizationId']}:{item[id_key]}:{item['version']}": item["uuid"]
        for item in items
    }


def published_kms(client: DswClient, organization: str, km_id: str) -> dict[str, str]:
    """Every published version of one KM, as ``package_id -> uuid``. The
    listing gives one row per KM, its latest version, whose own record lists
    every version."""
    latest = client.list_all(
        f"/knowledge-model-packages?organizationId={organization}&kmId={km_id}",
        "knowledgeModelPackages",
    )
    if not latest:
        return {}
    record = client.get(f"/knowledge-model-packages/{latest[0]['uuid']}")
    return {
        f"{organization}:{km_id}:{version['version']}": version["uuid"]
        for version in record["versions"]
    }


def published_templates(
    client: DswClient, organization: str, template_id: str
) -> dict[str, str]:
    """Every published version of one document template, as
    ``package_id -> uuid``."""
    return published_ids(
        client.get(
            f"/document-templates/all?organizationId={organization}"
            f"&templateId={template_id}"
        ),
        "templateId",
    )


def published_km(client: DswClient, uuid: str) -> dict[str, Any]:
    """The bundle of a published KM version, as it was uploaded."""
    return json.loads(client.download(f"/knowledge-model-packages/{uuid}/bundle"))


def published_template(client: DswClient, uuid: str) -> dict[str, Any]:
    """The template of a published template version, as it was uploaded."""
    bundle = client.download(f"/document-templates/{uuid}/bundle")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        return json.loads(archive.read(TEMPLATE_ENTRY))


def without_stamps(value: Any) -> Any:
    """A bundle without its time stamps, every ``createdAt`` at any depth."""
    if isinstance(value, dict):
        return {k: without_stamps(v) for k, v in value.items() if k != "createdAt"}
    if isinstance(value, list):
        return [without_stamps(item) for item in value]
    return value


# Uploading


def publish_km(client: DswClient, km: dict[str, Any]) -> str:
    """Upload a KM bundle, and say what was published."""
    result = client.post_bundle(
        "/knowledge-model-packages/bundle",
        "km.km",
        "application/json",
        json.dumps(km, ensure_ascii=False).encode(),
    )
    return (
        f"KM published: {result.get('organizationId')}:{result.get('kmId')}:"
        f"{result.get('version')}"
    )


def publish_template(client: DswClient, template: dict[str, Any]) -> str:
    """Upload a document template bundle, zipped as the endpoint expects it,
    ``template/template.json``, and say what was published."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(TEMPLATE_ENTRY, json.dumps(template, ensure_ascii=False))
    result = client.post_bundle(
        "/document-templates/bundle",
        "template.zip",
        "application/zip",
        buffer.getvalue(),
    )
    return f"Template published: {result.get('name')} ({result.get('uuid')})"


def publish_packages(
    client: DswClient,
    definition: dict[str, Any],
    km: dict[str, Any],
    template: dict[str, Any],
) -> list[str]:
    """A project version's KM and template, each uploaded unless the instance
    holds it already, one line each. A ``PublishError`` names each one the
    instance holds with another content, before anything is uploaded."""
    organization, project = definition["organizationId"], definition["id"]
    pid = package_id(definition)
    steps, problems = [], []
    for label, published_of, read, publish, bundle in (
        ("KM", published_kms, published_km, publish_km, km),
        (
            "Template",
            published_templates,
            published_template,
            publish_template,
            template,
        ),
    ):
        uuid = published_of(client, organization, project).get(pid)
        if uuid is None:
            steps.append((None, publish, bundle))
        elif without_stamps(read(client, uuid)) == without_stamps(bundle):
            steps.append((f"{label} {pid} already published.", None, None))
        else:
            problems.append(
                f"{label} {pid} is published with another content: give the "
                "project a new version to publish this one."
            )
    if problems:
        raise PublishError(problems)
    return [line or publish(client, bundle) for line, publish, bundle in steps]
