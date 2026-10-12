#!/usr/bin/env bash
set -euo pipefail

# 12 ядер / 30 ГБ на хосте — отдаём кластеру с запасом под будущий
# Prometheus/Loki/Jaeger/Grafana/Alertmanager/Karma.
minikube start --driver=docker --cpus=6 --memory=12g --disk-size=30g
kubectl get nodes
