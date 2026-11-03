"""The document template of a project version: ``build_template_bundle()``
emits the Jinja template DSW renders into the maDMP JSON document, ``dmp`` and
its ``metadata``. The macros ``sv`` and ``av`` read a reply as it is, ``jv``
escaped by ``js``. Every key carries its comma in front, an optional one in
its own ``{%- if %}`` block, and the first comma is stripped at render time.
"""

from __future__ import annotations

import json
from typing import Any

from madmp.model import Field, Model
from madmp.packages.common import (
    COMPUTED_FIELDS,
    field_kind,
    needs_a_synthetic_escape,
    package_description,
    package_id,
    readme,
    standard_label,
    top_level_split,
    utc_timestamp,
)
from madmp.packages.uuids import (
    answer_uuid,
    chapter_uuid,
    format_uuid,
    gate_uuid,
    gate_yes_uuid,
    list_item_value_uuid,
    other_answer_uuid,
    other_followup_uuid,
    question_uuid,
    template_file_uuid,
)

# The DSW document-template metamodel version the bundle declares.
TEMPLATE_METAMODEL_VERSION = "18.0"

# The Jinja expression for each computed top-level field, read from the
# render context. A computed field with no expression here is absent from the
# document.
COMPUTED_FIELD_EXPR: dict[str, str] = {
    "created": "ctx.project.createdAt",
    "modified": "ctx.project.updatedAt",
}

# Every output format, available or not: the available ones become formats
# of the bundle, every one a row of the table of its readme.
FORMATS: list[dict[str, Any]] = [
    {
        "name": "JSON",
        "available": True,
        "content_type": "application/json",
        "extension": "json",
        "notes": (
            "Plain JSON export of the `dmp` object, following the merged "
            "rules of the project's standards."
        ),
    },
    {
        "name": "JSON-LD",
        "available": False,
        "content_type": None,
        "extension": None,
        "notes": "Linked-data version of the same output. Not implemented yet.",
    },
]


def reply_path_expr(chain: list[str]) -> str:
    """The Jinja ``|reply_path`` expression for a chain of UUID expressions
    (quoted literals or variable names)."""
    return "[" + ", ".join(chain) + "]|reply_path"


def q(text: str) -> str:
    """``text`` as a Jinja string literal: a backslash, a single quote and
    every control character written as escapes, which Jinja decodes back."""
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return "'" + "".join(c if c >= " " else f"\\u{ord(c):04x}" for c in escaped) + "'"


# The escapes of the body of a JSON string: a backslash, a double quote, and
# every character below U+0020, the backslash first.
_JSON_ESCAPES: tuple[tuple[str, str], ...] = (
    ("\\", "\\\\"),
    ('"', '\\"'),
    ("\b", "\\b"),
    ("\f", "\\f"),
    ("\n", "\\n"),
    ("\r", "\\r"),
    ("\t", "\\t"),
    *(
        (chr(code), f"\\u{code:04x}")
        for code in range(0x20)
        if chr(code) not in "\b\f\n\r\t"
    ),
)


def _json_escape_chain(expression: str) -> str:
    """``expression`` followed by the ``|replace`` chain that turns whatever it
    evaluates to into the body of a JSON string."""
    return expression + "".join(
        f"\n  |replace({q(search)}, {q(replacement)})"
        for search, replacement in _JSON_ESCAPES
    )


class OutputField:
    """One emitted JSON ``"key": value`` pair of the output template.

    ``required`` keys are always emitted, optional keys are each wrapped in
    their own ``{%- if condition %}`` block. Both carry their separating comma
    in front of them, and ``render_object()`` strips the one that ends up
    first, so which keys render is decided at render time.

    ``is_object`` marks ``value_expr`` as raw JSON/Jinja text rather than a
    scalar to quote, and ``preamble`` holds the ``{% set %}`` statements that
    must run before ``condition`` is evaluated.
    """

    def __init__(
        self,
        key: str,
        value_expr: str,
        required: bool,
        condition: str | None = None,
        is_object: bool = False,
        preamble: str = "",
    ) -> None:
        self.key = key
        self.value_expr = value_expr
        self.required = required
        self.condition = condition
        self.is_object = is_object
        self.preamble = preamble

    def render(self, depth: int) -> str:
        """Render as an indented fragment, comma first. For object and array
        values the caller must have built ``value_expr`` with ``depth + 1`` for
        its children, see ``render_object()``."""
        indent = "  " * depth
        v = self.value_expr if self.is_object else f'"{{{{ {self.value_expr} }}}}"'
        line = f'{indent}"{self.key}": {v}'
        if self.required:
            return f"{self.preamble},\n{line}"
        return f"{self.preamble}{{%- if {self.condition} %}},\n{line}\n{{%- endif %}}"


