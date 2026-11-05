#!/usr/bin/env bash
# Starts the stack under docker compose, on this machine or on the docker host
# DOCKER_HOST names, its images already there or pulled, never built. Safe to
# re-run.
#
#   bash deploy/docker/scripts/deploy.sh
#
#   1. the values and the compose file checked, stopping at the first error
#   2. start the stack and wait until every service is healthy: the servers
#      and their databases and bucket, then the DMP database migrated and
#      synced before the DMP API, and DSW
#   3. summary, and whether DSW's demo accounts still log in
#
# Sourced, it skips step 1: the values are those of the script that sources
# it.

set -euo pipefail

# --- 1. Check ---------------------------------------------------------------
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  # shellcheck source-path=SCRIPTDIR source=check.sh
  source "$(dirname "${BASH_SOURCE[0]}")/check.sh"
fi

# --- 2. Start ---------------------------------------------------------------
# --wait returns once every healthcheck passes, and fails when a service
# exits with an error: the services that wait for it are not started. A
# container whose image changed is recreated.
echo ""
echo "Starting the stack..."
if ! compose up -d --wait; then
  echo "" >&2
  echo "error: the stack did not come up. What each service did:" >&2
  echo "  docker compose -p $STACK_NAME ps -a" >&2
  echo "  docker compose -p $STACK_NAME logs <service>" >&2
  exit 1
fi

# --- 3. Summary -------------------------------------------------------------
echo ""
echo "The stack is up."
echo "  Client         $DSW_CLIENT_URL"
echo "  API            $DSW_API_URL"
echo "  DMP API        http://$(compose port dmp-api 8081)/dmps/<key>, with DMP_READ_TOKEN or DMP_WRITE_TOKEN"

# The demo accounts DSW opens with, asked for a token. 201: they log in. 400
# or 401: the API refuses them. Anything else: asked again, for up to 30 s.
for attempt in 1 2 3 4 5 6 7; do
  code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST "$DSW_API_URL/tokens" \
    -H 'Content-Type: application/json' \
    -d '{"email":"albert.einstein@example.com","password":"password"}' || true)"
  case "$code" in
    201)
      echo ""
      echo "(!) The demo accounts still open DSW: albert.einstein@example.com / password"
      echo "    make dsw-admin creates DSW_USER, then deletes them."
      break ;;
    400 | 401) break ;;
  esac
  [ "$attempt" -eq 7 ] || sleep 5
done
echo ""
