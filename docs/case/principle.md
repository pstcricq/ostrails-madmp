# The principle

> A rule added to a JSON file becomes a DSW question **and** a check of every DMP submitted, with no code and no room for drift.

Everything else follows from that sentence. This page says what it means, what it buys and what it costs.

## Rules are data, and the only source of truth

A standard is a JSON file describing a tree of fields. This one is real, from the RDA DMP Common Standard file:

```json
"ethical_issues_exist": {
  "_cardinality": "1",
  "_type": "string",
  "_allowed_values": ["yes", "no", "unknown"],
  "_description": "Whether the project raises ethical issues."
}
```

- **cardinality** says *how many*: `1`, `0..1`, `1..n`, `0..n`
- **type** says *what each value is*: an object, or a scalar format such as `date`, `email`, `url`, `country_code`
- **a closed vocabulary** (`_allowed_values`) or **a recommended one** (`_suggested_values`), never both

There is no `list` type: being a list is carried by the cardinality alone, so one file cannot say the same thing two ways. That is the whole vocabulary an author needs. No code, no template syntax, no identifier to invent. The format is in [Rules](../guide/rules.md).

## Declared once, derived everywhere

| What a reader or a program meets | Where it comes from |
|---|---|
| a chapter of the questionnaire | a top-level object field |
| a question, and its type | a field, through one decision function |
| the answers of a controlled vocabulary | the vocabulary's values |
| the order questions are read in | the order fields are declared in |
| the identifier of every entity | the path of the field it was generated for |
| the tag naming a standard | the standard's own name, upper-cased |
| the expression that reads an answer in the template | the same field path |
| the checks a submitted document faces | the same field: cardinality, type, vocabulary |

One thing is declared rather than derived: a project's human-readable name. Deriving `SOCIB HF Radar` from `socib-hf-radar` fails on acronyms, accents and capitals, and it is safe to declare because it names nothing: no identifier, path or package depends on it.

## Structural, not disciplinary

The promise is not "we are careful". Two mechanisms make drift impossible rather than unlikely.

**Deterministic identity.** Every generated entity takes its UUID from a `uuid5` over the path of its field. The questionnaire generator and the template generator share no table, yet both arrive at the same identifier for the same field. The test of that agreement is not a fixture: both packages are generated, and every path the template reads is confronted with the entities the Knowledge Model emits. See [Identifiers](../guide/identifiers.md).

**A single decision point.** One function answers "what is this field, logically?" with one of eleven answers, and every generator asks it. A field the questionnaire asks as a list and the template renders as a single value would be a pair of packages nobody can fill in, and no test of either alone would catch it. See [Knowledge model](../guide/knowledge-model.md).

The rule behind both: what several programs must answer identically lives in exactly one place.

## Mechanism, not content

No code names a standard. A standard is a directory, the loader is handed one file at a time, a project pins versions in an ordered list, and the merge folds however many files it is given. Removing a standard removes data, not a capability. Adding a national or thematic profile is a file.

## The unit of change is one versioned file

One YAML file per project version carries everything that defines it: its identity, its organization, its name, its author and licence, and the rules versions it pins. From it alone come a Knowledge Model, a document template, and the keys its DMPs are stored under. A published version never changes: a change is a new file, at a new version, so no project drifts because another was edited. See [Projects](../guide/projects.md).

## What it costs

Three prices, paid knowingly.

**The identifier convention is frozen for life.** Changing how UUIDs are derived would change every identifier and orphan every answer stored in the platform. A test holds the derived values against what is already published.

**Everything must be expressible in the rules language.** A constraint the language cannot state, such as "required only when that other field has a given value", cannot be expressed until the language gains it. The alternative is an escape hatch into code, and an escape hatch used once is used everywhere within a year.

**Validation is strict at the door.** A rules file is checked three ways when it loads, and every problem is reported at once. A misplaced, misnamed or duplicated vocabulary is refused rather than half accepted. Authors pay in refused edits; the alternative is a typo reaching a researcher's questionnaire.
