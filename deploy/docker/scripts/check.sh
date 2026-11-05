#!/usr/bin/env bash
# Checks the stack under docker compose.
#
#   bash deploy/docker/scripts/check.sh
#
#   1. the values, with deploy/docker/.env when the file exists, then the
#      servers the stack runs itself, as the compose profiles of
#      COMPOSE_PROFILES
#   2. docker compose reads docker-compose.yml with them
#
# Sourced, it leaves the values exported, and the function compose.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

# --- 1. Values --------------------------------------------------------------
# shellcheck source-path=SCRIPTDIR source=../../scripts/values.sh
source deploy/scripts/values.sh deploy/docker/.env
# shellcheck source-path=SCRIPTDIR source=../../scripts/servers.sh
source deploy/scripts/servers.sh
export COMPOSE_PROFILES="${SERVERS// /,}"

# The tool of the step below.
if ! command -v docker > /dev/null; then
  echo "error: docker not found, needed by this check" >&2
  exit 1
fi

# --- 2. Compose -------------------------------------------------------------
# docker compose on this stack, the values from the environment.
compose() { docker compose -f deploy/docker/docker-compose.yml "$@"; }

echo ""
echo "Checks"
printf '  %-29s %s\n' values "$VALUES_SUMMARY"
printf '  %-29s %s\n' servers "run by the stack: ${SERVERS:-none}"
if ! problems="$(compose config --quiet 2>&1)"; then
  echo "" >&2
  echo "error: docker compose cannot read docker-compose.yml with these values:" >&2
  printf '%s\n' "$problems" | sed 's/^/  /' >&2
  exit 1
fi
printf '  %-29s %s\n' compose "docker-compose.yml reads with these values"
