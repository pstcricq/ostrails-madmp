"""A PostgreSQL for the tests of this directory: a postgres container of
DMP_POSTGRES_VERSION, started once per session, on the docker daemon of
DOCKER_HOST; without docker the tests are skipped, under CI they fail. ``conn``
and ``database`` give each test an empty database, migrated and synced.
"""

import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from madmp.store import Database, migrate, sync
from tests import ROOT

IMAGE = (
    "postgres:"
    + re.findall(
        r"^DMP_POSTGRES_VERSION=(.+)$",
        (ROOT / ".env.example").read_text(),
        re.MULTILINE,
    )[0]
)
# Where the docker daemon publishes ports: this machine, or the host of a
# tcp:// DOCKER_HOST.
DAEMON = urlparse(os.environ.get("DOCKER_HOST", "")).hostname or "127.0.0.1"
PASSWORD = "test"


def _wait(conninfo: str) -> None:
    for _ in range(60):
        try:
            psycopg.connect(conninfo, connect_timeout=2).close()
            return
        except psycopg.OperationalError:
            time.sleep(0.5)
    pytest.fail(f"no PostgreSQL answering at {conninfo}")


def need_docker(what: str) -> None:
    """Skip the test when docker is missing, or fail it under CI."""
    if shutil.which("docker") is None:
        if os.environ.get("CI"):
            pytest.fail(f"no docker under CI for {what}")
        pytest.skip(f"no docker for {what}")


@contextmanager
def postgres() -> Generator[str, None, None]:
    """A postgres container, its port 5432 published on DAEMON (on the
    loopback when that is this machine), ready once entered and removed on
    exit: its name."""
    name = f"madmp-test-{uuid.uuid4().hex[:8]}"
    publish = "127.0.0.1::5432" if DAEMON == "127.0.0.1" else "5432"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-p", publish]
        + ["-e", f"POSTGRES_PASSWORD={PASSWORD}", IMAGE],
        check=True,
        capture_output=True,
    )
    try:
        # -h 127.0.0.1: while it initialises, the server listens on its socket
        # alone.
        ready = ["docker", "exec", name, "pg_isready", "-q", "-h", "127.0.0.1"]
        for _ in range(60):
            if subprocess.run(ready, check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            pytest.fail(f"no PostgreSQL answering in {name}")
        yield name
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)


@pytest.fixture(scope="session")
def server():
    """A libpq connection string to a server the tests own."""
    need_docker("a PostgreSQL")
    with postgres() as name:
        published = subprocess.run(
            ["docker", "port", name, "5432/tcp"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        port = published.split(":")[-1].strip()
        conninfo = (
            f"host={DAEMON} port={port} dbname=postgres user=postgres "
            f"password={PASSWORD}"
        )
        _wait(conninfo)
        yield conninfo


@pytest.fixture()
def conn(server):
    """A connection to an empty, migrated database, holding the definitions of
    the repository."""
    with psycopg.connect(server, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        migrate(conn)
        sync(conn)
        yield conn


@pytest.fixture()
def database(server, conn):
    """The same database, as ``madmp store`` is given it."""
    parts = conninfo_to_dict(server)
    return Database(
        host=parts["host"],
        port=int(parts["port"]),
        name=parts["dbname"],
        user=parts["user"],
        password=parts["password"],
    )
