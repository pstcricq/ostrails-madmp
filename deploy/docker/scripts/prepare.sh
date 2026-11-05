#!/usr/bin/env bash
# Prepares this machine for the stack, then starts it. Safe to re-run.
#
#   1. the values and the compose file checked, stopping at the first error
#   2. the madmp image built from this checkout, under MADMP_IMAGE:MADMP_TAG
#   3. the stack started, on the values checked here

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

# shellcheck source-path=SCRIPTDIR source=check.sh
source deploy/docker/scripts/check.sh

# --- 2. Image ---------------------------------------------------------------
# From Docker's cache when the checkout has not changed, without provenance
# attestation: an unchanged checkout gives the same image id.
echo ""
echo "Building the madmp image ($MADMP_IMAGE:$MADMP_TAG)..."
docker build -q --provenance=false -f Dockerfile -t "$MADMP_IMAGE:$MADMP_TAG" . > /dev/null

# --- 3. Deploy --------------------------------------------------------------
# shellcheck source-path=SCRIPTDIR source=deploy.sh
source deploy/docker/scripts/deploy.sh
