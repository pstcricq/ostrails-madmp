"""A DMP file read for its assessment: the document, and the pins its
``metadata.rules`` names."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from madmp.errors import DocumentError


def read_document(path: str | Path) -> tuple[Any, list[dict[str, str]]]:
    """One DMP file, parsed, and the pins its ``metadata.rules`` names.

    Raises ``DocumentError`` for a file that cannot be read, that is not JSON,
    or that has no ``metadata.rules``.
    """
    path = Path(path)
    try:
        document = json.loads(path.read_text())
    except OSError as err:
        raise DocumentError([f"cannot be read, {err.strerror or err}"], path) from err
    except ValueError as err:
        raise DocumentError([f"is not valid JSON, {err}"], path) from err
    metadata = document.get("metadata") if isinstance(document, dict) else None
    if not isinstance(metadata, dict) or "rules" not in metadata:
        raise DocumentError(
            ["has no metadata.rules, the rules versions it was built from."], path
        )
    return document, metadata["rules"]
