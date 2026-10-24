#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
# Restore the lab2 stack only if there is no Prometheus Operator on this cluster.
if kubectl get prometheus -A -o name 2>/dev/null | grep -q '^prometheus.monitoring.coreos.com/'; then
  echo 'Existing Prometheus instance found; reusing the lab2 stack.'
  exit 0
fi
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 69.8.2 -n monitoring --create-namespace \
  -f "$LAB_DIR/../lab2-observability/observability/kube-prometheus-stack-values.yaml" \
  -f "$LAB_DIR/cluster/monitoring-values.yaml" --wait --timeout 12m
