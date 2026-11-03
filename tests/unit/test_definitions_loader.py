"""A definition of any kind read, checked and listed, on a kind of things
written for the tests, then on every kind of the repository."""

import json

import pytest

from madmp.definitions import KINDS, Kind, files, load
from madmp.errors import SchemaFileError


class ThingFileError(SchemaFileError):
    pass


@pytest.fixture
def kind(tmp_path):
    """A kind of things, in ``things/``, keyed by ``name``, in JSON, refusing
    a thing that calls itself ``bad``."""
    directory = tmp_path / "things"
    directory.mkdir()
    schema = directory / "thing.schema.json"
    schema.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["name", "version"],
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                },
            }
        )
    )
    return Kind(
        directory=directory,
        schema=schema,
        key="name",
        suffix=".json",
        error=ThingFileError,
        checks=lambda doc: ["is bad."] if doc["name"] == "bad" else [],
    )


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_a_thing_where_it_says_loads(kind, tmp_path):
    path = _write(kind.directory, "a/1.0.0.json", '{"name": "a", "version": "1.0.0"}')
    assert load(kind, path) == {"name": "a", "version": "1.0.0"}


def test_the_key_names_the_directory_and_the_version_the_file(kind, tmp_path):
    path = _write(kind.directory, "b/2.0.0.json", '{"name": "a", "version": "1.0.0"}')
    with pytest.raises(ThingFileError) as caught:
        load(kind, path)
    problems = caught.value.problems
    assert "declares name 'a' but sits in directory 'b'" in problems[0]
    assert "declares version '1.0.0' but is named '2.0.0'" in problems[1]


def test_the_kind_s_own_checks_run_once_the_schema_passed(kind, tmp_path):
    path = _write(
        kind.directory, "bad/1.0.0.json", '{"name": "bad", "version": "1.0.0"}'
    )
    with pytest.raises(ThingFileError, match="is bad"):
        load(kind, path)


def test_the_schema_comes_first(kind, tmp_path):
    path = _write(kind.directory, "a/1.0.0.json", '{"name": "a"}')
    with pytest.raises(ThingFileError, match="'version' is a required property"):
        load(kind, path)


def test_a_file_of_another_format_is_refused_not_skipped(kind, tmp_path):
    path = _write(kind.directory, "a/1.0.0.yaml", "name: a\nversion: 1.0.0\n")
    assert files(kind) == [path]
    with pytest.raises(ThingFileError, match="things are .json files"):
        load(kind, path)


@pytest.mark.parametrize(
    "text, message", [("{", "invalid JSON"), ("[]", "is not of type 'object'")]
)
def test_what_does_not_parse_is_the_kind_s_error(kind, tmp_path, text, message):
    path = _write(kind.directory, "a/1.0.0.json", text)
    with pytest.raises(ThingFileError, match=message):
        load(kind, path)


def test_a_file_that_cannot_be_read_is_the_kind_s_error(kind, tmp_path):
    with pytest.raises(ThingFileError, match="cannot be read"):
        load(kind, kind.directory / "a" / "1.0.0.json")


def test_files_are_listed_by_key_then_version_by_number(kind, tmp_path):
    for relative in ("b/1.0.0.json", "a/1.10.0.json", "a/1.9.0.json", "a/.DS_Store"):
        _write(kind.directory, relative, "")
    listed = [f"{p.parent.name}/{p.name}" for p in files(kind)]
    assert listed == ["a/1.9.0.json", "a/1.10.0.json", "b/1.0.0.json"]


def test_the_schema_beside_the_files_is_not_one_of_them(kind, tmp_path):
    assert files(kind) == []


# The real kinds


def test_the_kinds_in_their_order():
    assert [kind.name for kind in KINDS] == ["rules", "projects"]


@pytest.mark.parametrize("kind", KINDS, ids=lambda k: k.name)
def test_every_real_file_of_every_kind_loads(kind):
    paths = files(kind)
    assert paths
    for path in paths:
        assert load(kind, path)[kind.key] == path.parent.name
