.DEFAULT_GOAL := help
.PHONY: help install lint format pre-commit ci clean
.SILENT:

# Blank line once at the top of the output, then one after each command.
$(info )

# Run a command followed by a blank line and keep its exit code.
# Its argument holds no comma: $(call) splits its arguments on commas.
run = $(1); status=$$?; echo; exit $$status

UV  := uv
RUN := $(UV) run

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

##@ CI

ci: lint pre-commit ## Everything the CI checks, in this order

##@ Cleanup

clean: ## Remove the Python caches (__pycache__)
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	$(call run,echo "Cleaning Done.")
