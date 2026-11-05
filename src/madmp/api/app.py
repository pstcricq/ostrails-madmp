"""The DMP API's FastAPI routes over the DMP database, each behind its token.
The tokens and the database are read once at startup, and the schema checked
before anything is served.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse

from madmp.api.service import (
    handle_new_production,
    handle_production_version,
    handle_template,
)
from madmp.errors import (
    DmpNotFoundError,
    Refused,
    StoreError,
    VersionConflictError,
)
from madmp.store import (
    Database,
    Version,
    get_version,
    latest_version,
    list_versions,
    pending,
)
from madmp.store.database import ENVIRONMENT as DATABASE

TOKENS = ("TEMPLATE_WRITE_TOKEN", "DMP_READ_TOKEN", "DMP_WRITE_TOKEN")

# A DMP key, in the pattern the database writes it: anything else is unknown.
_KEY = re.compile(r"^[a-z0-9-]{1,160}$")

# The largest body read. Larger is refused with 413 before it is held in
# memory whole.
MAX_BODY = 5 * 1024 * 1024

# One line per write: the project or the DMP, what happened. Never the
# document.
log = logging.getLogger("madmp.api")


@dataclass(frozen=True)
class Settings:
    """What the API serves with, built once at startup and never rebuilt.
    The tokens are kept out of ``repr``, as the database password is."""

    template_token: str = field(repr=False)
    read_token: str = field(repr=False)
    write_token: str = field(repr=False)
    database: Database


def from_environment() -> Settings:
    """The variables, or one error naming every one of them that is unset.
    Missing and empty are the same failure."""
    missing = [name for name in (*TOKENS, *DATABASE) if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"not set: {', '.join(missing)}")
    try:
        database = Database.from_environment()
    except StoreError as err:
        raise RuntimeError(str(err)) from err
    return Settings(
        template_token=os.environ["TEMPLATE_WRITE_TOKEN"],
        read_token=os.environ["DMP_READ_TOKEN"],
        write_token=os.environ["DMP_WRITE_TOKEN"],
        database=database,
    )


def check_schema(settings: Settings) -> None:
    """Refuse a DMP database that lacks a migration of this version."""
    with settings.database.connect() as conn:
        missing = pending(conn)
    if missing:
        raise RuntimeError(
            f"the DMP database lacks {', '.join(missing)}: run `madmp store migrate`"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Read the environment and check the DMP database's schema before
    serving anything: an API missing a value or a migration refuses to start,
    its log naming what is missing."""
    # uvicorn configures its own loggers only, this one reaches the same
    # stream through the root logger, at INFO.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    log.setLevel(logging.INFO)
    app.state.settings = app.state.build()
    app.state.prepare(app.state.settings)
    log.info("DMP database up to date")
    yield


app = FastAPI(title="maDMP DMP API", lifespan=lifespan)
# What builds the settings and what checks the database, replaceable before
# the API is served.
app.state.build = from_environment
app.state.prepare = check_schema


