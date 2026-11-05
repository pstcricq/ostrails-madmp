"""Which package the instance holds already, compared with the one built, and
what is uploaded, against an instance written for the tests."""

import io
import json
import zipfile

import pytest

from madmp.definitions import PROJECTS, load
from madmp.dsw.client import DswClient
from madmp.dsw.publish import (
    TEMPLATE_ENTRY,
    publish_packages,
    published_ids,
    without_stamps,
)
from madmp.errors import PublishError
from madmp.model import model_for
from madmp.packages.build import build
from madmp.packages.common import package_id
from tests import ROOT

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"
STAMP = "2026-01-01T00:00:00.000Z"


@pytest.fixture
def definition():
    return load(PROJECTS, GLIDER_PROJECT)


def test_a_listing_is_read_as_the_three_names_of_one_package():
    items = [
        {"organizationId": "org", "kmId": "km", "version": "1.0.0", "uuid": "a"},
        {"organizationId": "org", "kmId": "km", "version": "2.0.0", "uuid": "b"},
    ]
    assert published_ids(items, "kmId") == {"org:km:1.0.0": "a", "org:km:2.0.0": "b"}


class _Packages(DswClient):
    """An instance holding versions of glider's KM and template, each version
    the bundles ``held`` gives for it, and recording what is uploaded."""

    def __init__(self, km_versions, template_versions, held=None):
        super().__init__("http://dsw/wizard-api", "a-token")
        self.km_versions, self.template_versions = km_versions, template_versions
        self.held = held
        self.uploaded = []

    def get(self, path):
        if path.startswith("/knowledge-model-packages?"):
            if not self.km_versions:
                return {"_embedded": {"knowledgeModelPackages": []}, "page": {}}
            latest = {"uuid": "km-latest", "organizationId": "socib", "kmId": "glider"}
            return {"_embedded": {"knowledgeModelPackages": [latest]}, "page": {}}
        if path == "/knowledge-model-packages/km-latest":
            return {
                "versions": [
                    {"version": v, "uuid": f"km-{v}"} for v in self.km_versions
                ]
            }
        if path.startswith("/document-templates/all"):
            return [
                {
                    "organizationId": "socib",
                    "templateId": "glider",
                    "version": v,
                    "uuid": f"tpl-{v}",
                }
                for v in self.template_versions
            ]
        raise AssertionError(path)

    def download(self, path):
        km, template = self.held
        if path.startswith("/knowledge-model-packages/km-"):
            return json.dumps(km).encode()
        if path.startswith("/document-templates/tpl-"):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(TEMPLATE_ENTRY, json.dumps(template))
            return buffer.getvalue()
        raise AssertionError(path)

    def post_bundle(self, path, filename, content_type, content):
        self.uploaded.append(path)
        return {"organizationId": "socib", "kmId": "glider", "version": "x"}


def _packages(definition, stamp=STAMP):
    packages = build(definition, model_for(definition["rules"]), created_at=stamp)
    return packages.km, packages.template


def test_the_time_stamps_are_left_out_at_any_depth():
    bundle = {"createdAt": "t", "a": [{"createdAt": "t", "b": 1}], "c": {"d": 2}}
    assert without_stamps(bundle) == {"a": [{"b": 1}], "c": {"d": 2}}


def test_a_version_already_there_the_same_is_skipped(definition):
    """An older KM version is found in the record of the latest one, and its
    bundles, stamped at another time, are the same."""
    older = {**definition, "version": "0.9.0"}
    held = _packages(definition, stamp="2025-06-01T00:00:00Z")
    dsw = _Packages(["0.9.0", "1.0.0"], ["0.9.0", "1.0.0"], held)
    lines = publish_packages(dsw, older, *_packages(definition))
    assert dsw.uploaded == []
    assert lines == [
        "KM socib:glider:0.9.0 already published.",
        "Template socib:glider:0.9.0 already published.",
    ]


def test_a_version_there_with_another_content_is_refused(definition):
    """Nothing uploaded, not even the template the instance does not hold."""
    km, template = _packages(definition)
    held = ({**km, "name": "Another name"}, template)
    dsw = _Packages(["1.0.0"], [], held)
    with pytest.raises(PublishError) as caught:
        publish_packages(dsw, definition, km, template)
    assert dsw.uploaded == []
    refused = (
        f"KM {package_id(definition)} is published with another content: give "
        "the project a new version to publish this one."
    )
    assert caught.value.problems == [refused]


def test_only_what_is_missing_is_uploaded(definition):
    dsw = _Packages(["1.0.0"], [], _packages(definition))
    lines = publish_packages(dsw, definition, *_packages(definition))
    assert dsw.uploaded == ["/document-templates/bundle"]
    assert lines[0] == f"KM {package_id(definition)} already published."


def test_a_new_instance_gets_both(definition):
    dsw = _Packages([], [])
    publish_packages(dsw, definition, *_packages(definition))
    assert dsw.uploaded == [
        "/knowledge-model-packages/bundle",
        "/document-templates/bundle",
    ]
