#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/05-rolling-update.txt") 2>&1
date -Is
python3 "$LAB_DIR/scripts/watch-health.py" > "$LAB_DIR/report/evidence/05-health.txt" &
health_pid=$!
kubectl get pods -n shop -l app.kubernetes.io/name=api -w > "$LAB_DIR/report/evidence/05-pods.txt" &
pods_pid=$!
trap 'kill "$health_pid" "$pods_pid" 2>/dev/null || true' EXIT
shop_upgrade -f "$LAB_DIR/experiments/update.yaml" --wait --timeout 4m
kubectl rollout status deployment/shop-api -n shop --timeout=180s
curl -fsS "$API_URL/version"
kill "$health_pid" "$pods_pid"
wait "$health_pid"
wait "$pods_pid" || true
trap - EXIT
cat "$LAB_DIR/report/evidence/05-health.txt"
kubectl get pods -n shop -l app.kubernetes.io/name=api
echo 'PASS: rolling update finished without failed health requests.'
