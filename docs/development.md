# Development

How the repository is organised, how it is tested, and how to make the changes it is built for.

## The repository

```text
ostrails-madmp/
├── definitions/
│   ├── rules/                rules.schema.json, <standard>/<version>.json
│   └── projects/             project.schema.json, <id>/<version>.yaml
├── src/madmp/
│   ├── cli/                  one module per command group
│   ├── definitions/          read and validate a definition, frozen versions
│   ├── model/                pins, merge
│   ├── assessment/           a DMP against its model
│   ├── packages/             Knowledge Model, document template, identifiers
│   ├── store/                DMP database, migrations/
│   ├── api/                  the DMP API
│   ├── dsw/                  a running DS Wizard instance
│   └── errors.py             every error, in one place
├── tests/
│   ├── unit/                 the repository alone
│   ├── integration/          a PostgreSQL, the API, the image
│   └── fixtures/             the DMPs they assess
├── deploy/                   docker/, kubernetes/, scripts/
├── docs/                     this site
├── Dockerfile, Makefile, mkdocs.yml, pyproject.toml, uv.lock
└── .env.example              every value, with its local value
```

## Make, one target per command

Each `madmp` command has a make target of the same name, and each CI job runs the make target of its name: what fails in the CI fails the same way locally.

| Section | Targets |
|---|---|
| Environment | `install` |
| Quality | `lint`, `format`, `pre-commit` |
| Validate | `validate-all`, `validate-rules`, `validate-projects`, `validate-models`, `validate-frozen` |
| Assess, Packages | `assess-conformance`, `packages-generate` |
| Store, API, DSW | `store-migrate`, `store-sync`, `api-serve`, `dsw-admin`, `dsw-publish`, `dsw-submission`, `dsw-sync` |
| Image | `image-build` |
| Docker | `docker-check`, `docker-up`, `docker-down`, `docker-ps`, `docker-logs`, `docker-reset` |
| k3d, Kubernetes | `k3d-up`, `k3d-down`, `k8s-check`, `k8s-up`, `k8s-deploy`, `k8s-down`, `k8s-ps`, `k8s-logs`, `k8s-reset` |
| Documentation | `docs-serve`, `docs-build` |
| Tests, CI | `test-all`, `test-unit`, `test-integration`, `ci` |

`make help` prints them with their one-line description.

## Tests

| | Needs | Count |
|---|---|---|
| `make test-unit` | the repository | 506 |
| `make test-integration` | Docker: a PostgreSQL started once for the session, the image built | 95 |

The unit tests cover every module, the deploy scripts' value checks included, run by bash on files written for each test. The integration tests start from an empty database for each test, migrated and synced, and run the API through FastAPI's test client, the CLI, the image, and the document each project version's template renders with its required questions answered. Without Docker they are skipped, except in the CI, where they fail.

What is tested has a specification, or is an invariant true of any project rather than a fact about this one:

- **No golden files.** The two packages are not compared with a stored copy: both are generated, and every path the template reads is confronted with the entities the Knowledge Model emits. That test keeps working when the rules change.
- **Identity is frozen, output is not.** The identifier convention and the two metamodel versions are held against published values, because they are identity.
- **Doubles return what the real system returns.** A fake DS Wizard that agrees with our code about a shape neither owns tests nothing.

## Hooks

`make install` installs the git hooks. On each commit, on the files of the commit: generic checks (merge conflicts, YAML, JSON, TOML, large files, private keys, end of file, trailing spaces), ruff check and format, shellcheck, and the three definition checks. On each push: the unit tests. A hook that fixes a file stops the commit: add the fixed file and commit again.

## The documentation

```bash
make docs-serve    # http://127.0.0.1:8000, reloaded on save
make docs-build    # the site in site/, every warning an error
```

The pages are Markdown under `docs/`, one paragraph per line; the code reference is generated from the docstrings. The README says what the repository holds and how to run it; this site says how each part works and why; code comments say what the code does, and nothing else.

## Making the changes it is built for

### A new rules version

1. Copy `definitions/rules/<standard>/<version>.json` to the new version.
2. Edit the fields; `make validate-rules`.
3. Pin it from a new project version (below); `make validate-models` merges it.

### A new project version

1. Copy `definitions/projects/<id>/<version>.yaml` to the new version, with its new `version`.
2. Change the pins, the name, the author.
3. `make validate-all`, `make packages-generate PROJECT=definitions/projects/<id>`.

DS Wizard then holds both packages side by side, and researchers move their projects with its Knowledge Model migration.

### A new standard or profile

A new directory, `definitions/rules/<standard>/1.0.0.json`, with `extends` for a profile. No code: the loader, the merge, the tags and the packages take it as it is. See [Rules](guide/rules.md).

### A new migration

A new file `src/madmp/store/migrations/NNN_<name>.sql`, numbered after the last; `make test-integration` applies every migration to an empty database. A deployed database applies it at the next start of `prepare-db`.

## Conventions

- **No default for a coordinate.** No address or credential has a fallback; a missing value is named, every one at once.
- **Every error at once.** A check reports every problem of its step before stopping.
- **Each package knows one thing**, and the layout follows what a module knows, not who calls it.
- **Comments say what the code does.** The why lives here.
