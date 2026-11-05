#!/usr/bin/env bash
# Deploys the stack on the cluster a context of kubectl names, in the
# namespace STACK_NAME, which exists already, the images pulled by the cluster
# or already there. Safe to re-run.
#
#   bash deploy/kubernetes/scripts/deploy.sh <context>
#
#   1. the values and the charts checked, stopping at the first error; the
#      stack checked is the one applied
#   2. the context and the namespace STACK_NAME
#   3. the Secret madmp-secrets
#   4. apply the stack; the Deployments that read a changed secret restarted
#   5. wait until every pod is ready, create-bucket done; a
#      Deployment that fails goes back to its previous version
#   6. summary, and whether DSW's demo accounts still log in
#
# Sourced, it skips step 1: the values and the stack are those of the script
# that sources it.

set -euo pipefail

# Named, never the current context of kubectl.
if [ -z "${1:-}" ]; then
  echo "usage: bash deploy/kubernetes/scripts/deploy.sh <context of kubectl>" >&2
  exit 1
fi
CONTEXT="$1"
k() { kubectl --context "$CONTEXT" "$@"; }

# --- 1. Check ---------------------------------------------------------------
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  # shellcheck source-path=SCRIPTDIR source=check.sh
  source "$(dirname "${BASH_SOURCE[0]}")/check.sh"
fi

# --- 2. Target --------------------------------------------------------------
NS="$STACK_NAME"
if ! k get namespace "$NS" > /dev/null 2>&1; then
  echo "" >&2
  echo "error: no namespace $NS on $CONTEXT (created by prepare.sh on k3d, provided by the cluster otherwise)" >&2
  exit 1
fi

# The label every object of the stack carries, read from the charts: it
# lists the Deployments of the stack among those of the namespace.
PART_OF="$(sed -n 's|^ *app\.kubernetes\.io/part-of: *\(..*\)|\1|p' deploy/kubernetes/charts/kustomization.yaml)"
if [ -z "$PART_OF" ]; then
  echo "error: no label app.kubernetes.io/part-of in deploy/kubernetes/charts/kustomization.yaml" >&2
  exit 1
fi
SELECTOR="app.kubernetes.io/part-of=$PART_OF"

# --- 3. Secret --------------------------------------------------------------
# The secrets of the examples (SECRET_KEYS), written to kubectl's stdin,
# base64 encoded.
b64() { printf '%s' "$1" | base64 | tr -d '\n'; }
echo ""
echo "Secret:"

# The keys whose value changes, compared with the cluster before the Secret is
# replaced. None on a first deployment.
changed=""
if k -n "$NS" get secret madmp-secrets > /dev/null 2>&1; then
  for key in $SECRET_KEYS; do
    current="$(k -n "$NS" get secret madmp-secrets -o jsonpath="{.data.$key}")"
    [ "$current" = "$(b64 "${!key}")" ] || changed="$changed $key"
  done
fi

{
  printf 'apiVersion: v1\nkind: Secret\nmetadata:\n  name: madmp-secrets\n'
  printf '  namespace: %s\n  labels:\n    app.kubernetes.io/part-of: %s\n' "$NS" "$PART_OF"
  printf 'type: Opaque\ndata:\n'
  for key in $SECRET_KEYS; do
    printf '  %s: %s\n' "$key" "$(b64 "${!key}")"
  done
} | k apply -f - | sed 's/^/  /'
[ -z "$changed" ] || echo "  changed:$changed"

# With a PostgreSQL server of the stack, a changed password of its account is
# said: the server keeps the one it was created with.
for pair in dmp-database:DMP_PASSWORD dsw-database:DSW_DB_PASSWORD; do
  case " $SERVERS " in *" ${pair%%:*} "*) ;; *) continue ;; esac
  case " $changed " in
    *" ${pair#*:} "*)
      echo ""
      echo "(!) ${pair#*:} changed, its database still has the old one: change"
      echo "    it there too (ALTER USER), or the stack cannot connect."
      ;;
  esac
done

# --- 4. Apply ---------------------------------------------------------------
# The revision of each Deployment before the apply, against the one after
# (step 5): the Deployments this run changed.
revision() {
  k -n "$NS" get deployment "$1" \
    -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' 2>/dev/null
}
revisions_before=""
for name in $(k -n "$NS" get deployments -l "$SELECTOR" -o jsonpath='{.items[*].metadata.name}'); do
  revisions_before="$revisions_before $name=$(revision "$name")"
done

