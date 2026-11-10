# Engineering practices

Nothing here is specific to DMPs. It is here because a proof of concept that someone else cannot rerun is a demonstration rather than an implementation, and because a few of these choices are the ones we would most recommend copying.

## One name per thing, everywhere

A `madmp` command, its make target and its CI job share one name: `madmp validate rules`, `make validate-rules`, the job `validate-rules`. A script, its target and its job too: `deploy.sh`, `make k8s-deploy`, the job `k8s-deploy`. A red CI job names the make target that reproduces it on a laptop, and the README, the help and this site all say the same word for the same thing.

## Report, or act

The useful line through a pipeline is not "before or after validation". Jobs that **report** run in parallel and each names its own culprit. Jobs that **act**, writing outside the repository (an image, a site, a deployment), wait for every verdict. See [CI and CD](../deployment/ci-cd.md).

## What we test, and what we refuse to test

**No golden test where there is no expected output.** Freezing our own output once the oracle is gone is recording ourselves. What is tested has a specification, or is an invariant true for any project rather than a fact about this one.

The two generated packages are not compared with a stored copy: both are generated, and every path the template reads is confronted with the entities the questionnaire emits. That test keeps working when the rules change.

Two things are frozen against published values, because they are **identity** rather than output: the identifier convention, and the two metamodel versions.

**A double that agrees with the code about a shape neither owns tests nothing.** A fake DS Wizard instance once returned what our code writes rather than what DS Wizard returns, and hid a guard that could never fire. Doubles now return what the external system returns.

**Tests do not depend on a stack.** The integration tests start their own PostgreSQL and render the template themselves; the stack jobs of the CI deploy, then run the commands a CD would run, twice.

## Reproducibility

Every job installs from the committed lockfile, with `--locked`, which also fails when the lockfile no longer matches `pyproject.toml`, so the code runs against the same versions on a laptop, on a runner and in the image. The image's base names its Python patch and its Debian release. One commit gives one image, one pair of packages and one set of definitions in the database, deployed together.

**Dependencies are earned.** The base package needs jsonschema, pyyaml and jinja2; the database driver and the API server are extras; the DS Wizard client uses the standard library only.

## Each package knows one thing

The rule that keeps the layout stable is not "how many modules use this", it is **what does this module know**. That criterion can refuse an addition, which is what a layout rule is for: resolving pins knows nothing of DS Wizard, the database knows nothing of HTTP.

## No default for a coordinate

No address or credential has a fallback value. A default address is one deployment's address baked into every other, and a missing value is an error naming every missing value at once, so a fresh deployment is fixed in one pass.

## Three places to write things down

- **The README** says what the repository holds today and how to run it, and only what is verified.
- **The documentation**, this site, says how each part works and why it is built this way.
- **Code comments** say what the code does, and nothing else.

The three age differently. A README describing a plan rots the day the plan changes; a document repeating the code rots at the first refactor. Keeping each to its own question is what makes them worth reading a year later.
