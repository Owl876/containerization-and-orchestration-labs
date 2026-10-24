#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/06-broken-rollback.txt") 2>&1
date -Is
revision=$(helm history shop -n shop -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)[-1]["revision"])')
python3 "$LAB_DIR/scripts/watch-health.py" > "$LAB_DIR/report/evidence/06-health.txt" &
health_pid=$!
restore() {
  helm rollback shop "$revision" -n shop --wait --timeout 4m
  kill "$health_pid" 2>/dev/null || true
}
trap restore EXIT
# Do not use --atomic: the blocked rollout must be observed before manual rollback.
shop_upgrade -f "$LAB_DIR/experiments/broken.yaml"
if kubectl rollout status deployment/shop-api -n shop --timeout=140s; then
  echo 'FAIL: unhealthy rollout unexpectedly succeeded'; exit 1
fi
kubectl get deployment,rs,pods -n shop
bad_pod=$(kubectl get pods -n shop -l app.kubernetes.io/name=api -o json | python3 -c 'import json,sys; print(next(p["metadata"]["name"] for p in json.load(sys.stdin)["items"] if any(e.get("name")=="HEALTH_FAIL" and e.get("value")=="true" for e in p["spec"]["containers"][0].get("env",[]))))')
kubectl get events -n shop --field-selector "involvedObject.name=$bad_pod" --sort-by=.lastTimestamp
kubectl get deployment shop-api -n shop -o json > "$LAB_DIR/.state/broken-deploy.json"
python3 - "$LAB_DIR/.state/broken-deploy.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d['status']['availableReplicas'] >= d['spec']['replicas']
assert any(c['type']=='Progressing' and c['reason']=='ProgressDeadlineExceeded' for c in d['status']['conditions'])
print('PASS: failed rollout, old replicas remain available.')
PY
helm rollback shop "$revision" -n shop --wait --timeout 4m
kill "$health_pid"
wait "$health_pid"
trap - EXIT
cat "$LAB_DIR/report/evidence/06-health.txt"
curl -fsS "$API_URL/health"
helm history shop -n shop
echo 'PASS: broken rollout blocked; manual rollback restored the deployment.'