def object_var(path: tuple[str, ...]) -> str:
    """The Jinja variable an object's body is captured in: ``_obj``, then
    each part of its path, ``_obj_a_b`` for ``("a", "b")``, ``_obj`` for the
    ``dmp`` root, ``()``."""
    return "_obj" + "".join(f"_{part}" for part in path)


def render_object(fields: list[OutputField], depth: int, var: str) -> str:
    """Assemble a JSON object literal, required fields first.

    Every key renders with a comma in front of it: the body is captured, then
    its first comma stripped. An object whose fields are all optional renders
    as ``{}`` until one of them is answered.

    The newline after the ``{`` sits between the brace and the ``{%-`` that
    follows, which strips it back.
    """
    required = [f for f in fields if f.required]
    optional = [f for f in fields if not f.required]
    body = "".join(f.render(depth) for f in required + optional)
    closing_indent = "  " * (depth - 1)
    return (
        "{\n"
        f"{{%- set {var}_raw %}}{body}{{%- endset %}}"
        f"{{%- set {var} = {var}_raw.lstrip()[1:] -%}}"
        f"{{{{ {var} }}}}\n{closing_indent}}}"
    )


class TemplateBuilder:
    """Accumulates the answer-label table while building the output tree."""

    def __init__(self) -> None:
        # answer_uuid -> label, for the template's AL Jinja dict, which
        # translates a stored answer UUID back into its literal label.
        self.answer_labels: dict[str, str] = {}

    def build_scalar_field(self, field: Field, chain: list[str]) -> OutputField:
        """A scalar field, plain value, strict or suggested options with their
        "Other" follow-up, or boolean, on one line."""
        kind = field_kind(field)
        own_chain = chain + [q(question_uuid(field.path))]
        own_path = reply_path_expr(own_chain)

        if kind == "options_suggested" and needs_a_synthetic_escape(field):
            for value in field.suggested_values:
                self.answer_labels[answer_uuid(field.path, value)] = value
            other_chain = chain + [
                q(question_uuid(field.path)),
                q(other_answer_uuid(field.path)),
                q(other_followup_uuid(field.path)),
            ]
            other_path = reply_path_expr(other_chain)
            # The "Other" answer has no entry in AL: a lookup falling back to
            # 'other' finds it, and the value typed under it is emitted,
            # escaped. Any other answer gives its label, '' unanswered.
            value_expr = (
                f"jv({other_path}) if (av({own_path}, 'other') == 'other' and "
                f"{other_path} in r and r[{other_path}]|reply_str_value) "
                f"else js(av({own_path}, ''))"
            )
        elif kind in ("options_strict", "options_suggested"):
            # A closed vocabulary, or a suggested one naming its own escape:
            # every value is an answer of its own, with its label in AL.
            for value in field.allowed_values or field.suggested_values:
                self.answer_labels[answer_uuid(field.path, value)] = value
            # The label, escaped, '' unanswered.
            value_expr = f"js(av({own_path}, ''))"
        elif kind == "boolean":
            for value in ("yes", "no"):
                self.answer_labels[answer_uuid(field.path, value)] = value
            # A JSON boolean: true for Yes, false for No, null unanswered. A
            # required key is emitted, answered or not.
            answered = f"av({own_path}, '')"
            return OutputField(
                field.name,
                f"{{{{ 'true' if {answered} == 'yes' "
                f"else ('false' if {answered} == 'no' else 'null') }}}}",
                required=field.cardinality == "1",
                condition=f"{own_path} in r and r[{own_path}]|reply_str_value",
                is_object=True,
            )
        elif kind == "value":
            value_expr = f"jv({own_path})"
        else:
            # Any other kind is refused, "computed" included.
            raise ValueError(f"{field.dotted_path}: nothing renders kind {kind!r}")

        condition = f"{own_path} in r and r[{own_path}]|reply_str_value"
        return OutputField(
            field.name,
            value_expr,
            required=field.cardinality == "1",
            condition=condition,
        )

    def build_multi_choice_field(
        self, field: Field, chain: list[str], depth: int
    ) -> OutputField:
        """An ``options_*_multi`` field: a JSON array of every chosen label,
        appending the one manually-entered value from an "other" follow-up
        where the field was given one."""
        own_path = reply_path_expr(chain + [q(question_uuid(field.path))])

        values = list(field.allowed_values or field.suggested_values)
        for value in values:
            self.answer_labels[answer_uuid(field.path, value)] = value

        item_var = f"{'_'.join(field.path)}_choice"
        preamble = (
            f"{{%- set {item_var}_items = r[{own_path}]|reply_items "
            f"if {own_path} in r else [] %}}\n"
        )

        other_var = None
        if needs_a_synthetic_escape(field):
            other_path = reply_path_expr(chain + [q(other_followup_uuid(field.path))])
            # Held raw, escaped where it is emitted. It also decides the
            # array's last comma and whether the key renders.
            other_var = f"{item_var}_other"
            preamble += (
                f"{{%- set {other_var} = sv({other_path}) if {other_path} in r and "
                f"r[{other_path}]|reply_str_value else '' %}}\n"
            )

        item_indent = "  " * (depth + 1)
        closing_indent = "  " * depth
        comma_guard = f" or {other_var}" if other_var else ""
        lines = [
            "[",
            f"{{%- for {item_var}_uuid in {item_var}_items %}}",
            (
                f"{item_indent}\"{{{{ js(AL.get({item_var}_uuid, 'unknown')) }}}}\""
                f"{{% if not loop.last{comma_guard} %}},{{% endif %}}"
            ),
            "{%- endfor %}",
        ]
        if other_var:
            lines += [
                f"{{%- if {other_var} %}}",
                f'{item_indent}"{{{{ js({other_var}) }}}}"',
                "{%- endif %}",
            ]
        lines.append(f"{closing_indent}]")

        condition = f"{item_var}_items" + (f" or {other_var}" if other_var else "")
        return OutputField(
            field.name,
            "\n".join(lines),
            required=False,
            condition=condition,
            is_object=True,
            preamble=preamble,
        )

    def build_scalar_list_field(
        self, field: Field, chain: list[str], depth: int
    ) -> OutputField:
        """A ``value_multi`` field: a JSON array of the value of each list
        item's one question."""
        list_path = reply_path_expr(chain + [q(question_uuid(field.path))])
        item_var = f"{'_'.join(field.path)}_item"
        item_value_path = reply_path_expr(
            [list_path, f"{item_var}_uuid", q(list_item_value_uuid(field.path))]
        )

        item_indent = "  " * (depth + 1)
        closing_indent = "  " * depth
        preamble = (
            f"{{%- set {item_var}_items = r[{list_path}]|reply_items "
            f"if {list_path} in r else [] %}}\n"
        )
        value = (
            f"[\n"
            f"{{%- for {item_var}_uuid in {item_var}_items %}}\n"
            f'{item_indent}"{{{{ jv({item_value_path}) }}}}"'
            f"{{% if not loop.last %}},{{% endif %}}\n"
            f"{{%- endfor %}}\n"
            f"{closing_indent}]"
        )
        return OutputField(
            field.name,
            value,
            required=False,
            condition=f"{item_var}_items",
            is_object=True,
            preamble=preamble,
        )

    def build_gated_object_field(
        self, field: Field, chain: list[str], depth: int
    ) -> OutputField:
        """A ``0..1`` gated object: the JSON key appears only when the gate
        was answered "Yes"."""
        gate_path = reply_path_expr(chain + [q(gate_uuid(field.path))])
        yes_chain = chain + [q(gate_uuid(field.path)), q(gate_yes_uuid(field.path))]

        sub_fields = [
            self.build_any_field(child, yes_chain, depth + 1)
            for child in field.children
        ]
        condition = (
            f"{gate_path} in r and r[{gate_path}]|reply_str_value == "
            f"{q(gate_yes_uuid(field.path))}"
        )
        return OutputField(
            field.name,
            render_object(sub_fields, depth + 1, object_var(field.path)),
            required=False,
            condition=condition,
            is_object=True,
        )

    def build_list_field(
        self, field: Field, chain: list[str], depth: int
    ) -> OutputField:
        """A list of objects: a Jinja ``{% for %}`` over the list's items,
        rebuilding each item's reply path from its item UUID."""
        list_path = reply_path_expr(chain + [q(question_uuid(field.path))])
        item_var = f"{'_'.join(field.path)}_item"

        sub_fields = [
            self.build_any_field(child, [f"{item_var}_path"], depth + 2)
            for child in field.children
        ]
        item_obj = render_object(sub_fields, depth + 2, object_var(field.path))
        item_indent = "  " * (depth + 1)
        closing_indent = "  " * depth

        preamble = (
            f"{{%- set {item_var}_items = r[{list_path}]|reply_items "
            f"if {list_path} in r else [] %}}\n"
        )
        value = (
            f"[\n"
            f"{{%- for {item_var}_uuid in {item_var}_items %}}\n"
            f"{{%- set {item_var}_path = [{list_path}, {item_var}_uuid]|reply_path %}}\n"
            f"{item_indent}{item_obj}{{% if not loop.last %}},{{% endif %}}\n"
            f"{{%- endfor %}}\n"
            f"{closing_indent}]"
        )
        return OutputField(
            field.name,
            value,
            required=False,
            condition=f"{item_var}_items",
            is_object=True,
            preamble=preamble,
        )

    def build_any_field(
        self, field: Field, chain: list[str], depth: int
    ) -> OutputField:
        kind = field_kind(field)
        if kind == "object_inline":
            sub_fields = [
                self.build_any_field(child, chain, depth + 1)
                for child in field.children
            ]
            return OutputField(
                field.name,
                render_object(sub_fields, depth + 1, object_var(field.path)),
                required=True,
                is_object=True,
            )
        if kind == "object_gated":
            return self.build_gated_object_field(field, chain, depth)
        if kind == "list":
            return self.build_list_field(field, chain, depth)
        if kind in ("options_strict_multi", "options_suggested_multi"):
            return self.build_multi_choice_field(field, chain, depth)
        if kind == "value_multi":
            return self.build_scalar_list_field(field, chain, depth)
        return self.build_scalar_field(field, chain)


