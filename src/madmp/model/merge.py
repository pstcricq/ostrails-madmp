"""Rules files merged into one ``Model``, the base standard first. An extension
may only tighten what the base defines, each judged against the base, so the
order of the pins does not matter; every conflict across the files is
collected into one ``RulesConflictError``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from madmp.definitions import RULES, field_children, load
from madmp.errors import RulesConflictError, RulesSetError

_SHAPE = {"1": "single", "0..1": "single", "1..n": "list", "0..n": "list"}
# The types a pattern alone decides, the codes of three ISO standards: what
# Field.pattern answers.
_CODE_PATTERNS = {
    "language": r"^[a-z]{3}$",  # ISO 639-3
    "currency": r"^[A-Z]{3}$",  # ISO 4217
    "country_code": r"^[A-Z]{2}$",  # ISO 3166-1 alpha-2
}
_REQUIRED = {"1", "1..n"}
# Metadata key -> the aspect name a Tightening records it under.
_VOCABULARY_ASPECTS = {
    "_allowed_values": "allowed_values",
    "_suggested_values": "suggested_values",
}
# Descriptive metadata: an extension may supply what the base left out (a
# chapter description), or repeat it, saying something else is a conflict.
_DESCRIPTIVE_KEYS = ("_description", "_chapter_description")


def _is_list(cardinality: str) -> bool:
    """Whether a cardinality means the field holds a JSON array."""
    return _SHAPE[cardinality] == "list"


@dataclass(frozen=True)
class Tightening:
    """One restriction an extension imposed on a field the base standard
    left weaker: the aspect it tightened, and the before/after values."""

    standard: str
    aspect: Literal["cardinality", "allowed_values", "suggested_values"]
    before: Any
    after: Any


@dataclass(frozen=True)
class Field:
    """One merged DMP field: its constraints, its provenance, its children."""

    name: str
    path: tuple[str, ...]  # from the dmp root, e.g. ("dataset", "title")
    dotted_path: str  # e.g. "dmp.dataset[].title"
    cardinality: str
    type: str
    origin: str  # the standard that introduced this field
    description: str | None = None
    chapter_description: str | None = None
    allowed_values: tuple[str, ...] | None = None
    suggested_values: tuple[str, ...] | None = None
    tightenings: tuple[Tightening, ...] = ()
    children: tuple[Field, ...] = ()

    @property
    def is_list(self) -> bool:
        return _is_list(self.cardinality)

    @property
    def is_required(self) -> bool:
        return self.cardinality in _REQUIRED

    @property
    def pattern(self) -> str | None:
        """The pattern a value of this field matches where its type alone
        decides it, the codes of three ISO standards, ``None`` otherwise."""
        return _CODE_PATTERNS.get(self.type)

    def walk(self) -> Iterator[Field]:
        """This field, then every descendant, depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Source:
    """One merged rules file: its standard and version as declared, and how a
    reader names it, its ``name`` and its ``references``, each a
    ``(label, url)`` pair."""

    standard: str
    version: str
    name: str
    references: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Model:
    """The merged rules of every standard: the top-level ``dmp`` fields, and
    the rules files merged into them, base first."""

    fields: tuple[Field, ...]
    sources: tuple[Source, ...]

    @property
    def base_standard(self) -> str:
        return self.sources[0].standard

    @property
    def extension_standards(self) -> tuple[str, ...]:
        return tuple(source.standard for source in self.sources[1:])

    @property
    def standards(self) -> tuple[str, ...]:
        return tuple(source.standard for source in self.sources)

    @property
    def standard_versions(self) -> tuple[tuple[str, str], ...]:
        """(standard, version), base first, each file's declared version."""
        return tuple((source.standard, source.version) for source in self.sources)

    def walk(self) -> Iterator[Field]:
        """Every field of the merged tree, depth-first."""
        for field in self.fields:
            yield from field.walk()


# Merging (over mutable interim nodes, frozen into Field at the end)


