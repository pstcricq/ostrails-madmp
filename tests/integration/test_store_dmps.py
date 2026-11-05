"""A DMP's versions written and read back, the template's and the production
ones', on the PostgreSQL of the tests, every test starting with the definitions
of the repository synced."""

import json
import threading

import psycopg
import pytest

from madmp.errors import DmpNotFoundError, StoreError, VersionConflictError
from madmp.store import (
    Stored,
    add_production_version,
    create_production,
    get_version,
    latest_version,
    list_versions,
    project_pins,
    write_template,
)
from tests import FIXTURES
from tests.integration.test_store_sync import glider_at

EXAMPLE = FIXTURES / "rda_dcs-ostrails.json"
DOCUMENT = json.loads(EXAMPLE.read_text())["dmp"]
ASSESSMENT = {"verdict": "pass", "summary": {"fail": 0}}
METADATA = {
    "project": "glider",
    "project_version": "1.0.0",
    "rules": [{"rda_dcs": "1.0.0"}, {"ostrails": "1.0.0"}],
}
TEMPLATE = "socib-glider-template"
PRODUCTION = "socib-glider-0001"


def _template(conn, title="title", project_version="1.0.0", source="writer"):
    return write_template(
        conn,
        project="glider",
        project_version=project_version,
        document={**DOCUMENT, "title": title},
        assessment=ASSESSMENT,
        source=source,
    )


def _production(conn, title="mission", template_version=1):
    return create_production(
        conn,
        project="glider",
        from_template_version=template_version,
        document={**DOCUMENT, "title": title},
        assessment=ASSESSMENT,
        source="client",
    )


def _version(conn, title, based_on, template_version=1):
    return add_production_version(
        conn,
        key=PRODUCTION,
        based_on=based_on,
        from_template_version=template_version,
        document={**DOCUMENT, "title": title},
        assessment=ASSESSMENT,
        source="client",
    )


# The template


def test_a_first_write_is_version_1(conn):
    assert _template(conn) == Stored(TEMPLATE, 1, "created")


def test_the_key_comes_from_the_project_version_and_goes_into_dmp_id(conn):
    _template(conn)
    assert latest_version(conn, TEMPLATE).document["dmp_id"] == {
        "identifier": TEMPLATE,
        "type": "other",
    }


def test_the_caller_s_document_is_left_as_it_was(conn):
    document = dict(DOCUMENT)
    write_template(
        conn,
        project="glider",
        project_version="1.0.0",
        document=document,
        assessment=ASSESSMENT,
        source="writer",
    )
    assert document == DOCUMENT


def test_the_same_content_adds_nothing(conn):
    _template(conn)
    assert _template(conn) == Stored(TEMPLATE, 1, "unchanged")
    assert len(list_versions(conn, TEMPLATE)) == 1


def test_the_order_of_the_keys_does_not_count(conn):
    _template(conn)
    reordered = dict(reversed({**DOCUMENT, "title": "title"}.items()))
    stored = write_template(
        conn,
        project="glider",
        project_version="1.0.0",
        document=reordered,
        assessment=ASSESSMENT,
        source="writer",
    )
    assert stored.action == "unchanged"


def test_a_changed_content_adds_the_next_version(conn):
    _template(conn)
    assert _template(conn, title="renamed") == Stored(TEMPLATE, 2, "updated")
    assert latest_version(conn, TEMPLATE).document["title"] == "renamed"
    assert get_version(conn, TEMPLATE, 1).document["title"] == "title"


def test_a_new_project_version_alone_is_a_new_version(conn, tmp_path):
    _template(conn)
    glider_at(conn, tmp_path, "1.1.0")
    assert _template(conn, project_version="1.1.0").version == 2


def test_a_project_version_never_synced_is_refused(conn):
    with pytest.raises(StoreError, match="never synced"):
        _template(conn, project_version="9.9.9")


def test_where_a_version_comes_from_is_recorded_as_given(conn):
    """One template per project, each version saying what wrote it."""
    _template(conn)
    _template(conn, title="from the other one", source="another-writer")
    assert [v["source"] for v in list_versions(conn, TEMPLATE)] == [
        "writer",
        "another-writer",
    ]


def test_a_failed_write_leaves_nothing_behind(conn):
    """One transaction: the template's row goes with the version the schema
    refused."""
    with pytest.raises(psycopg.errors.CheckViolation):
        _template(conn, source="Not a name")
    assert conn.execute("SELECT count(*) FROM dmps").fetchone()[0] == 0


