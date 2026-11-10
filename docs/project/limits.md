# Known limits

The limits we know about and have not solved. Each says what would make it worth re-judging, because a limit without a trigger is one nobody revisits. Listing them is deliberate: a proof of concept that only reports what works is advertising, not evidence.

## Not verified automatically

### The template is not rendered by a DS Wizard in the CI

Verified: the Knowledge Model conforms to DS Wizard's metamodel, the template body parses as Jinja and renders, with DS Wizard's three filters replaced by doubles, to a document the API stores; the stack jobs publish both packages to a real instance and set its submission service. Not verified by a test: that a real DS Wizard renders the template the same way. A researcher's submission is the end-to-end proof, done by hand.

**Re-judge when** a step can create a project through the API and render it, on the CI's test stack.

### The metamodel versions describe one DS Wizard release

They are right for 4.31. A newer DS Wizard is an unknown until someone tries.

**Re-judge at** the first upgrade.

## Not built yet

**Production DMPs have no client.** The API creates and versions them, the database keeps them; nothing yet fills a template version with one deployment's values. See [What is next](next.md).

**One output format.** maDMP JSON is available; JSON-LD is listed as not implemented.

**No migration of a published Knowledge Model.** Raising the version publishes a new package; moving a project onto it is DS Wizard's own migration, done by hand.

## One project, one profile

One project, and a profile stack of one base plus one extension that only adds fields. The merge machinery is exercised on fixtures, not on a real disagreement between standards.

**Re-judge at** a second profile, national or institutional.

## The assessment judges values one at a time

Two datasets with the same title pass; a `modified` earlier than `created` says nothing; there are no conditional rules ("if `ethical_issues_exist` is `yes`, a description is required"). A rules file has no way of speaking about a field other than itself, so lifting this means extending the rules format first.

Formats are checked by shape, not membership: `language` is three lowercase letters, not the ISO 639-3 list.

## The deployment

**One environment.** The CD deploys `development`. A production instance, with its own domain, TLS and backups, is a second environment to add.

**The image comes from GitHub.** The CD deploys the GitHub image of the same commit, found in its registry before anything is applied: a commit GitHub has not published yet stops the job, run again once it has. The GitLab registry gets the same image, not deployed: pulling from it needs a pull secret on the cluster.

**A published image tag can be pushed again.** Protected tags would close it.

## True only under conditions

- **`S3_URL` must resolve identically from a container and from a browser.**
- **A local stack binds on `127.0.0.1`.** On a GitLab dind runner, the stack starts but the DS Wizard steps cannot reach it, so GitLab's stack jobs stop once it is up; GitHub's run them.
- **The demo accounts open a fresh instance completely** until `make dsw-admin` runs.
