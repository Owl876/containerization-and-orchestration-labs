#!/usr/bin/env bash
# Часть 7Б: давление по памяти и eviction. Запуск из корня лабы: bash experiments/eviction-demo.sh
# Каждые 10 секунд печатает working set нод (то, с чем kubelet сравнивает порог) и статусы batch,
# в конце — события Evicted, порядок кандидатов из лога kubelet и состояние критических подов.
# Если выселили что-то кроме batch, опыт прерывается и релиз откатывается.
set -euo pipefail
cd "$(dirname "$0")/.."

NODES=$(kubectl get nodes -o name | sed 's|node/||')

echo ">>> ждём, пока с нод слезут taint-ы memory-pressure от прошлых опытов"
until [ -z "$(kubectl get nodes -o jsonpath='{.items[*].spec.taints}')" ]; do sleep 10; done
kubectl delete pods -A --field-selector=status.phase=Failed >/dev/null 2>&1 || true
kubectl delete events -A --field-selector reason=Evicted >/dev/null 2>&1 || true

echo ">>> порог eviction: $(docker exec minikube grep -A1 evictionHard /var/lib/kubelet/config.yaml | tail -1 | sed 's/^ *//; s/"//g; s/:/ </')"
START=$(date -u +%T)
helm upgrade shop charts/shop --reset-values -f experiments/eviction.values.yaml >/dev/null

ws() { kubectl get --raw "/api/v1/nodes/$1/proxy/stats/summary" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['node']['memory']['workingSetBytes']//2**20)"; }

for i in $(seq 1 27); do
  sleep 10
  line=$(printf "t=%3ss" $((i*10)))
  for n in $NODES; do line="$line  $n=$(ws $n)Mi"; done
  st=$(kubectl get pods -l app=batch --no-headers | awk '{print $3}' | sort | uniq -c | tr '\n' ' ')
  echo "$line | $st"
  other=$(kubectl get events -A --field-selector reason=Evicted --no-headers 2>/dev/null | grep -vc shop-batch || true)
  if [ "$other" -gt 0 ]; then echo "!!! выселили не batch, откатываем"; break; fi
done

echo; echo ">>> события Evicted"
kubectl get events -A --field-selector reason=Evicted --sort-by=.lastTimestamp \
  -o custom-columns=NAME:.involvedObject.name,MESSAGE:.message --no-headers | sed 's/Threshold quantity: [0-9]*Ki, //'
echo; echo ">>> кого kubelet ставил в очередь на выселение (первые 5 кандидатов)"
for n in $NODES; do
  echo "--- $n"
  docker exec "$n" journalctl -u kubelet --no-pager --since "$START" 2>/dev/null \
    | grep "pods ranked for eviction" | tail -1 | grep -o 'pods=\[[^]]*' | sed 's/pods=\[//' | tr ',' '\n' | head -5
done
echo; echo ">>> критический путь"
kubectl get pods --no-headers | grep -v batch | awk '{print $1, $2, $3, "restarts="$4}'

helm upgrade shop charts/shop --reset-values >/dev/null
echo; echo ">>> релиз откатан к дефолтам. Failed-поды: kubectl delete pods -A --field-selector=status.phase=Failed"