# The DMP's URL in DSW, from the render context: the client's base URL, then
# the project's uuid.
DSW_DMP_ID_URL = "{{ ctx.config.clientUrl }}/projects/{{ ctx.project.uuid }}"


def _dsw_dmp_id_field(depth: int) -> OutputField:
    child_indent = "  " * (depth + 1)
    closing_indent = "  " * depth
    value = (
        "{\n"
        f'{child_indent}"identifier": "{DSW_DMP_ID_URL}",\n'
        f'{child_indent}"type": "url"\n'
        f"{closing_indent}}}"
    )
    return OutputField("dmp_id", value, required=True, is_object=True)


def _metadata_object(definition: dict[str, Any], model: Model) -> str:
    """The provenance block the rendered document carries beside ``dmp``, as
    the JSON literal it is emitted as.

    Resolved when the template is built: the project, its version, and the
    rules versions of the merged model, written as pins. Every value is
    written by ``json.dumps()``.
    """
    pins = ",\n".join(
        f"      {json.dumps({name: version})}"
        for name, version in model.standard_versions
    )
    return (
        "{\n"
        f'    "project": {json.dumps(definition["id"])},\n'
        f'    "project_version": {json.dumps(definition["version"])},\n'
        '    "rules": [\n'
        f"{pins}\n"
        "    ]\n"
        "  }"
    )


