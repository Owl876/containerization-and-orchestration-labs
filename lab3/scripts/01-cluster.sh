#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
if ! kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
  kind create cluster --name "$CLUSTER_NAME" --config "$LAB_DIR/cluster/kind.yaml" --wait 180s
else
  kind export kubeconfig --name "$CLUSTER_NAME" --kubeconfig "$KUBECONFIG"
fi
check_context
# Docker Desktop's VM may have no direct external DNS/network access (VPN).
# Its built-in HTTP proxy resolves registry names on the host side.
if [[ $(docker context show) == desktop-linux ]]; then
  for node in $(kind get nodes --name "$CLUSTER_NAME"); do
    docker exec "$node" sh -c 'mkdir -p /etc/systemd/system/containerd.service.d
cat > /etc/systemd/system/containerd.service.d/proxy.conf <<"EOF"
[Service]
Environment="HTTP_PROXY=http://http.docker.internal:3128"
Environment="HTTPS_PROXY=http://http.docker.internal:3128"
Environment="NO_PROXY=localhost,127.0.0.1,10.96.0.0/12,10.244.0.0/16,172.18.0.0/16,.svc,.cluster.local"
EOF
systemctl daemon-reload
systemctl restart containerd'
  done
fi
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl get nodes -o wide
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update
