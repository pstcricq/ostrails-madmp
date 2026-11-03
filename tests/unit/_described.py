"""``described()`` adds a ``_description`` to every field of a base standard
that has none. An extension is left as written."""

from typing import Any

TEST_DESCRIPTION = "A test field."


def _fill(tree: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in tree.items():
        if key.startswith("_") or not isinstance(value, dict):
            out[key] = value
        else:
            out[key] = {"_description": TEST_DESCRIPTION, **_fill(value)}
    return out


def described(doc: dict[str, Any]) -> dict[str, Any]:
    """``doc`` with a ``_description`` on every field of a base standard."""
    if "extends" in doc or not isinstance(doc.get("dmp"), dict):
        return doc
    return {**doc, "dmp": _fill(doc["dmp"])}