def build_template_bundle(
    definition: dict[str, Any], model: Model, created_at: str | None = None
) -> dict[str, Any]:
    """The full DSW ``DocumentTemplate`` bundle for one project version, its
    ``definition`` and the ``model`` its pins merge into, ready for the
    ``document-templates/bundle`` endpoint.

    ``created_at`` defaults to now. Given, two runs give the same bundle.
    """
    created_at = created_at or utc_timestamp()
    pid = package_id(definition)
    builder = TemplateBuilder()

    general, chapters = top_level_split(model)

    root_fields: list[OutputField] = []
    general_chain = [q(chapter_uuid("general"))]
    for field in general:
        if field.name in COMPUTED_FIELDS:
            expr = COMPUTED_FIELD_EXPR.get(field.name)
            if expr is not None:
                root_fields.append(OutputField(field.name, expr, required=True))
            continue
        # Built like a chapter field: a top-level scalar can still be a list
        # through its cardinality.
        root_fields.append(builder.build_any_field(field, general_chain, depth=2))

    for field in chapters:
        if field.name in COMPUTED_FIELDS:
            # Of the computed chapter fields, dmp_id alone is emitted, from
            # DSW_DMP_ID_URL.
            if field.name == "dmp_id":
                root_fields.append(_dsw_dmp_id_field(depth=2))
            continue
        root_fields.append(
            builder.build_any_field(field, [q(chapter_uuid(field.name))], depth=2)
        )

    dmp_object = render_object(root_fields, 2, object_var(()))

    al_entries = ",\n".join(
        f"  {q(uuid_)}: {q(label)}"
        for uuid_, label in sorted(builder.answer_labels.items())
    )
    al_dict = "{\n" + al_entries + "\n}"

    template_body = (
        "{% autoescape false %}\n"
        "{%- set r = ctx.project.replies -%}\n\n"
        f"{{%- set AL = {al_dict} -%}}\n\n"
        "{#- js() makes a string safe to sit between two quotes; every macro\n"
        "    and every expression below that renders text goes through it. -#}\n"
        f"{{%- macro js(text) -%}}{{{{ {_json_escape_chain('text')} }}}}{{%- endmacro -%}}\n"
        "{%- macro sv(path) -%}{{ r[path]|reply_str_value if path in r else '' }}{%- endmacro -%}\n"
        "{%- macro av(path, default='') -%}{{ AL.get(r[path]|reply_str_value, default) if path in r else default }}{%- endmacro -%}\n"
        "{%- macro jv(path) -%}{{ js(r[path]|reply_str_value) if path in r else '' }}{%- endmacro -%}\n\n"
        "{#- Every chapter and question UUID below is the KM's, derived from\n"
        "    the path of its rules field. -#}\n\n"
        "{\n"
        '  "dmp": ' + dmp_object + ",\n"
        '  "metadata": ' + _metadata_object(definition, model) + "\n"
        "}\n"
        "{% endautoescape %}\n"
    )

    template_filename = f"{definition['id'].replace('-', '_')}.json.j2"

    def build_readme() -> str:
        standards = [standard_label(s) for s in model.standards]
        base, extensions = standards[0], standards[1:]
        coverage = (
            base if not extensions else f"{base}, extended with {', '.join(extensions)}"
        )
        body = [
            "## Output",
            "",
            (
                f"Structured around the `dmp` root object, covering {coverage}. "
                "A `metadata` object sits beside it, naming the project, its "
                "version and the rules versions this document was built "
                "from."
            ),
            "",
            "| Format | Status | Notes |",
            "|---|---|---|",
        ]
        for fmt in FORMATS:
            status = "Available" if fmt["available"] else "Planned"
            body.append(f"| {fmt['name']} | {status} | {fmt['notes']} |")
        if COMPUTED_FIELD_EXPR:
            body += [
                "",
                (
                    "Auto-filled from the DSW project itself rather than from "
                    "the researcher's replies:"
                ),
                "",
            ]
            for field_name, expr in sorted(COMPUTED_FIELD_EXPR.items()):
                body.append(f"- `dmp.{field_name}`, from `{expr}`")
            body.append(
                "- `dmp.dmp_id`, the DMP's current URL in DSW "
                "(`ctx.config.clientUrl` + `/projects/<uuid>`)"
            )
        return readme(
            definition,
            model,
            "Document Template",
            body,
            [
                f"Knowledge Model: `{pid}`",
                f"DS Wizard template metamodel version: {TEMPLATE_METAMODEL_VERSION}",
            ],
        )

    return {
        "allowedPackages": [
            {
                # Its own KM, at its own version only.
                "kmId": definition["id"],
                "maxVersion": definition["version"],
                "minVersion": definition["version"],
                "orgId": definition["organizationId"],
            }
        ],
        "assets": [],
        "createdAt": created_at,
        "description": package_description(model),
        "formats": [
            {
                "icon": "fas fa-file-code",
                "name": f"maDMP {fmt['name']} ({definition['id']})",
                "steps": [
                    {
                        "name": "jinja",
                        "options": {
                            "content-type": fmt["content_type"],
                            "extension": fmt["extension"],
                            "template": template_filename,
                        },
                    }
                ],
                "uuid": format_uuid(fmt["name"]),
            }
            for fmt in FORMATS
            if fmt["available"]
        ],
        "id": pid,
        "license": definition["license"],
        "metamodelVersion": TEMPLATE_METAMODEL_VERSION,
        "name": definition["name"],
        "organizationId": definition["organizationId"],
        "readme": build_readme(),
        "templateId": definition["id"],
        "version": definition["version"],
        "files": [
            {
                "fileName": template_filename,
                # Derived from the package id: one per project version, the
                # same at every run.
                "uuid": template_file_uuid(pid, template_filename),
                "content": template_body,
            }
        ],
    }
