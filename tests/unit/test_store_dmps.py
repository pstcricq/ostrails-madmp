"""The keys a DMP is written under."""

from madmp.store import production_key, template_key


def test_a_template_key_names_organization_and_project():
    assert template_key("example", "project") == "example-project-template"


def test_a_production_key_has_four_digits_at_least():
    assert production_key("example", "project", 1) == "example-project-0001"
    assert production_key("example", "project", 12345) == "example-project-12345"
