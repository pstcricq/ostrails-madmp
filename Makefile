.DEFAULT_GOAL := help
.PHONY: help install lint format pre-commit test-all test-unit test-integration validate-all validate-rules validate-projects validate-models validate-frozen assess-conformance packages-generate store-migrate store-sync api-serve dsw-admin dsw-publish dsw-submission dsw-sync image-build docker-check docker-up docker-down docker-ps docker-logs docker-reset k8s-check k3d-up k3d-down k8s-up k8s-down k8s-ps k8s-logs k8s-reset ci clean
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

# What `make packages-generate` and `dsw-publish` take, a project's directory
# or one of its versions; unset, every version of every project.
PROJECT ?=

# Where `make packages-generate` writes the packages it builds; unset, nowhere.
OUT ?=

# Every shell script of the repository, for shellcheck.
SCRIPTS := find . -name '*.sh' -not -path './.*/*'

# The stack under docker compose (deploy/docker/), its values from
# .env.example, then deploy/docker/.env when the file exists, else from the
# environment; every profile, so the targets below reach every service the
# stack runs.
COMPOSE := docker compose -f deploy/docker/docker-compose.yml --profile "*" --env-file .env.example \
	$(if $(wildcard deploy/docker/.env),--env-file deploy/docker/.env)

# The local Kubernetes cluster by its name in deploy/kubernetes/k3d.yaml
# (metadata.name), and its context.
CLUSTER := $(shell sed -n 's/^  name: \(..*\)/\1/p' deploy/kubernetes/k3d.yaml)
CONTEXT := k3d-$(CLUSTER)
# The stack's namespace, STACK_NAME, from deploy/kubernetes/.env, else from
# the environment.
STACK_NAME := $(or $(firstword $(shell sed -n 's/^STACK_NAME=\(..*\)/\1/p' deploy/kubernetes/.env 2>/dev/null)),$(STACK_NAME))
KUBECTL := kubectl --context $(CONTEXT) -n $(STACK_NAME)

# What `make k3d-up` adds to `k3d cluster create`, its flags over k3d.yaml;
# unset, nothing.
K3D_ARGS ?=

# The image `make image-build` builds, its name and tag.
IMAGE ?= madmp:local

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
	$(call run,$(UV) sync --extra api)
	$(call run,$(RUN) pre-commit install)

##@ Quality

lint: ## Lint the Python (ruff) and the shell scripts (shellcheck)
	$(call run,$(RUN) ruff check .)
	$(call run,$(RUN) ruff format --check .)
	$(call run,$(SCRIPTS) -exec $(RUN) shellcheck -x {} + && echo "shellcheck: no issue")

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

##@ API (madmp api, ENV_FILE=<file>, else the environment)

api-serve: ## Serve the DMP API on 127.0.0.1:8081, until stopped
	$(RUN_ENV) madmp api serve

##@ DSW (madmp dsw, ENV_FILE=<file>, else the environment)

dsw-admin: ## Make sure of DSW's administrator, DSW_USER
	$(call run,$(RUN_ENV) madmp dsw admin)

dsw-publish: ## Upload what DSW lacks, refuse a changed one (PROJECT=)
	$(call run,$(RUN_ENV) madmp dsw publish $(PROJECT))

dsw-submission: ## Set DSW's submission service for the templates it holds
	$(call run,$(RUN_ENV) madmp dsw submission)

dsw-sync: dsw-admin dsw-publish dsw-submission ## Run dsw-admin, dsw-publish, then dsw-submission

##@ Image (docker)

image-build: ## Build the madmp image of this checkout (IMAGE=madmp:local)
	$(call run,docker build -t $(IMAGE) .)

##@ Docker (deploy/docker/.env, else the environment)

docker-check: ## Check the values, then docker-compose.yml with them
	$(call run,bash deploy/docker/scripts/check.sh)

docker-up: ## Check, build the madmp image, start the stack and wait
	$(call run,bash deploy/docker/scripts/prepare.sh)

docker-down: ## Stop the stack, keep its volumes
	$(call run,$(COMPOSE) down)

docker-ps: ## Show the containers and their health
	$(call run,$(COMPOSE) ps -a)

docker-logs: ## Follow the logs (s=<name>), or print the last n=<lines>
	$(COMPOSE) logs $(if $(n),--no-color --tail $(n),-f) $(s)

docker-reset: ## Stop the stack and delete its volumes (its data)
	printf 'Delete the volumes of the stack, its databases and its bucket? [y/N] ' && read ans && [ "$$ans" = y ]
	$(call run,$(COMPOSE) down -v)

##@ k3d (the local Kubernetes cluster, deploy/kubernetes/k3d.yaml)

k3d-up: ## Create the local Kubernetes cluster
	$(call run,k3d cluster create --config deploy/kubernetes/k3d.yaml $(K3D_ARGS) --wait)

# The current context unset when it was the cluster's, any other left as is.
k3d-down: ## Delete the cluster and everything on it
	current="$$(kubectl config current-context 2>/dev/null || true)"; \
	k3d cluster delete $(CLUSTER); \
	if [ "$$current" = $(CONTEXT) ]; then kubectl config unset current-context; fi; \
	echo

##@ Kubernetes (deploy/kubernetes/.env, else the environment)

k8s-check: ## Check the values, then build and validate the charts
	$(call run,bash deploy/kubernetes/scripts/check.sh)

k8s-up: ## Check, import the images into k3d, apply and wait
	$(call run,bash deploy/kubernetes/scripts/prepare.sh)

k8s-down: ## Stop the stack, keep its disks, Secret and ConfigMap
	$(call run,$(KUBECTL) scale deployment --all --replicas=0)

k8s-ps: ## Show the pods, their state and the last events
	$(call run,$(KUBECTL) get pods)
	$(call run,$(KUBECTL) get events --sort-by=.lastTimestamp | tail -20)

# Without s, every container of the stack, by its part-of label.
k8s-logs: ## Follow the logs (s=<name>), or print the last n=<lines>
	$(KUBECTL) logs $(if $(n),--tail $(n),-f) \
		$(if $(s),deployment/$(s),-l app.kubernetes.io/part-of=madmp --all-containers --prefix --max-log-requests 20)

k8s-reset: ## Delete the stack and its disks (its data)
	printf 'Delete the namespace $(STACK_NAME) and its disks? [y/N] ' && read ans && [ "$$ans" = y ]
	echo "Deleting, returns once everything is gone..."
	$(call run,kubectl --context $(CONTEXT) delete namespace $(STACK_NAME) --ignore-not-found --timeout=5m)

##@ Tests

test-all: test-unit test-integration ## Run every test: unit, then integration

test-unit: ## Run the tests that need only the repository
	$(call run,$(RUN) pytest tests/unit -q)

test-integration: ## Run the tests that need a PostgreSQL (docker)
	$(call run,$(RUN) pytest tests/integration -q)

##@ CI

ci: lint pre-commit validate-all packages-generate test-all docker-check k8s-check ## Everything the CI checks, in this order

##@ Cleanup

clean: ## Remove the Python caches (__pycache__)
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
	$(call run,echo "Cleaning Done.")
