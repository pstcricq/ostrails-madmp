"""The madmp image built from this checkout: it migrates and syncs an empty
PostgreSQL, then serves the API. Every container shares the database
container's network namespace, where the database is 127.0.0.1.
"""

import json
import re
import subprocess
import time
import uuid

import pytest

from madmp.definitions import KINDS, files
from tests import ROOT
from tests.integration.conftest import PASSWORD, need_docker, postgres

TAG = "madmp:test"

HEALTH = (
    "import urllib.request; "
    "print(urllib.request.urlopen('http://127.0.0.1:8081/health').read().decode())"
)


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], check=False, capture_output=True, text=True
    )


def _on(db: str) -> list[str]:
    """The options that put a container next to the database ``db``."""
    return [
        "--network", f"container:{db}",
        "-e", "DMP_HOST=127.0.0.1",
        "-e", "DMP_PORT=5432",
        "-e", "DMP_DB=postgres",
        "-e", "DMP_USER=postgres",
        "-e", f"DMP_PASSWORD={PASSWORD}",
    ]  # fmt: skip


@pytest.fixture(scope="module")
def image():
    """The image built from this checkout, for this machine's platform."""
    need_docker("the madmp image")
    built = _docker("build", "-q", "-t", TAG, str(ROOT))
    if built.returncode != 0:
        pytest.fail(f"the image does not build:\n{built.stderr}")
    return TAG


@pytest.fixture(scope="module")
def db():
    """A postgres container of its own, its database empty."""
    with postgres() as name:
        yield name


@pytest.fixture(scope="module")
def prepared(image, db):
    """``madmp store migrate`` then ``madmp store sync``, run in the image."""
    return {
        step: _docker("run", "--rm", *_on(db), image, "madmp", "store", step)
        for step in ("migrate", "sync")
    }


def test_the_image_carries_its_licence_and_notice(image):
    shown = _docker("run", "--rm", image, "cat", "/app/LICENSE", "/app/NOTICE")
    assert shown.returncode == 0, shown.stderr
    assert "Apache License" in shown.stdout
    assert "dsw-deployment-example" in shown.stdout


def test_the_image_migrates_an_empty_database(prepared):
    migrate = prepared["migrate"]
    assert migrate.returncode == 0, migrate.stderr
    assert "001_init.sql" in migrate.stdout


def test_the_image_syncs_every_definition_of_the_checkout(prepared):
    sync = prepared["sync"]
    assert sync.returncode == 0, sync.stderr
    added = re.search(r"(\d+) definitions? added", sync.stdout)
    expected = sum(len(files(kind)) for kind in KINDS)
    assert added and int(added[1]) == expected, sync.stdout


def test_the_image_serves_the_api_with_its_own_command(image, db, prepared):
    name = f"madmp-test-api-{uuid.uuid4().hex[:8]}"
    tokens = ["TEMPLATE_WRITE_TOKEN=t", "DMP_READ_TOKEN=r", "DMP_WRITE_TOKEN=w"]
    try:
        started = _docker(
            "run", "-d", "--name", name, *_on(db),
            *(option for token in tokens for option in ("-e", token)),
            image,
        )  # fmt: skip
        assert started.returncode == 0, started.stderr
        # Up to a minute, polled from inside the API's container.
        for _ in range(60):
            answer = _docker("exec", name, "python", "-c", HEALTH)
            if answer.returncode == 0:
                break
            running = _docker("container", "inspect", "-f", "{{.State.Running}}", name)
            if running.stdout.strip() != "true":
                pytest.fail(f"the API exited:\n{_docker('logs', name).stderr}")
            time.sleep(1)
        else:
            pytest.fail(f"no answer on /health:\n{_docker('logs', name).stderr}")
        assert json.loads(answer.stdout) == {"status": "ok"}
    finally:
        _docker("rm", "-f", name)