echo ""
echo "Applying the stack checked above:"
# The previous Jobs deleted first.
k -n "$NS" delete job create-bucket --ignore-not-found > /dev/null
k -n "$NS" apply -f "$STACK" | sed 's/^/  /'

# The Deployments that read a changed key of madmp-secrets, in a container or
# an init container, restarted.
if [ -n "$changed" ]; then
  k -n "$NS" get deployments -l "$SELECTOR" -o jsonpath='{range .items[*]}{.metadata.name}{" "}{range .spec.template.spec.initContainers[*].env[*]}{.valueFrom.secretKeyRef.key}{" "}{end}{range .spec.template.spec.containers[*].env[*]}{.valueFrom.secretKeyRef.key}{" "}{end}{"\n"}{end}' |
  while read -r name keys; do
    for key in $changed; do
      case " $keys " in
        *" $key "*)
          k -n "$NS" rollout restart "deployment/$name" > /dev/null
          echo "  deployment.apps/$name restarted, reads $key"
          break ;;
      esac
    done
  done
fi

# --- 5. Wait ----------------------------------------------------------------
# Each Deployment has 10 minutes to roll out, counted from the apply
# (progressDeadlineSeconds). A Deployment this run changed and that fails goes
# back to its previous version (`rollout undo`). One it did not change is
# waited for again once the rollbacks are done. The Secret and the ConfigMap
# stay as applied, the previous ConfigMaps too, until the namespace is
# deleted.

# Whether a Deployment rolled out, `rollout status` tried 3 times: a watch the
# API server cuts ends one early. Its last error stays in rollout_error.
rolled_out() {
  for _ in 1 2 3; do
    if rollout_error="$(k -n "$NS" rollout status "$1" --timeout=600s 2>&1 > /dev/null)"; then
      return 0
    fi
  done
  return 1
}

echo ""
echo "Waiting:"
failed=""
for deployment in $(k -n "$NS" get deployments -l "$SELECTOR" -o name); do
  if rolled_out "$deployment"; then
    echo "  ${deployment#*/} ready"
  else
    echo "  ${deployment#*/} NOT READY: ${rollout_error##*$'\n'}"
    failed="$failed ${deployment#*/}"
  fi
done

if [ -n "$failed" ]; then
  echo ""
  echo "Rolling back:"
  culprits=""
  unchanged=""
  for name in $failed; do
    before=""
    for pair in $revisions_before; do
      [ "${pair%%=*}" != "$name" ] || before="${pair#*=}"
    done
    if [ "$before" = "$(revision "$name")" ]; then
      unchanged="$unchanged $name"
      continue
    fi
    culprits="$culprits $name"
    if [ -z "$before" ]; then
      echo "  $name: new, no previous version to go back to"
    elif ! k -n "$NS" rollout undo "deployment/$name" > /dev/null 2>&1; then
      echo "  $name: the rollback was refused"
    elif rolled_out "deployment/$name"; then
      echo "  $name: back to its previous version"
    else
      echo "  $name: its previous version does not come up either"
    fi
  done
  for name in $unchanged; do
    if rolled_out "deployment/$name"; then
      echo "  $name: unchanged, ready again"
    else
      echo "  $name: unchanged, still not ready"
      culprits="$culprits $name"
    fi
  done
  echo "" >&2
  echo "error: failed to roll out:$culprits. The events of the failed version, and the stack's logs:" >&2
  echo "  kubectl --context $CONTEXT -n $NS get events --sort-by=.lastTimestamp" >&2
  echo "  kubectl --context $CONTEXT -n $NS logs -l $SELECTOR --all-containers --prefix" >&2
  exit 1
fi

# The Job deletes itself a minute after it succeeds: absent, done.
if k -n "$NS" get job create-bucket > /dev/null 2>&1; then
  if ! k -n "$NS" wait --for=condition=complete job/create-bucket --timeout=120s > /dev/null 2>&1; then
    echo "error: create-bucket failed, see: kubectl --context $CONTEXT -n $NS logs job/create-bucket" >&2
    exit 1
  fi
fi
echo "  create-bucket done"

# --- 6. Summary -------------------------------------------------------------
echo ""
echo "The stack is up on $CONTEXT, namespace $NS."
echo "  Client         $DSW_CLIENT_URL"
echo "  API            $DSW_API_URL"
echo "  DMP API        $DMP_API_URL/dmps/<key>, with DMP_READ_TOKEN or DMP_WRITE_TOKEN"

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
