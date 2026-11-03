"""A DMP file read, the document and the pins its metadata.rules names, or the
reason it cannot be assessed."""

import json

import pytest

from madmp.assessment import read_document
from madmp.errors import DocumentError
from tests import FIXTURES


def test_a_fixture_reads_with_its_pins():
    path = FIXTURES / "rda_dcs-ostrails.json"
    document, pins = read_document(path)
    assert document == json.loads(path.read_text())
    assert pins == [{"rda_dcs": "1.0.0"}, {"ostrails": "1.0.0"}]


@pytest.mark.parametrize(
    "text, problem",
    [
        ("{", "is not valid JSON"),
        ("[]", "has no metadata.rules"),
        ('{"dmp": {}}', "has no metadata.rules"),
        ('{"dmp": {}, "metadata": {}}', "has no metadata.rules"),
    ],
)
def test_a_file_that_cannot_be_assessed_says_why(tmp_path, text, problem):
    path = tmp_path / "dmp.json"
    path.write_text(text)
    with pytest.raises(DocumentError, match=problem) as caught:
        read_document(path)
    assert caught.value.subject == str(path)


def test_a_file_that_is_not_there_cannot_be_read(tmp_path):
    with pytest.raises(DocumentError, match="cannot be read"):
        read_document(tmp_path / "absent.json")
