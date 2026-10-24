#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/03-reconciliation.txt") 2>&1
date -Is
echo 'API: delete one Pod and wait for a different UID'
selector='app.kubernetes.io/name=api,app.kubernetes.io/instance=shop'
kubectl get pods -n shop -l "$selector" -o wide
pod=$(kubectl get pods -n shop -l "$selector" -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod -n shop "$pod" --wait=true
kubectl rollout status -n shop deployment/shop-api --timeout=180s
kubectl get pods -n shop -l "$selector" -o wide
echo 'Scale via values overlay: 3 -> 4 -> 3'
shop_upgrade -f "$LAB_DIR/experiments/scale.yaml" --wait --timeout 3m
kubectl rollout status -n shop deployment/shop-api --timeout=180s
kubectl get deployment shop-api -n shop
[[ $(kubectl get deployment shop-api -n shop -o jsonpath='{.status.availableReplicas}') == 4 ]]
shop_upgrade --set api.replicas=3 --wait --timeout 3m
kubectl rollout status -n shop deployment/shop-api --timeout=180s
echo 'PostgreSQL: data must survive deletion and recovery'
curl -fsS -X POST "$API_URL/order" -H 'Content-Type: application/json' -d '{"item":"persistent-bamboo","quantity":7}'
curl -fsS "$API_URL/orders" > "$LAB_DIR/.state/orders-before.json"
pod=$(kubectl get pods -n shop -l cnpg.io/cluster=shop-db,cnpg.io/podRole=instance -o jsonpath='{.items[0].metadata.name}')
old_uid=$(kubectl get pod -n shop "$pod" -o jsonpath='{.metadata.uid}')
kubectl delete pod -n shop "$pod" --wait=true
for attempt in $(seq 1 60); do
  new_uid=$(kubectl get pod -n shop "$pod" -o jsonpath='{.metadata.uid}' 2>/dev/null || true)
  [[ -n "$new_uid" && "$new_uid" != "$old_uid" ]] && break
  sleep 2
done
kubectl wait -n shop --for=condition=Ready cluster/shop-db --timeout=180s
kubectl wait -n shop --for=condition=Ready pod -l cnpg.io/cluster=shop-db,cnpg.io/podRole=instance --timeout=180s
new_uid=$(kubectl get pod -n shop "$pod" -o jsonpath='{.metadata.uid}')
[[ "$new_uid" != "$old_uid" ]]
echo "PostgreSQL Pod UID: $old_uid -> $new_uid"
curl -fsS "$API_URL/orders" > "$LAB_DIR/.state/orders-after.json"
python3 - "$LAB_DIR/.state/orders-before.json" "$LAB_DIR/.state/orders-after.json" <<'PY'
import json,sys
before,after=(json.load(open(p)) for p in sys.argv[1:])
assert {r['id'] for r in before} <= {r['id'] for r in after}
print('PASS: PostgreSQL recreated, order IDs preserved:', [r['id'] for r in after])
PY
kubectl get cluster shop-db -n shop -o yaml > "$LAB_DIR/report/evidence/04-postgres-cluster.yaml"
kubectl get cluster shop-db -n shop
echo 'PASS: API and database reconciliation, scaling, data persistence.'
