"""Both packages of a project version come out together, a broken one is
refused with every problem it has, and both are written as the files DSW
imports."""

import json

import pytest

from madmp.definitions import PROJECTS, load
from madmp.errors import PackageError
from madmp.model import model_for
from madmp.packages import build as build_module
from madmp.packages.build import build, write
from madmp.packages.common import package_id
from tests import ROOT

GLIDER_PROJECT = ROOT / "definitions" / "projects" / "glider" / "1.0.0.yaml"
STAMP = "2026-01-01T00:00:00.000Z"


@pytest.fixture(scope="module")
def definition():
    return load(PROJECTS, GLIDER_PROJECT)


@pytest.fixture(scope="module")
def model(definition):
    return model_for(definition["rules"])


def test_both_packages_carry_the_package_id_and_one_time_stamp(definition, model):
    packages = build(definition, model, created_at=STAMP)
    assert packages.km["id"] == packages.template["id"] == package_id(definition)
    assert packages.km["packages"][0]["createdAt"] == STAMP
    assert packages.template["createdAt"] == STAMP


def test_a_km_that_emits_an_entity_twice_is_refused(monkeypatch, definition, model):
    real = build_module.build_km_bundle

    def twice(*args, **kwargs):
        km = real(*args, **kwargs)
        events = km["packages"][0]["events"]
        events.append(dict(events[-1]))
        return km

    monkeypatch.setattr(build_module, "build_km_bundle", twice)
    with pytest.raises(PackageError) as refused:
        build(definition, model, created_at=STAMP)
    assert refused.value.subject == package_id(definition)
    assert refused.value.problems[0].startswith("the KM emits 1 entity(ies) twice")


def test_a_template_that_is_not_jinja_is_refused(monkeypatch, definition, model):
    real = build_module.build_template_bundle

    def broken(*args, **kwargs):
        template = real(*args, **kwargs)
        template["files"][0]["content"] += "{% if %}"
        return template

    monkeypatch.setattr(build_module, "build_template_bundle", broken)
    with pytest.raises(PackageError) as refused:
        build(definition, model, created_at=STAMP)
    assert refused.value.problems[0].startswith("the document template is not Jinja")


def test_both_packages_are_written_as_the_files_dsw_imports(
    tmp_path, definition, model
):
    packages = build(definition, model, created_at=STAMP)
    out = tmp_path / "packages"
    km_file, template_file = write(packages, definition, out)
    assert (km_file.name, template_file.name) == (
        "glider_1.0.0_km.km",
        "glider_1.0.0_template.json",
    )
    assert json.loads(km_file.read_text()) == packages.km
    assert json.loads(template_file.read_text()) == packages.template