@dataclass
class _Node:
    """A field mid-merge: tightening rewrites its metadata in place and
    appends to its record."""

    # The combined state, what every standard merged so far amounts to.
    meta: dict[str, Any]
    # The declaration every extension is judged against, the introducing
    # standard's own, frozen. Not the same thing as ``meta``.
    base_meta: dict[str, Any]
    origin: str
    # Per metadata key, the standard that wrote the value ``meta`` currently
    # holds. ``origin`` answers a different question, who introduced the
    # field. Kept for every key, the descriptions included.
    meta_origin: dict[str, str]
    tightenings: list[Tightening]
    children: dict[str, _Node]


def _new_node(raw: dict[str, Any], origin: str) -> _Node:
    """An interim merge node for a field (and subtree) one file introduced."""
    meta = {k: v for k, v in raw.items() if k.startswith("_")}
    return _Node(
        meta=dict(meta),
        base_meta=meta,
        origin=origin,
        meta_origin=dict.fromkeys(meta, origin),
        tightenings=[],
        children={k: _new_node(v, origin) for k, v in field_children(raw)},
    )


def _ordered_like(reference: list[str], keep: list[str]) -> list[str]:
    """``keep``'s values, in ``reference``'s order."""
    kept = set(keep)
    return [value for value in reference if value in kept]


def _vocabulary_key(meta: dict[str, Any]) -> str | None:
    """Which of the two vocabulary keys a declaration carries, if any.

    At most one, a rules file cannot declare both and the merge never writes a
    second onto a node.
    """
    return next((k for k in _VOCABULARY_ASPECTS if k in meta), None)


def _check_against_base(
    node: _Node, add_key: str, addition: list[str], origin: str, dotted: str
) -> str | None:
    """Whether this extension's vocabulary is a tightening of the base's, and
    what to say if it is not.

    Judged against ``base_meta``, never against what another extension has
    already imposed.
    """
    ref_key = _vocabulary_key(node.base_meta)
    if ref_key is None:
        return None  # an open field: any vocabulary closes it, which tightens
    ref = node.base_meta[ref_key]
    if ref_key == "_allowed_values" and add_key == "_suggested_values":
        return (
            f"{dotted}: {origin} offers _suggested_values where {node.origin} "
            f"closed the vocabulary with _allowed_values, that turns a "
            f"violation into a warning, and an extension may only tighten."
        )
    if set(addition) <= set(ref):
        return None
    outside = sorted(set(addition) - set(ref))
    if ref_key == add_key:
        return (
            f"{dotted}: {origin} widens {add_key} with {outside}, {node.origin} "
            f"declares {ref}, and an extension may only restrict a vocabulary "
            f"to a subset, never widen it."
        )
    return (
        f"{dotted}: {origin} closes the vocabulary on {outside}, which "
        f"{node.origin} does not recommend, closing what is suggested is a "
        f"tightening only over the values the base suggests, here it would "
        f"forbid {sorted(set(ref) - set(addition))}, which it recommends."
    )


def _merge_vocabulary(
    node: _Node,
    raw: dict[str, Any],
    origin: str,
    dotted: str,
    conflicts: list[str],
) -> None:
    """Merge whichever vocabulary an extension declares into the field's.

    Two steps: whether it tightens the base, then what all the extensions
    amount to together, which is an intersection and so does not depend on the
    order they are merged in.

    A field holds at most one vocabulary. The pair is read as a single fact
    with a nature, closed or recommended, and changing that nature is a move
    like any other, closing a recommended vocabulary tightens and the reverse
    is refused.
    """
    add_key = _vocabulary_key(raw)
    if add_key is None:
        return
    addition = list(raw[add_key])

    if problem := _check_against_base(node, add_key, addition, origin, dotted):
        conflicts.append(problem)
        return

    state_key = _vocabulary_key(node.meta)
    if state_key is None:
        _set_vocabulary(node, add_key, addition, origin)
        return

    state, author = node.meta[state_key], node.meta_origin[state_key]
    # The base's order if it has one, otherwise the order the first standard
    # to close it used.
    order = node.base_meta.get(_vocabulary_key(node.base_meta) or "", state)

    if state_key == add_key:
        combined = _ordered_like(order, sorted(set(state) & set(addition)))
        if not combined:
            conflicts.append(
                f"{dotted}: {origin} restricts {add_key} to {addition} and "
                f"{author} to {state}, no value satisfies both."
            )
        elif set(combined) != set(state):
            _set_vocabulary(node, add_key, combined, origin)
        # else: nothing this standard says is new, a redeclaration or a subset
        # another extension has already gone below. Not a tightening.
        return

    # One closes, the other recommends. Closing wins, but only over values that
    # are recommended, the rule _check_against_base applies to the base, here
    # between two extensions.
    closed, suggested = (
        (addition, state) if add_key == "_allowed_values" else (state, addition)
    )
    if not set(closed) <= set(suggested):
        closer = origin if add_key == "_allowed_values" else author
        suggester = author if add_key == "_allowed_values" else origin
        conflicts.append(
            f"{dotted}: {closer} closes the vocabulary on "
            f"{sorted(set(closed) - set(suggested))}, which {suggester} does "
            f"not recommend, the two standards disagree on what this field "
            f"may hold."
        )
        return
    if add_key == "_allowed_values":
        # The recommendation is not kept, it has become false.
        node.tightenings.append(
            Tightening(origin, _VOCABULARY_ASPECTS[state_key], list(state), None)
        )
        del node.meta[state_key]
        del node.meta_origin[state_key]
        _set_vocabulary(node, add_key, _ordered_like(order, addition), origin)


