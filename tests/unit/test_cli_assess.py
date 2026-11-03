"""madmp assess conformance on the fixtures and on documents written for a test."""

import json

import pytest

from madmp.cli import main
from tests import FIXTURES


def test_every_fixture_passes_its_assessment(capsys):
    """The directory stands for every JSON file in it."""
    count = len(list(FIXTURES.glob("*.json")))
    assert count
    assert main(["assess", "conformance", str(FIXTURES)]) == 0
    assert f"{count} DMPs assessed, none failing." in capsys.readouterr().out


def test_a_directory_with_no_dmp_fails(tmp_path, capsys):
    assert main(["assess", "conformance", str(tmp_path)]) == 1
    assert "No DMP found." in capsys.readouterr().err


def _document(tmp_path, document) -> str:
    path = tmp_path / "dmp.json"
    path.write_text(json.dumps(document))
    return str(path)


def test_a_failing_check_is_named(tmp_path, capsys):
    path = _document(
        tmp_path, {"dmp": {}, "metadata": {"rules": [{"rda_dcs": "1.0.0"}]}}
    )
    assert main(["assess", "conformance", path]) == 1
    err = capsys.readouterr().err
    assert "FAIL" in err and "- dmp.title:" in err
    assert "1 of 1 DMP failing." in err


@pytest.mark.parametrize(
    "document, problem",
    [
        ({"dmp": {}}, "has no metadata.rules"),
        ({"dmp": {}, "metadata": {"rules": [{"nope": "1.0.0"}]}}, "unknown standard"),
    ],
)
def test_a_document_that_names_no_usable_rules_fails(
    tmp_path, capsys, document, problem
):
    assert main(["assess", "conformance", _document(tmp_path, document)]) == 1
    assert problem in capsys.readouterr().err


def test_a_file_that_is_not_json_fails(tmp_path, capsys):
    path = tmp_path / "dmp.json"
    path.write_text("{")
    assert main(["assess", "conformance", str(path)]) == 1
    assert "is not valid JSON" in capsys.readouterr().err
