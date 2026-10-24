#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
for version in 1.0.0 1.1.0; do
  docker build --build-arg "APP_VERSION=$version" -t "registry.local/shop/app:$version" "$LAB_DIR/app"
  kind load docker-image --name "$CLUSTER_NAME" "registry.local/shop/app:$version"
done
helm lint "$LAB_DIR/charts/shop"
helm upgrade --install shop "$LAB_DIR/charts/shop" -n shop --create-namespace --wait --timeout 10m
kubectl wait -n shop --for=condition=Ready cluster/shop-db --timeout=180s
kubectl get pods,svc,cluster -n shop
curl -fsS "$API_URL/health"
curl -fsS -X POST "$API_URL/order" -H 'Content-Type: application/json' -d '{"item":"bamboo","quantity":3}'
curl -fsS "$API_URL/orders"
