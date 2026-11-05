"""A DS Wizard instance and its account, from DSW_API_URL, DSW_USER and
DSW_PASSWORD: ``login()`` opens a ``DswClient`` over the standard library, a
refused or unreachable call raising ``DswError``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any

from madmp.errors import DswError, PublishError

# The page size a listing is read with.
LISTING_PAGE_SIZE = 1000

# What each value says, for the message that names a missing one.
_VALUES = {
    "DSW_API_URL": "says which DSW instance to reach",
    "DSW_USER": "is the email of the account the API is called as",
    "DSW_PASSWORD": "is its password",
}


@dataclass(frozen=True)
class Instance:
    """Which DSW instance, and the account its API is called as. The password
    is kept out of ``repr``."""

    api_url: str
    user: str
    password: str = field(repr=False)


def from_environment() -> Instance:
    """The instance and the account, or every missing name at once."""
    values = {name: os.environ.get(name) for name in _VALUES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise PublishError(
            [f"{name} is not set, it {_VALUES[name]}." for name in missing]
        )
    return Instance(values["DSW_API_URL"], values["DSW_USER"], values["DSW_PASSWORD"])


class DswClient:
    """The calls of the DSW API, standard library only."""

    def __init__(self, api_url: str, token: str):
        self.api_url = api_url.rstrip("/")
        self.token = token

    def _send(self, request: urllib.request.Request, what: str) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            raise DswError(e.code, f"{what}: {e.read().decode()}") from e
        # After HTTPError, an OSError too: what never became a response, a
        # name that does not resolve, a refused connection, a timeout.
        except OSError as e:
            raise DswError(None, f"{what}: {e}") from e

    def _request(self, method: str, path: str, payload: Any | None = None) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            self.api_url + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers=headers,
            method=method,
        )
        return self._send(request, f"{method} {path}")

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: Any) -> Any:
        return self._request("POST", path, payload)

    def put(self, path: str, payload: Any) -> Any:
        return self._request("PUT", path, payload)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def post_bundle(
        self, path: str, filename: str, content_type: str, data: bytes
    ) -> dict[str, Any]:
        """POST a file to a bundle endpoint, as a multipart upload."""
        boundary = "----FormBoundary" + uuid.uuid4().hex[:16]
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )
        request = urllib.request.Request(
            self.api_url + path,
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        return self._send(request, f"POST {path}")

    def download(self, path: str) -> bytes:
        """The file behind a link the API answers ``path`` with,
        ``{"url": ...}``, fetched without the token: the link carries its own
        signature. A message names the link without its query, the
        signature."""
        link = self.get(path)["url"]
        where = f"GET {link.split('?', 1)[0]}"
        try:
            with urllib.request.urlopen(link, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            raise DswError(e.code, where) from e
        except OSError as e:
            raise DswError(None, f"{where}: {e}") from e

    def list_all(self, endpoint: str, collection: str) -> list[dict[str, Any]]:
        """Every item of a paginated listing, page after page."""
        separator = "&" if "?" in endpoint else "?"
        first = self.get(f"{endpoint}{separator}size={LISTING_PAGE_SIZE}")
        items = list(first["_embedded"][collection])
        total_pages = (first.get("page") or {}).get("totalPages", 1)
        for number in range(1, total_pages):
            page = self.get(
                f"{endpoint}{separator}size={LISTING_PAGE_SIZE}&page={number}"
            )
            items.extend(page["_embedded"][collection])
        return items


def login(instance: Instance) -> DswClient:
    """A client logged in as the instance's account. A refused login is a
    ``DswError`` of status 400."""
    token = DswClient(instance.api_url, "").post(
        "/tokens", {"email": instance.user, "password": instance.password}
    )
    return DswClient(instance.api_url, token["token"])
