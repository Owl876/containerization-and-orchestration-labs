#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/07-control-plane.txt") 2>&1
date -Is
node="$CLUSTER_NAME-control-plane"
# Move the static manifest out of kubelet's watched directory. Stopping only
# the container would let kubelet restart it, invalidating the experiment.
restore() {
  docker exec "$node" sh -c 'if [ -f /tmp/lab3-kube-apiserver.yaml ]; then mv /tmp/lab3-kube-apiserver.yaml /etc/kubernetes/manifests/kube-apiserver.yaml; fi'
}
trap restore EXIT
docker exec "$node" mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/lab3-kube-apiserver.yaml
for attempt in $(seq 1 45); do
  if ! kubectl --request-timeout=2s get --raw=/readyz >/dev/null 2>&1; then break; fi
  sleep 1
done
if kubectl --request-timeout=2s get nodes; then
  echo 'FAIL: apiserver still running'; exit 1
fi
if kubectl --request-timeout=3s -n shop annotate deployment/shop-api lab3-control-plane=down --overwrite; then
  echo 'FAIL: mutation was accepted'; exit 1
fi
marker="control-plane-down-$(date +%s)"
for attempt in $(seq 1 5); do
  printf 'API health: '; curl -fsS --max-time 5 "$API_URL/health"; echo
  printf 'Worker health: '; curl -fsS --max-time 5 "$WORKER_URL/health"; echo
  curl -fsS --max-time 5 -X POST "$API_URL/order" -H 'Content-Type: application/json' -d "{\"item\":\"$marker\",\"quantity\":1}"
  sleep 2
done
curl -fsS "$API_URL/orders" > "$LAB_DIR/report/evidence/07-orders-during-outage.json"
python3 - "$LAB_DIR/report/evidence/07-orders-during-outage.json" "$marker" <<'PY'
import json,sys
rows=json.load(open(sys.argv[1]))
new=[r for r in rows if r['item']==sys.argv[2]]
assert len(new)==5 and all(r['status']=='processed' for r in new)
print('PASS: new orders written to PostgreSQL and processed during the outage.')
PY
restore
trap - EXIT
for attempt in $(seq 1 60); do
  kubectl --request-timeout=2s get --raw=/readyz >/dev/null 2>&1 && break
  sleep 2
done
kubectl wait --for=condition=Ready nodes --all --timeout=180s
# Admission controllers also reconnect/re-elect leaders after the API outage.
# An API /readyz response alone does not prove mutations are accepted yet.
manageable=false
for attempt in $(seq 1 45); do
  if kubectl --request-timeout=5s -n shop annotate deployment/shop-api lab3-control-plane=restored --overwrite; then
    manageable=true
    break
  fi
  sleep 2
done
[[ "$manageable" == true ]]
kubectl get pods -n shop
date -Is
echo 'PASS: apiserver restored, management works again.'
