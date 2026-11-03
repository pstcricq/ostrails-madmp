.DEFAULT_GOAL := help
.PHONY: help install lint format pre-commit test-all test-unit test-integration validate-all validate-rules validate-projects validate-models validate-frozen assess-conformance packages-generate store-migrate store-sync ci clean
.SILENT:

# Blank line once at the top of the output, then one after each command.
$(info )

# Run a command followed by a blank line and keep its exit code.
# Its argument holds no comma: $(call) splits its arguments on commas.
run = $(1); status=$$?; echo; exit $$status

# A section per group of the madmp command, named after it: `uv run madmp
# --help` lists the commands.

UV  := uv
RUN := $(UV) run

# What `make validate-all` and `validate-frozen` compare this checkout with, a
# branch or a commit, given to madmp as --base; unset, madmp's own default
# (origin/main).
BASE ?=

# What `make assess-conformance` assesses, a DMP file or a directory of them,
# no default.
DMP ?=

# What `make packages-generate` takes, a project's directory or one of its
# versions; unset, every version of every project.
PROJECT ?=

# Where `make packages-generate` writes the packages it builds; unset, nowhere.
OUT ?=

# The values the targets below that need some read: a file of .env.example's
# lines, filled in; unset, the environment.
ENV_FILE ?=
RUN_ENV := $(RUN) $(if $(ENV_FILE),--env-file $(ENV_FILE))

help: ## Show this help
	awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	echo

##@ Environment

install: ## Install the locked environment and the git hooks
	$(call run,$(UV) sync --extra store)
	$(call run,$(RUN) pre-commit install)

##@ Quality

lint: ## Lint the Python (ruff check + format --check)
	$(call run,$(RUN) ruff check .)
	$(call run,$(RUN) ruff format --check .)

format: ## Format and auto-fix the Python
	$(call run,$(RUN) ruff check --fix .)
	$(call run,$(RUN) ruff format .)

pre-commit: ## Run every pre-commit hook on every file
	$(call run,$(RUN) pre-commit run --all-files --show-diff-on-failure)

##@ Validate (madmp validate)

validate-all: ## Run every validate-* step, stopping at the first failure
	$(call run,$(RUN) madmp validate all $(if $(BASE),--base $(BASE)))

validate-rules: ## Check each rules file: meta-schema, path, coherence
	$(call run,$(RUN) madmp validate rules)

validate-projects: ## Check each project: schema and path
	$(call run,$(RUN) madmp validate projects)

validate-models: ## Resolve each project's pins and merge their rules
	$(call run,$(RUN) madmp validate models)

validate-frozen: ## Check no published version changed (BASE=origin/main)
	$(call run,$(RUN) madmp validate frozen $(if $(BASE),--base $(BASE)))

##@ Assess (madmp assess)

assess-conformance: ## Check DMP=<file or dir> against the rules it pins
	$(if $(DMP),,$(error DMP is not set: make assess-conformance DMP=<file or directory>))
	$(call run,$(RUN) madmp assess conformance $(DMP))

##@ Packages (madmp packages)

packages-generate: ## Build and check every KM and template (OUT=, PROJECT=)
	$(call run,$(RUN) madmp packages generate $(if $(OUT),--out $(OUT)) $(PROJECT))

##@ Store (madmp store, ENV_FILE=<file>, else the environment)

store-migrate: ## Bring the tables to this version's schema
	$(call run,$(RUN_ENV) madmp store migrate)

store-sync: ## Copy the rules and the projects into the database
	$(call run,$(RUN_ENV) madmp store sync)

##@ Tests

test-all: test-unit test-integration ## Run every test: unit, then integration

test-unit: ## Run the tests that need only the repository
	$(call run,$(RUN) pytest tests/unit -q)

test-integration: ## Run the tests that need a PostgreSQL (docker)
	$(call run,$(RUN) pytest tests/integration -q)

##@ CI

ci: lint pre-commit validate-all packages-generate test-all ## Everything the CI checks, in this order

##@ Cleanup

clean: ## Remove the Python caches (__pycache__)
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	$(call run,echo "Cleaning Done.")
