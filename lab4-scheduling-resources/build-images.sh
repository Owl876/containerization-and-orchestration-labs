#!/usr/bin/env bash
# Собирает образы shop-api/shop-worker/shop-batch на control-plane ноде minikube
# и раскладывает их по остальным нодам (minikube image build на multi-node
# кластере грузит образ только на ту ноду, где шла сборка).
# Использование: bash build-images.sh [api worker batch]  (без аргументов — все три)
set -euo pipefail
cd "$(dirname "$0")"

CONTROL_PLANE=minikube
COMPONENTS=("$@")
[ ${#COMPONENTS[@]} -eq 0 ] && COMPONENTS=(api worker batch)

WORKER_NODES=$(kubectl get nodes -o name | sed 's|node/||' | grep -vx "$CONTROL_PLANE" || true)

for comp in "${COMPONENTS[@]}"; do
  img="shop-$comp"
  echo ">>> собираем $img:local"
  minikube image build -t "$img:local" "$comp"
  for node in $WORKER_NODES; do
    echo ">>> $img:local -> $node"
    docker exec "$CONTROL_PLANE" ctr -n k8s.io images export - "docker.io/library/$img:local" \
      | docker exec -i "$node" ctr -n k8s.io images import -
  done
done

echo ">>> образы на нодах:"
for node in $CONTROL_PLANE $WORKER_NODES; do
  echo "--- $node"
  docker exec "$node" crictl images | grep "shop-" || true
done
