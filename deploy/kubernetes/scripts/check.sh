#!/usr/bin/env bash
# Checks the stack on Kubernetes.
#
#   bash deploy/kubernetes/scripts/check.sh
#
#   1. the values, with deploy/kubernetes/.env when the file exists, then the
#      servers the stack runs itself
#   2. the template filled in a copy of the charts, removed on exit: the
#      components of the servers the stack does not run left out, every hole
#      filled, none a secret
#   3. the stack built by kustomize, no placeholder left
#   4. each object against the Kubernetes schema of its kind, at the version
#      of the k3d cluster (kubeconform -strict), the schemas downloaded into
#      the copy
#
# Sourced, it leaves the values exported, and STACK, the file of the objects
# checked.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

# The Kubernetes version of the k3s image of deploy/kubernetes/k3d.yaml
# (rancher/k3s:v1.30.10-k3s1 -> 1.30.10).
KUBERNETES_VERSION="$(sed -n 's|^image: rancher/k3s:v\([0-9.]*\)-k3s.*|\1|p' deploy/kubernetes/k3d.yaml)"
if [ -z "$KUBERNETES_VERSION" ]; then
  echo "error: no rancher/k3s image in deploy/kubernetes/k3d.yaml" >&2
  exit 1
fi

# --- 1. Values --------------------------------------------------------------
# shellcheck source-path=SCRIPTDIR source=../../scripts/values.sh
source deploy/scripts/values.sh deploy/kubernetes/.env
# shellcheck source-path=SCRIPTDIR source=../../scripts/servers.sh
source deploy/scripts/servers.sh

# The tools of the steps below. On macOS: brew install kubectl gettext
# (envsubst) kubeconform.
for tool in kubectl envsubst curl kubeconform; do
  if ! command -v "$tool" > /dev/null; then
    echo "error: $tool not found, needed by this check" >&2
    exit 1
  fi
done

echo ""
echo "Checks"
printf '  %-29s %s\n' values "$VALUES_SUMMARY"
printf '  %-29s %s\n' servers "run by the stack: ${SERVERS:-none}"

COPY="$(mktemp -d)"
trap 'rm -rf "$COPY"' EXIT
cp -R deploy/kubernetes/charts "$COPY/charts"
TEMPLATES="$COPY/charts/templates"

# The servers the stack does not run itself, out of the copy's components:
# their objects are not built.
for server in dmp-database dsw-database storage; do
  case " $SERVERS " in
    *" $server "*) ;;
    *)
      grep -vx "  - components/$server" "$COPY/charts/kustomization.yaml" > "$COPY/kustomization.yaml"
      mv "$COPY/kustomization.yaml" "$COPY/charts/kustomization.yaml"
      ;;
  esac
done

# --- 2. Template ------------------------------------------------------------
# The host of a URL: no scheme, no path, no port.
host_of() {
  local rest="${1#*://}"
  rest="${rest%%/*}"
  printf '%s' "${rest%%:*}"
}
# The port of a URL: the one written, else its scheme's.
port_of() {
  local rest="${1#*://}"
  rest="${rest%%/*}"
  case "$rest" in
    *:*) printf '%s' "${rest##*:}" ;;
    *) case "$1" in https://*) printf 443 ;; *) printf 80 ;; esac ;;
  esac
}
# Each ingress on the host of its URL. MinIO's Service on the port of S3_URL,
# where the pods reach it as the browser does.
INGRESS_CLIENT_HOST="$(host_of "$DSW_CLIENT_URL")"
INGRESS_API_HOST="$(host_of "$DSW_API_URL")"
INGRESS_S3_HOST="$(host_of "$S3_URL")"
S3_PORT="$(port_of "$S3_URL")"
export INGRESS_CLIENT_HOST INGRESS_API_HOST INGRESS_S3_HOST S3_PORT

