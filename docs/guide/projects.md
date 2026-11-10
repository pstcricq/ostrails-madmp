# Projects

A project at one version is one YAML file, `definitions/projects/<id>/<version>.yaml`. It says who the project is and which rules it is built from; everything else is derived.

```yaml
# A project at one version: its own facts, then the rules it is built from.
# Filed as <id>/<version>.yaml.

id: glider
organizationId: socib
name: "SOCIB Glider"
version: "1.0.0"
author: "Pierre St-Cricq dit Lompre ([SOCIB](https://www.socib.es))"
license: "CC BY 4.0"

# Each rules file at one version -> definitions/rules/<standard>/<version>.json
rules:
  - rda_dcs: "1.0.0"
  - ostrails: "1.0.0"
```

*`definitions/projects/glider/1.0.0.yaml`, the one project of the repository today.*

## The keys

Every key is required and no other is accepted.

| Key | Format | Used for |
|---|---|---|
| `id` | lowercase letters, digits and `-`, up to 64 | the directory, the package identifier, the DMP keys |
| `organizationId` | lowercase parts joined by dots | the package identifier, the DMP keys |
| `name` | free text | what DS Wizard shows; never derived from `id` |
| `version` | `X.Y.Z`, quoted | the file name, the package version |
| `author` | Markdown | the packages' README |
| `license` | free text | the packages' README |
| `rules` | `[{standard: version}, ...]`, at least one | the rules files the model merges, in this order |

Versions are quoted: unquoted, `1.0` would be a YAML number, not a version.

## What a project version produces

| Produced | Derived from | Value for glider 1.0.0 |
|---|---|---|
| the DS Wizard package identifier | `organizationId:id:version` | `socib:glider:1.0.0` |
| the Knowledge Model | the merged rules | `glider_1.0.0_km.km`, 171 questions |
| the document template | the same merged rules | `glider_1.0.0_template.json` |
| the key of the template DMP | `<organizationId>-<id>-template` | `socib-glider-template` |
| the keys of the production DMPs | `<organizationId>-<id>-<number>`, four digits at least | `socib-glider-0001`, `socib-glider-0002`, … |

The Knowledge Model and the template carry the same identifier, so DS Wizard offers the template for projects of that Knowledge Model only, and every maDMP the template renders carries `metadata.project`, `metadata.project_version` and `metadata.rules`: what it was built from, which is what the API judges it by.

## Checked like the rules

A project file is read, checked against `project.schema.json` (strict: every key required, none extra) and against its path, its `id` naming the directory and its `version` the file. Then its pins are resolved: each names exactly one rules file, which must exist, and the files they name must merge.

```bash
make validate-projects
make validate-models
```

## Versions are frozen

A published project version never changes. To pin a new rules version, rename the project, or change its author, add a new file at a new version: DS Wizard holds both packages side by side, researchers migrate their projects with DS Wizard's own Knowledge Model migration, and the database keeps every DMP version tied to the project version it came from.

## Adding a project

1. Create `definitions/projects/<id>/1.0.0.yaml` with the seven keys.
2. `make validate-all`, then `make packages-generate PROJECT=definitions/projects/<id>` to build its two packages.
3. Commit. The CI checks it, and the CD publishes its packages and copies it into the DMP database.
