#!/usr/bin/env bash
set -euo pipefail

echo ">>> helm upgrade panda-api (накатываем PrometheusRule)"
helm upgrade panda-api charts/panda-api

echo ">>> ждём, пока Prometheus Operator подхватит правило"
sleep 10
kubectl get prometheusrule panda-api -o yaml | grep -A2 "alert:"

echo ">>> ставим Karma"
helm repo add karma https://zekker6.github.io/helm-charts/
helm repo update
helm install karma karma/karma -n monitoring \
  --set env.ALERTMANAGER_URI="http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093"

kubectl get pods -n monitoring -l app.kubernetes.io/name=karma -w