# The holes of the template. A secret among them stops the check.
# shellcheck disable=SC2016 # the characters $ { } removed
HOLES="$(grep -ohE '\$\{[A-Z][A-Z0-9_]*\}' "$TEMPLATES"/*.yaml | tr -d '${}' | sort -u)"
secrets=""
missing=""
for hole in $HOLES; do
  if is_in "$hole" "$SECRET_KEYS"; then
    secrets="$secrets $hole"
  fi
  [ -n "${!hole:-}" ] || missing="$missing $hole"
done
if [ -n "$secrets" ] || [ -n "$missing" ]; then
  echo "" >&2
  [ -z "$secrets" ] || echo "error: secrets in the template, they would land in the ConfigMap:$secrets" >&2
  [ -z "$missing" ] || echo "error: no value for:$missing" >&2
  exit 1
fi

# envsubst replaces the listed holes only, from its environment.
# shellcheck disable=SC2016,SC2086 # a literal list of names, one per hole
list="$(printf '${%s} ' $HOLES)"
for template in "$TEMPLATES"/*.yaml; do
  envsubst "$list" < "$template" > "$template.filled"
  mv "$template.filled" "$template"
done
printf '  %-29s %s\n' template "$(printf '%s\n' "$HOLES" | wc -l | tr -d ' ') holes filled"

# --- 3. Build ---------------------------------------------------------------
STACK="$COPY/stack.yaml"
if ! problems="$(kubectl kustomize "$COPY/charts" 2>&1 > "$STACK")"; then
  echo "" >&2
  echo "error: the stack does not build:" >&2
  printf '%s\n' "$problems" | sed 's/^/  /' >&2
  exit 1
fi
if grep -q placeholder "$STACK"; then
  echo "" >&2
  echo "error: placeholders left, at these lines of the built stack:" >&2
  grep -n placeholder "$STACK" | cut -d: -f1 | tr '\n' ' ' | sed 's/^/  /' >&2
  echo "" >&2
  exit 1
fi
printf '  %-29s %s\n' build "$(grep -c '^kind:' "$STACK") objects, no placeholder left"

# --- 4. Schema --------------------------------------------------------------
# The schema of each kind of object built, downloaded once, one at a time,
# under the name kubeconform looks for: the kind in lower case, then the first
# label of the API group if any, then the version (Deployment apps/v1 ->
# deployment-apps-v1, Service v1 -> service-v1). Each download gives up after
# 30 s and is tried 3 more times.
SCHEMAS="https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/v$KUBERNETES_VERSION-standalone-strict"
mkdir "$COPY/schemas"
names="$(awk '
  /^---/        { api = ""; kind = "" }
  /^apiVersion:/ { api = $2 }
  /^kind:/       { kind = $2 }
  api != "" && kind != "" {
    n = split(api, part, "/")
    if (n == 2) { split(part[1], group, "."); suffix = "-" group[1] "-" part[2] }
    else        { suffix = "-" part[1] }
    print tolower(kind) suffix
    api = ""; kind = ""
  }' "$STACK" | sort -u)"
for name in $names; do
  if ! problem="$(curl -fsS --max-time 30 --retry 3 -o "$COPY/schemas/$name.json" "$SCHEMAS/$name.json" 2>&1)"; then
    echo "" >&2
    echo "error: the schema $name could not be downloaded from $SCHEMAS/$name.json:" >&2
    printf '%s\n' "$problem" | sed 's/^/  /' >&2
    exit 1
  fi
done

# kubeconform reads the downloaded schemas only, never the network.
# shellcheck disable=SC2016 # kubeconform's template, not a shell variable
if ! report="$(kubeconform -strict -summary \
                 -schema-location "$COPY/schemas/{{ .ResourceKind }}{{ .KindSuffix }}.json" \
                 "$STACK" 2>&1)"; then
  echo "" >&2
  echo "error: objects that do not match Kubernetes $KUBERNETES_VERSION:" >&2
  printf '%s\n' "$report" | sed 's/^/  /' >&2
  exit 1
fi
printf '  %-29s %s\n' schema "$(printf '%s\n' "$report" | sed -n 's/.*Valid: \([0-9]*\).*/\1/p') objects valid for Kubernetes $KUBERNETES_VERSION ($(printf '%s\n' "$names" | wc -l | tr -d ' ') schemas)"
