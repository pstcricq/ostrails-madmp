.DEFAULT_GOAL := help
.PHONY: help install lint format pre-commit test-unit validate-all validate-rules validate-projects validate-models validate-frozen ci clean
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

help: ## Show this help
	awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	echo

##@ Environment

install: ## Install the locked environment and the git hooks
	$(call run,$(UV) sync)
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

##@ Tests

test-unit: ## Run the tests that need only the repository
	$(call run,$(RUN) pytest tests/unit -q)

##@ CI

ci: lint pre-commit validate-all test-unit ## Everything the CI checks, in this order

##@ Cleanup

clean: ## Remove the Python caches (__pycache__)
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	$(call run,echo "Cleaning Done.")
