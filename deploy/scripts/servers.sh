#!/usr/bin/env bash
# The servers a target's stack runs itself, read from their addresses. Sourced
# from the repository root, the values exported:
#
#   source deploy/scripts/servers.sh
#
#   dmp-database  the PostgreSQL server of the DMPs, when DMP_HOST is
#                 dmp-postgres
#   dsw-database  the PostgreSQL server of DSW, when DSW_DB_HOST is
#                 dsw-postgres
#   storage       the S3 server and its bucket, when the host of S3_URL is
#                 minio
#
# Any other address is a server of the target. DMP_PORT and DSW_DB_PORT are
# numbers, the ports the stack's servers listen on when it runs them. SERVERS
# lists the servers the stack runs, space-separated.
#
# Every error is printed at once, and stops the caller.

errors=()
for key in DMP_PORT DSW_DB_PORT; do
  case "${!key}" in
    '' | *[!0-9]*) errors+=("$key is ${!key}, not a port number") ;;
  esac
done
if [ ${#errors[@]} -gt 0 ]; then
  echo "" >&2
  printf 'error: %s\n' "${errors[@]}" >&2
  exit 1
fi

# The host of S3_URL: no scheme, no path, no port.
s3_host="${S3_URL#*://}"
s3_host="${s3_host%%/*}"
s3_host="${s3_host%%:*}"

SERVERS=""
[ "$DMP_HOST" != dmp-postgres ] || SERVERS="$SERVERS dmp-database"
[ "$DSW_DB_HOST" != dsw-postgres ] || SERVERS="$SERVERS dsw-database"
[ "$s3_host" != minio ] || SERVERS="$SERVERS storage"
SERVERS="${SERVERS# }"