def test_two_writes_at_once_take_two_numbers(server, conn):
    """The second write waits for the first and takes the next number."""
    barrier = threading.Barrier(2)
    results = []

    def write(title):
        with psycopg.connect(server, autocommit=True) as own:
            barrier.wait()
            results.append(_template(own, title=title))

    _template(conn)
    threads = [threading.Thread(target=write, args=(t,)) for t in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r.version for r in results) == [2, 3]


# Production DMPs


def test_a_production_is_filled_from_a_template_version(conn):
    _template(conn)
    assert _production(conn) == Stored(PRODUCTION, 1, "created")
    stored = latest_version(conn, PRODUCTION)
    assert stored.document["dmp_id"] == {"identifier": PRODUCTION, "type": "other"}
    assert stored.from_template_version == 1
    assert stored.project_version == "1.0.0"


def test_a_production_takes_the_project_version_of_its_template_version(conn, tmp_path):
    _template(conn)
    _production(conn)
    glider_at(conn, tmp_path, "1.1.0")
    _template(conn, project_version="1.1.0")
    _version(conn, "moved on", based_on=1, template_version=2)
    assert latest_version(conn, PRODUCTION).project_version == "1.1.0"


def test_a_production_needs_a_stored_template_version(conn):
    with pytest.raises(StoreError, match="has no version 1"):
        _production(conn)
    _template(conn)
    with pytest.raises(StoreError, match="has no version 2"):
        _production(conn, template_version=2)


def test_a_project_never_synced_has_no_production(conn):
    with pytest.raises(StoreError, match="never synced"):
        create_production(
            conn,
            project="nothing",
            from_template_version=1,
            document=DOCUMENT,
            assessment=ASSESSMENT,
            source="client",
        )


def test_numbers_only_go_up(conn):
    _template(conn)
    assert [_production(conn, title=t).key for t in ("a", "b")] == [
        PRODUCTION,
        "socib-glider-0002",
    ]


def test_two_productions_created_at_once_take_two_numbers(server, conn):
    """The project's row is locked while a number is taken."""
    _template(conn)
    barrier = threading.Barrier(2)
    keys = []

    def create(title):
        with psycopg.connect(server, autocommit=True) as own:
            barrier.wait()
            keys.append(_production(own, title=title).key)

    threads = [threading.Thread(target=create, args=(t,)) for t in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(keys) == [PRODUCTION, "socib-glider-0002"]
    assert conn.execute("SELECT next_number FROM projects").fetchone()[0] == 3


def test_a_production_version_based_on_the_latest_is_the_next_one(conn):
    _template(conn)
    _production(conn)
    assert _version(conn, "changed", based_on=1) == Stored(PRODUCTION, 2, "updated")


def test_a_production_version_is_never_based_on_a_stale_one(conn):
    _template(conn)
    _production(conn)
    _version(conn, "A", based_on=1)
    with pytest.raises(VersionConflictError, match="based on version 1"):
        _version(conn, "B", based_on=1)


def test_the_same_production_content_adds_nothing(conn):
    _template(conn)
    _production(conn)
    assert _version(conn, "mission", based_on=1) == Stored(PRODUCTION, 1, "unchanged")


@pytest.mark.parametrize("key", [TEMPLATE, "socib-glider-9999"])
def test_a_production_version_goes_to_a_production_dmp(conn, key):
    _template(conn)
    with pytest.raises(DmpNotFoundError):
        add_production_version(
            conn,
            key=key,
            based_on=1,
            from_template_version=1,
            document=DOCUMENT,
            assessment=ASSESSMENT,
            source="client",
        )


# Reading


def test_an_unknown_dmp_reads_as_none(conn):
    assert latest_version(conn, TEMPLATE) is None
    assert get_version(conn, TEMPLATE, 1) is None
    assert list_versions(conn, TEMPLATE) == []


def test_a_version_is_read_back_whole(conn):
    _template(conn)
    stored = get_version(conn, TEMPLATE, 1)
    assert stored.metadata == METADATA
    assert stored.assessment == ASSESSMENT
    assert stored.source == "writer"
    assert stored.from_template_version is None


def test_the_list_says_when_from_where_and_the_verdict(conn):
    _template(conn)
    (row,) = list_versions(conn, TEMPLATE)
    assert row["version"] == 1
    assert row["source"] == "writer"
    assert row["verdict"] == "pass"
    assert row["created_at"] is not None


def test_the_pins_of_a_project_version(conn):
    assert project_pins(conn, "glider", "1.0.0") == METADATA["rules"]
    assert project_pins(conn, "glider", "9.9.9") is None
