#!/usr/bin/env bash
# Prepares the local k3d cluster for the stack, then deploys it. Always the
# k3d cluster of deploy/kubernetes/k3d.yaml, its context k3d-<its name>. Safe
# to re-run.
#
#   1. the values and the charts checked, stopping at the first error
#   2. the k3d cluster exists
#   3. the madmp image built from this checkout, and wizard-server (amd64
#      only), imported into the cluster
#   4. the namespace STACK_NAME
#   5. the DMP API restarted when the madmp image changed
#   6. the stack checked here, deployed on that context

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

# shellcheck source-path=SCRIPTDIR source=check.sh
source deploy/kubernetes/scripts/check.sh

# The name of the cluster in deploy/kubernetes/k3d.yaml (metadata.name).
CLUSTER="$(sed -n 's|^  name: \(..*\)|\1|p' deploy/kubernetes/k3d.yaml)"
if [ -z "$CLUSTER" ]; then
  echo "error: no cluster name in deploy/kubernetes/k3d.yaml" >&2
  exit 1
fi
CONTEXT="k3d-$CLUSTER"
NS="$STACK_NAME"
k() { kubectl --context "$CONTEXT" "$@"; }

# --- 2. Cluster -------------------------------------------------------------
echo ""
if ! k3d cluster list "$CLUSTER" > /dev/null 2>&1; then
  echo "error: no k3d cluster $CLUSTER, run 'make k3d-up' first." >&2
  exit 1
fi

# --- 3. Images --------------------------------------------------------------
# The madmp image, built from this checkout for the machine's own platform,
# from Docker's cache when the checkout has not changed, without provenance
# attestation: an unchanged checkout gives the same image id (step 5).
# wizard-server pulled for amd64, which k3s runs emulated on an ARM machine.
# k3d imports both into the cluster.
madmp="$MADMP_IMAGE:$MADMP_TAG"
echo "Building the madmp image ($madmp)..."
docker build -q --provenance=false -f Dockerfile -t "$madmp" . > /dev/null
server="datastewardshipwizard/wizard-server:$DSW_SERVER_VERSION"
docker pull -q --platform linux/amd64 "$server" > /dev/null
echo "Imported into the cluster:"
k3d image import -c "$CLUSTER" "$madmp" "$server" > /dev/null
echo "  $madmp"
echo "  $server"

# --- 4. Namespace -----------------------------------------------------------
# A namespace being deleted is waited for first.
echo ""
echo "Namespace $NS:"
if [ "$(k get namespace "$NS" -o jsonpath='{.status.phase}' 2>/dev/null)" = "Terminating" ]; then
  echo "  waiting for the previous deletion to end..."
  k wait --for=delete "namespace/$NS" --timeout=300s > /dev/null
fi
k create namespace "$NS" --dry-run=client -o yaml | k apply -f - | sed 's/^/  /'

# --- 5. madmp image ---------------------------------------------------------
# The id of the image the cluster holds under MADMP_IMAGE:MADMP_TAG, read on
# its node, against the id the running DMP API runs: different, the API is
# restarted on the image imported above, prepare-db running again before it.
# No DMP API running yet: it starts on that image.
imported="$(docker exec "k3d-$CLUSTER-server-0" crictl inspecti \
  -o go-template --template '{{.status.id}}' "$madmp")"
running="$(k -n "$NS" get pods -l app=dmp-api \
  -o jsonpath='{.items[0].status.containerStatuses[?(@.name=="dmp-api")].imageID}' 2>/dev/null || true)"
if [ -n "$running" ] && [ "$running" != "$imported" ]; then
  echo ""
  echo "madmp image changed, restarting dmp-api"
  k -n "$NS" rollout restart deployment/dmp-api > /dev/null
fi

# --- 6. Deploy --------------------------------------------------------------
# shellcheck source-path=SCRIPTDIR source=deploy.sh
source deploy/kubernetes/scripts/deploy.sh "$CONTEXT"