def _set_vocabulary(node: _Node, key: str, values: list[str], origin: str) -> None:
    """Record the tightening and write the vocabulary.

    ``before`` is the base's declaration for this key, not the state this
    standard found.
    """
    node.tightenings.append(
        Tightening(origin, _VOCABULARY_ASPECTS[key], node.base_meta.get(key), values)
    )
    node.meta[key] = values
    node.meta_origin[key] = origin


def _merge_meta(
    node: _Node,
    raw: dict[str, Any],
    origin: str,
    dotted: str,
    conflicts: list[str],
) -> None:
    """Merge one extension's metadata onto a field's interim node, tightening
    only."""
    meta, base_meta, wrote = node.meta, node.base_meta, node.meta_origin

    if raw["_type"] != base_meta["_type"]:
        conflicts.append(
            f"{dotted}: _type {base_meta['_type']!r} ({node.origin}) vs "
            f"{raw['_type']!r} ({origin}), a field's type is never negotiable."
        )

    base_card, addition_card = base_meta["_cardinality"], raw["_cardinality"]
    if addition_card != base_card:
        # Against the base's cardinality, not the merged one. Tightenings then
        # combine, required wins.
        if _SHAPE[addition_card] != _SHAPE[base_card]:
            conflicts.append(
                f"{dotted}: _cardinality {base_card!r} ({node.origin}) "
                f"vs {addition_card!r} ({origin}) changes the field's shape "
                f"(single value vs list)."
            )
        elif base_card in _REQUIRED:
            conflicts.append(
                f"{dotted}: {origin} loosens _cardinality {base_card!r}, "
                f"required by {node.origin}, to {addition_card!r}, an extension "
                f"may only tighten (optional -> required), never loosen."
            )
        else:
            node.tightenings.append(
                Tightening(origin, "cardinality", base_card, addition_card)
            )
            meta["_cardinality"] = addition_card
            wrote["_cardinality"] = origin

    _merge_vocabulary(node, raw, origin, dotted, conflicts)

    for key in _DESCRIPTIVE_KEYS:
        if key not in raw:
            continue
        if key not in meta:
            meta[key] = raw[key]
            wrote[key] = origin
        elif raw[key] != meta[key]:
            conflicts.append(
                f"{dotted}: {key} differs between {wrote[key]} and {origin}, "
                f"an extension may repeat what a description says, but not "
                f"replace it."
            )


def _merge_children(
    merged: dict[str, _Node],
    raw_children: dict[str, dict],
    origin: str,
    prefix: str,
    conflicts: list[str],
) -> None:
    for key, raw in raw_children.items():
        dotted = f"{prefix}.{key}"
        if key in merged:
            node = merged[key]
            _merge_meta(node, raw, origin, dotted, conflicts)
            _merge_children(
                node.children, dict(field_children(raw)), origin, dotted, conflicts
            )
        else:
            merged[key] = _new_node(raw, origin)


