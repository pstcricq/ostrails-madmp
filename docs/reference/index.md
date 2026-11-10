# Code reference

Generated from the docstrings of `src/madmp/`, so it is always the code's own account of itself. The guide says how the parts work together; this reference says what each module, class and function does.

| Package | Knows |
|---|---|
| [Command line](cli.md) | the `madmp` command, one module per group |
| [Definitions](definitions.md) | where a definition lives, how it is read and checked, what changed since a git revision |
| [Model](model.md) | which rules files a pin names, and how they merge |
| [Assessment](assessment.md) | whether a DMP holds up against a model |
| [Packages](packages.md) | what a field becomes in DS Wizard, the two packages, their identifiers |
| [DMP database](store.md) | the database: its schema, the definitions in it, the DMPs |
| [DMP API](api.md) | the routes, the tokens, what each write checks |
| [DS Wizard](dsw.md) | a running instance: its administrator, its packages, its submission service |
| [Errors](errors.md) | every error, in one place |

Private names, starting with `_`, are left out.
