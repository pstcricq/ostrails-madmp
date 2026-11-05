"""A target's values, from a file or from the environment, against
.env.example, then the servers its stack runs, both scripts sourced by bash on
files written for each test."""

import re
import subprocess

import pytest

from tests import ROOT

# Both scripts sourced from the repository root, then what they export.
CHECK = """
cd "$1" && shift
source deploy/scripts/values.sh "${1:-}"
source deploy/scripts/servers.sh
echo "values $VALUES_SUMMARY"
echo "servers $SERVERS"
"""
EXAMPLE = (ROOT / ".env.example").read_text()
EMPTY = re.findall(r"^([A-Z][A-Z0-9_]*)=$", EXAMPLE, re.MULTILINE)
FIXED = re.findall(r"^([A-Z][A-Z0-9_]*)=.+$", EXAMPLE, re.MULTILINE)
SECRET = re.compile(r"_(USER|PASSWORD|SECRET|TOKEN|PRIVATE_KEY)$")

# A stack on this machine: its own servers, named by their services, a value
# for every other key.
STACK = {
    **{key: f"value-of-{key.lower()}" for key in EMPTY},
    "DMP_HOST": "dmp-postgres",
    "DMP_PORT": "5432",
    "DSW_DB_HOST": "dsw-postgres",
    "DSW_DB_PORT": "5432",
    "S3_URL": "http://minio:9000",
}


def _env_file(tmp_path, values=STACK, extra=""):
    path = tmp_path / ".env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()) + extra)
    return path


def _check(*args, env=None):
    """The check, in an environment holding PATH alone unless given more."""
    return subprocess.run(
        ["bash", "-c", CHECK, "check", str(ROOT), *map(str, args)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(env or {})},
        check=False,
    )


# A file


def test_a_complete_file_passes_and_says_what_it_read(tmp_path):
    checked = _check(_env_file(tmp_path))
    assert checked.returncode == 0, checked.stderr
    assert "Configuration (.env.example, then " in checked.stdout
    assert re.search(
        rf"^values {len(EMPTY) + len(FIXED)} keys: {len(FIXED)} fixed",
        checked.stdout,
        re.MULTILINE,
    )
    assert "\nservers dmp-database dsw-database storage\n" in checked.stdout


def test_a_secret_is_printed_as_set_and_a_variable_in_full(tmp_path):
    out = _check(_env_file(tmp_path)).stdout
    for key in EMPTY:
        shown = re.search(rf"^    {key} +(.*)$", out, re.MULTILINE)[1]
        assert shown == ("set" if SECRET.search(key) else STACK[key])


def test_every_empty_key_left_out_is_named(tmp_path):
    values = {k: v for k, v in STACK.items() if k not in ("DMP_DB", "DSW_USER")}
    checked = _check(_env_file(tmp_path, values))
    assert checked.returncode == 1
    assert "empty or absent in" in checked.stderr
    assert "DMP_DB" in checked.stderr and "DSW_USER" in checked.stderr


@pytest.mark.parametrize(
    "extra, problem",
    [
        ("DMP_DB=again\n", "keys given twice: DMP_DB"),
        ("DMP_DB=x\r\n", "lines ending in CR"),
        ("not a key\n", "lines that are not KEY=value"),
        ("UNKNOWN=x\n", "not in .env.example"),
        (f"{FIXED[0]}=x\n", "fixed by .env.example"),
    ],
)
def test_a_wrong_line_is_refused(tmp_path, extra, problem):
    checked = _check(_env_file(tmp_path, extra=extra))
    assert checked.returncode == 1
    assert problem in checked.stderr


@pytest.mark.parametrize(
    "value, problem",
    [
        (" spaced", "values starting or ending with a space"),
        ("'quoted'", "values between single quotes"),
    ],
)
def test_a_value_is_written_as_it_is_meant(tmp_path, value, problem):
    checked = _check(_env_file(tmp_path, {**STACK, "DMP_DB": value}))
    assert checked.returncode == 1
    assert problem in checked.stderr


def test_a_value_between_double_quotes_spans_several_lines(tmp_path):
    values = {**STACK, "DMP_PASSWORD": '"first\nsecond"'}
    assert _check(_env_file(tmp_path, values)).returncode == 0


def test_a_wrong_line_is_named_by_its_number_and_never_shown(tmp_path):
    checked = _check(_env_file(tmp_path, extra="secret value here\n"))
    assert "secret value here" not in checked.stdout + checked.stderr


# A target's own example, beside its .env


def _target_example(tmp_path, text="# --- Target ---\nTARGET_KEY=\n"):
    (tmp_path / ".env.example").write_text(text)


def test_a_target_s_own_example_adds_its_keys(tmp_path):
    _target_example(tmp_path)
    missing = _check(_env_file(tmp_path))
    assert missing.returncode == 1
    assert "TARGET_KEY" in missing.stderr
    checked = _check(_env_file(tmp_path, {**STACK, "TARGET_KEY": "x"}))
    assert checked.returncode == 0, checked.stderr
    assert f".env.example and {tmp_path}/.env.example, then" in checked.stdout


def test_the_environment_fills_a_target_s_own_keys_too(tmp_path):
    _target_example(tmp_path)
    checked = _check(tmp_path / ".env", env={**STACK, "TARGET_KEY": "x"})
    assert checked.returncode == 0, checked.stderr


def test_a_key_in_both_examples_is_refused(tmp_path):
    _target_example(tmp_path, f"{EMPTY[0]}=\n")
    checked = _check(_env_file(tmp_path))
    assert checked.returncode == 1
    assert f"keys in both .env.example and {tmp_path}/.env.example: " in (
        checked.stderr
    )


# The environment


def test_without_a_file_the_environment_is_read(tmp_path):
    checked = _check(env=STACK)
    assert checked.returncode == 0, checked.stderr
    assert "Configuration (.env.example, then environment)" in checked.stdout


def test_a_fixed_key_in_the_environment_is_refused():
    checked = _check(env={**STACK, FIXED[0]: "x"})
    assert checked.returncode == 1
    assert "unset in the environment" in checked.stderr


# The servers


def test_the_addresses_of_the_target_leave_the_stack_none(tmp_path):
    values = {
        **STACK,
        "DMP_HOST": "db.example.org",
        "DSW_DB_HOST": "db.example.org",
        "S3_URL": "https://s3.example.org",
    }
    checked = _check(_env_file(tmp_path, values))
    assert checked.returncode == 0, checked.stderr
    assert "\nservers \n" in checked.stdout


@pytest.mark.parametrize(
    "values, servers",
    [
        ({"DMP_HOST": "db.example.org"}, "dsw-database storage"),
        ({"DSW_DB_HOST": "db.example.org"}, "dmp-database storage"),
        ({"S3_URL": "https://minio.example.org"}, "dmp-database dsw-database"),
        ({"DMP_PORT": "6543"}, "dmp-database dsw-database storage"),
    ],
)
def test_each_server_is_read_from_its_own_address(tmp_path, values, servers):
    checked = _check(_env_file(tmp_path, {**STACK, **values}))
    assert checked.returncode == 0, checked.stderr
    assert f"\nservers {servers}\n" in checked.stdout


@pytest.mark.parametrize("key", ["DMP_PORT", "DSW_DB_PORT"])
def test_a_port_that_is_not_a_number_is_refused(tmp_path, key):
    checked = _check(_env_file(tmp_path, {**STACK, key: "x"}))
    assert checked.returncode == 1
    assert f"{key} is x, not a port number" in checked.stderr
