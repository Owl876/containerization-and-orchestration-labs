#!/usr/bin/env bash
set -euo pipefail
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$LAB_DIR/.tools:$PATH"
# Keep credentials, Helm downloads and tools inside the ignored task directory.
export KUBECONFIG="${LAB3_KUBECONFIG:-$LAB_DIR/.state/kubeconfig}"
export HELM_CACHE_HOME="$LAB_DIR/.state/helm/cache"
export HELM_CONFIG_HOME="$LAB_DIR/.state/helm/config"
export HELM_DATA_HOME="$LAB_DIR/.state/helm/data"
mkdir -p "$LAB_DIR/.state" "$LAB_DIR/report/evidence"
CLUSTER_NAME=${LAB3_CLUSTER_NAME:-lab3}
API_URL=${LAB3_API_URL:-http://127.0.0.1:18000}
WORKER_URL=${LAB3_WORKER_URL:-http://127.0.0.1:18001}
PROM_URL=${LAB3_PROM_URL:-http://127.0.0.1:19090}
export API_URL WORKER_URL PROM_URL

check_context() {
  local context
  context=$(kubectl config current-context)
  if [[ "$context" != "kind-$CLUSTER_NAME" ]]; then
    echo "Expected kind-$CLUSTER_NAME; current context is $context. Refusing experiment." >&2
    exit 1
  fi
}

shop_upgrade() {
  helm upgrade shop "$LAB_DIR/charts/shop" -n shop --reuse-values "$@"
}
