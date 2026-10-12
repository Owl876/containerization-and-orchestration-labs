#!/usr/bin/env bash
set -euo pipefail

echo ">>> пересобираем образ моста с httpx[socks]"
cd telegram-bridge
minikube image build -t telegram-bridge:local .
cd ..

echo ">>> перекатываем мост (чтобы подхватил новый образ и TELEGRAM_PROXY_URL)"
helm upgrade telegram-bridge charts/telegram-bridge -n monitoring
kubectl -n monitoring rollout restart deployment/telegram-bridge
kubectl -n monitoring rollout status deployment/telegram-bridge

echo ">>> накатываем Alertmanager с proxy_url в telegram_configs"
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f observability/kube-prometheus-stack-values.yaml

echo ">>> готово, жди пока alertmanager перекатится"
kubectl get pods -n monitoring -l app.kubernetes.io/name=alertmanager -w