@app.exception_handler(HTTPException)
async def refuse_in_plain_text(request: Request, exc: HTTPException) -> Response:
    """Every refusal as the text it says and nothing around it, its lines
    kept."""
    return PlainTextResponse(
        str(exc.detail), status_code=exc.status_code, headers=exc.headers
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Answers only once the variables are in place and the database is up to
    date, see lifespan."""
    return {"status": "ok"}


def _bearer(request: Request, token: str) -> bool:
    """Whether the request carries ``Authorization: Bearer <token>``,
    compared in constant time, on bytes."""
    presented = request.headers.get("authorization", "").encode()
    return hmac.compare_digest(presented, f"Bearer {token}".encode())


def _settings(request: Request) -> Settings:
    return request.app.state.settings


async def _json_body(request: Request) -> Any:
    """The body, a JSON document no larger than MAX_BODY."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY:
        raise HTTPException(413, f"body larger than {MAX_BODY} bytes")
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise HTTPException(413, f"body larger than {MAX_BODY} bytes")
    try:
        return json.loads(raw)
    except ValueError as e:
        raise HTTPException(400, "body is not valid JSON") from e


def _refused(where: str, err: Exception) -> HTTPException:
    """The answer to a write that raised, logged on one line: 400 a request
    that cannot be taken, 422 a document that does not hold up or a write the
    database cannot take, 404 a DMP that is not there, 409 a version written
    on one that is no longer the latest, 503 a database that could not be
    reached."""
    if isinstance(err, Refused):
        status, detail = err.status, str(err)
    elif isinstance(err, DmpNotFoundError):
        status, detail = 404, str(err)
    elif isinstance(err, VersionConflictError):
        status, detail = 409, str(err)
    elif isinstance(err, StoreError):
        status, detail = 422, str(err)
    else:
        log.error("%s: refused 503, the DMP database is unreachable", where)
        return HTTPException(
            503, "the DMP database is unreachable, nothing was written. Send it again."
        )
    log.warning("%s: refused %s, %s", where, status, type(err).__name__)
    return HTTPException(status, detail)


# What each write can be refused with, beside an unreachable database.
_REFUSALS = (Refused, StoreError, psycopg.OperationalError)


async def _write(
    where: str, handle: Callable[..., dict[str, Any]], *args: Any
) -> JSONResponse:
    """Run a write in a thread, and answer 201 when it wrote a version, 200
    when the DMP already held it."""
    try:
        result = await run_in_threadpool(handle, *args)
    except _REFUSALS as e:
        raise _refused(where, e) from e
    log.info(
        "%s: %s %s version %s",
        where,
        result["action"],
        result["key"],
        result["version"],
    )
    status = 200 if result["action"] == "unchanged" else 201
    return JSONResponse(result, status_code=status)


# Writing


@app.post("/templates")
async def write_template(request: Request) -> JSONResponse:
    settings = _settings(request)
    if not _bearer(request, settings.template_token):
        raise HTTPException(401, "invalid or missing template token")
    body = await _json_body(request)
    return await _write("templates", handle_template, body, settings.database)


def _writer(request: Request) -> Database:
    """The database to write a production DMP to, once the write token is
    checked."""
    settings = _settings(request)
    if not _bearer(request, settings.write_token):
        raise HTTPException(401, "invalid or missing write token")
    return settings.database


@app.post("/productions")
async def new_production(request: Request) -> JSONResponse:
    database = _writer(request)
    body = await _json_body(request)
    return await _write("productions", handle_new_production, body, database)


@app.post("/productions/{key}/versions")
async def production_version(key: str, request: Request) -> JSONResponse:
    database = _writer(request)
    if not _KEY.match(key):
        raise HTTPException(404, f"no production DMP {key!r}")
    body = await _json_body(request)
    return await _write(key, handle_production_version, key, body, database)


# Reading. Plain ``def``: FastAPI runs them in a thread.


def _reader(request: Request, key: str) -> Database:
    """The database to read from, once the read or the write token is checked
    and the key is one the database could hold. The write token reads
    too."""
    settings = _settings(request)
    if not (
        _bearer(request, settings.read_token) or _bearer(request, settings.write_token)
    ):
        raise HTTPException(401, "invalid or missing read token")
    if not _KEY.match(key):
        raise HTTPException(404, f"no DMP {key!r}")
    return settings.database


def _read(database: Database, read: Callable[..., Any], *args: Any) -> Any:
    """``read(conn, *args)`` on a new connection, 503 when the database cannot
    be reached."""
    try:
        with database.connect() as conn:
            return read(conn, *args)
    except psycopg.OperationalError as e:
        raise HTTPException(503, "the DMP database is unreachable") from e


def _version_body(version: Version) -> JSONResponse:
    """One version: the DMP under ``dmp`` and its metadata under ``metadata``,
    as it was written, beside its assessment and where it came from."""
    body = asdict(version)
    return JSONResponse(
        {
            "key": body["key"],
            "version": body["version"],
            "created_at": body["created_at"].isoformat(),
            "source": body["source"],
            "project_version": body["project_version"],
            "from_template_version": body["from_template_version"],
            "dmp": body["document"],
            "metadata": body["metadata"],
            "assessment": body["assessment"],
        }
    )


@app.get("/dmps/{key}")
def read_latest(key: str, request: Request) -> JSONResponse:
    version = _read(_reader(request, key), latest_version, key)
    if version is None:
        raise HTTPException(404, f"no DMP {key!r}")
    return _version_body(version)


@app.get("/dmps/{key}/versions")
def read_versions(key: str, request: Request) -> JSONResponse:
    versions = _read(_reader(request, key), list_versions, key)
    if not versions:
        raise HTTPException(404, f"no DMP {key!r}")
    listed = [{**v, "created_at": v["created_at"].isoformat()} for v in versions]
    return JSONResponse({"key": key, "versions": listed})


@app.get("/dmps/{key}/versions/{number}")
def read_version(key: str, number: int, request: Request) -> JSONResponse:
    version = _read(_reader(request, key), get_version, key, number)
    if version is None:
        raise HTTPException(404, f"no version {number} of {key!r}")
    return _version_body(version)
