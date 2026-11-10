# Assessment

The assessment answers one question: **is this DMP a valid instance of the standards it pins?** It reads the rules the document's own `metadata.rules` names, merges them like a project does, and walks the model and the document together, once. No network, no database, no state: the same document always gives the same result.

It runs in two places, with the same code: `make assess-conformance` on files, and the [DMP API](api.md) on every write, where a document that fails is refused.

## Four statuses

| Status | Meaning | Decides the verdict |
|---|---|---|
| `fail` | a required field missing, a JSON shape the cardinality does not allow, a wrong type or format, a value outside a closed vocabulary, or a key no rule declares | **yes** |
| `warning` | a present value outside a recommended vocabulary | no |
| `missing` | an optional field is absent | no |
| `pass` | present and valid | no |

There is one rule for the verdict: a document **fails when at least one check fails**. Warnings and absences are reported, never decisive.

## What is checked

| Category | Asks | For |
|---|---|---|
| `structure` | is the document an object holding a `dmp` object? | the document, once |
| `presence` | is the field there, and required? | every field the model declares |
| `shape` | a single value where the cardinality says one, an array where it says `n`? | every present field |
| `type` | the right scalar type, the right format? | every present scalar value |
| `allowed_values` | inside the closed vocabulary? | fields with `_allowed_values` |
| `suggested_values` | inside the recommended vocabulary? | fields with `_suggested_values` |
| `unexpected` | a key the document carries that no rule declares? | every key of every object |

Formats are checked by shape: `language` is three lowercase letters (ISO 639-3), `currency` three capitals (ISO 4217), `country_code` two capitals (ISO 3166-1 alpha-2), `date` is `YYYY-MM-DD` and a day the calendar has, `datetime` a date and a time, `email` and `url` what they look like.

An empty string counts as an **absence**, not a value; so does an item `""` of a list, and a list of nothing else. A string of spaces stays a value. An absent field gives exactly one `presence` result and nothing underneath it.

## On the command line

```bash
make assess-conformance DMP=glider.json
```

```text
FAIL glider.json
     rda_dcs + ostrails, 144 checks: 4 fail, 0 warning, 37 missing, 103 pass
     - dmp.colour: 'dmp.colour' is not a field the merged rules declare. Check the spelling, or whether it belongs to a standard this project does not pin.
     - dmp.ethical_issues_exist: 'dmp.ethical_issues_exist' = 'maybe' is not one of the allowed values ['yes', 'no', 'unknown'].
     - dmp.language: 'dmp.language': 'english' is not an ISO 639-3 language code (3 lowercase letters).
     - dmp.title: Required field 'dmp.title' (cardinality 1) is missing.

1 of 1 DMP failing.
```

*A DMP with four mistakes: a key nobody declared, a value outside a closed vocabulary, a wrong format, a required field left out. `DMP=` also takes a directory, every `*.json` in it.*

## The envelope

What the API stores beside every version, and returns with every write: everything one assessment produced, in one shape. Here for a DMP missing its title, with a wrong language code:

```json
{
  "dmp": "glider.json",
  "standards": ["rda_dcs", "ostrails"],
  "rules_versions": { "rda_dcs": "1.0.0", "ostrails": "1.0.0" },
  "verdict": "fail",
  "engine": "1.0.0",
  "summary": { "total": 143, "fail": 2, "warning": 0, "missing": 37, "pass": 104 },
  "fail": [
    {
      "category": "presence",
      "status": "fail",
      "rule_path": "dmp.title",
      "instance_path": "dmp.title",
      "standard": "rda_dcs",
      "message": "Required field 'dmp.title' (cardinality 1) is missing."
    }
  ],
  "warning": [],
  "missing": ["…"],
  "pass": ["…"]
}
```

| Key | |
|---|---|
| `rules_versions` | what judged it: the standards and versions merged |
| `engine` | the version of `madmp` that judged it |
| `summary` | the count of each status; each list holds exactly that many results |
| `rule_path` | the rule checked, `[]` marking a list: `dmp.dataset[].distribution[].title` |
| `instance_path` | the concrete spot: `dmp.dataset[0].distribution[2].title` |
| `standard` | the standard that introduced the field; a constraint an extension tightened says so in the message |

There is no timestamp: the database records when a version was written, and the envelope stays a pure function of the document and the rules.

## What it does not judge

The assessment judges **the plan**, value by value. It does not say whether the described data exist, whether they are FAIR, or whether two values of the document agree with each other: two datasets with the same title pass, a `modified` earlier than `created` says nothing, and there is no "required only when". Those are other layers, see [What is next](../project/next.md#assessment-in-three-layers).