def _freeze(
    name: str, node: _Node, parent_path: tuple[str, ...], parent_dotted: str
) -> Field:
    """One interim node and its subtree, frozen into a Field."""
    meta = node.meta
    path = parent_path + (name,)
    is_list = _is_list(meta["_cardinality"])
    dotted = f"{parent_dotted}.{name}[]" if is_list else f"{parent_dotted}.{name}"

    def _values(key: str) -> tuple[str, ...] | None:
        return tuple(meta[key]) if key in meta else None

    return Field(
        name=name,
        path=path,
        dotted_path=dotted,
        cardinality=meta["_cardinality"],
        type=meta["_type"],
        origin=node.origin,
        description=meta.get("_description"),
        chapter_description=meta.get("_chapter_description"),
        allowed_values=_values("_allowed_values"),
        suggested_values=_values("_suggested_values"),
        tightenings=tuple(node.tightenings),
        children=tuple(
            _freeze(k, child, path, dotted) for k, child in node.children.items()
        ),
    )


def merge_rules(rules_paths: list[str | Path]) -> Model:
    """Load, validate and merge every rules file, ``<standard>/<version>.json``,
    into one ``Model``. The base is the one file without ``extends``, the
    extensions keep the order given.

    Raises ``RulesFileError`` for a malformed file, ``RulesSetError`` for an
    ill-formed set of files, ``RulesConflictError`` for extensions that do
    more than tighten the base, each with every problem of its phase.
    """
    return _build_model([(str(p), load(RULES, p)) for p in rules_paths])


def _set_problems(docs: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Everything wrong with the set of files before any merging: a standard
    declared twice, not exactly one base, or an extension written for another
    base or another version of it."""
    problems = []
    seen: dict[str, str] = {}
    for path, doc in docs:
        standard = doc["standard"]
        if standard in seen:
            problems.append(
                f'{path!r} declares "standard": {standard!r}, already declared '
                f"by {seen[standard]!r}, standard names must be unique."
            )
        else:
            seen[standard] = path

    bases = [doc for _, doc in docs if "extends" not in doc]
    if len(bases) != 1:
        problems.append(
            f"rules files must contain exactly one base standard (no "
            f'"extends"), found {len(bases)} among '
            f"{sorted(path for path, _ in docs)}."
        )
        return problems

    base = bases[0]
    for path, doc in docs:
        if "extends" not in doc:
            continue
        wanted, versions = doc["extends"]["standard"], doc["extends"]["versions"]
        if wanted != base["standard"]:
            problems.append(
                f"{path!r} extends {wanted!r}, the base here is "
                f"{base['standard']!r}: an extension extends the base."
            )
        elif base["version"] not in versions:
            problems.append(
                f"{path!r} extends {wanted} {', '.join(versions)}, the base "
                f"here is {wanted} {base['version']}."
            )
    return problems


def _build_model(docs: list[tuple[str, dict[str, Any]]]) -> Model:
    """Merge already-loaded, already-validated rules documents.

    Two phases, each complete: whether the set of files is well-formed, then
    whether they merge. Every problem of a phase is collected before it
    raises.
    """
    if problems := _set_problems(docs):
        raise RulesSetError(problems)

    base = next(doc for _, doc in docs if "extends" not in doc)
    extensions = [doc for _, doc in docs if "extends" in doc]

    merged: dict[str, _Node] = {
        key: _new_node(raw, base["standard"])
        for key, raw in field_children(base["dmp"])
    }
    conflicts: list[str] = []
    for doc in extensions:
        _merge_children(
            merged, dict(field_children(doc["dmp"])), doc["standard"], "dmp", conflicts
        )
    if conflicts:
        raise RulesConflictError(conflicts)

    fields = tuple(_freeze(k, node, (), "dmp") for k, node in merged.items())
    # A field an extension introduces is described by that extension.
    undescribed = [
        f"{field.dotted_path}: no _description, introduced by {field.origin}, "
        f"every field needs one, it is the question a researcher reads."
        for top in fields
        for field in top.walk()
        if field.description is None
    ]
    if undescribed:
        raise RulesSetError(undescribed)

    # The version is the document's own declaration.
    return Model(
        fields=fields,
        sources=tuple(
            Source(
                standard=doc["standard"],
                version=doc["version"],
                name=doc["name"],
                references=tuple((r["label"], r["url"]) for r in doc["references"]),
            )
            for doc in (base, *extensions)
        ),
    )
