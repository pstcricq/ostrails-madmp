"""Where the DMP database is, and how to open a connection to it."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import psycopg

from madmp.errors import StoreError

# Seconds a connection attempt waits for the server before giving up.
CONNECT_TIMEOUT = 10

# The variables that name the database, in the order Database takes them.
ENVIRONMENT = ("DMP_HOST", "DMP_PORT", "DMP_DB", "DMP_USER", "DMP_PASSWORD")


@dataclass(frozen=True)
class Database:
    """The server, the database and the account the DMPs are written with.

    ``password`` is kept out of ``repr``.
    """

    host: str
    port: int
    name: str
    user: str
    password: str = field(repr=False)

    def connect(self) -> psycopg.Connection:
        """A new connection. The caller closes it, ``with`` does."""
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.name,
            user=self.user,
            password=self.password,
            connect_timeout=CONNECT_TIMEOUT,
        )

    @classmethod
    def from_environment(cls) -> Database:
        """The database the variables name, or one error naming every one of
        them that is unset, and a port that is not a number.

        Missing and empty are the same failure.
        """
        values = [os.environ.get(name, "") for name in ENVIRONMENT]
        missing = [
            name for name, value in zip(ENVIRONMENT, values, strict=True) if not value
        ]
        if missing:
            raise StoreError(f"not set: {', '.join(missing)}")
        host, port, name, user, password = values
        if not port.isdigit():
            raise StoreError(f"DMP_PORT is {port!r}, not a port number")
        return cls(host, int(port), name, user, password)
