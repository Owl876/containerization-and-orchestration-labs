#!/usr/bin/env bash
# Часть 8: нагрузка на путь заказа (POST /orders) ~21 минуту, а поверх неё две перегрузки от batch:
#   1) давление по памяти и eviction (experiments/eviction-demo.sh)
#   2) CPU-перегрузка: 7 реплик batch жгут все ядра нод (максимум, что влезает по requests)
# Запуск из корня лабы: bash experiments/sla-run.sh | tee /tmp/sla-run.log
set -euo pipefail
cd "$(dirname "$0")/.."

export CYCLES="${CYCLES:-3}"            # 3 цикла по 7 минут = 21 минута нагрузки
LOAD_SECONDS=$((CYCLES * 420))
T0=$(date +%s)
mark() { echo; echo "=== $(date -u +%T) UTC (+$(( $(date +%s) - T0 ))с) — $1"; }
sleep_until() { local d=$(( T0 + $1 - $(date +%s) )); [ "$d" -gt 0 ] && sleep "$d" || true; }

helm upgrade shop charts/shop --reset-values >/dev/null
kubectl delete pods -A --field-selector=status.phase=Failed >/dev/null 2>&1 || true

mark "старт нагрузки (CYCLES=$CYCLES), базовая линия без перегрузки"
T0=$(date +%s)
bash loadgen/run.sh >/tmp/loadgen-follow.log 2>&1 &

sleep_until 120
mark "перегрузка 1: eviction по памяти (экран ниже — вывод eviction-demo.sh)"
bash experiments/eviction-demo.sh
mark "eviction-опыт закончен"

mark "ждём, пока с нод слезут taint-ы memory-pressure"
until [ -z "$(kubectl get nodes -o jsonpath='{.items[*].spec.taints}')" ]; do sleep 10; done
mark "перегрузка 2: 7 реплик batch жгут CPU"
helm upgrade shop charts/shop --reset-values --set batch.replicaCount=7 >/dev/null
HOLD_UNTIL=$(( $(date +%s) - T0 + 240 ))
[ "$HOLD_UNTIL" -lt $((LOAD_SECONDS - 110)) ] && HOLD_UNTIL=$((LOAD_SECONDS - 110))
sleep_until "$HOLD_UNTIL"
kubectl get pods -l app=batch --no-headers | awk '{print $3}' | sort | uniq -c
helm upgrade shop charts/shop --reset-values >/dev/null
mark "перегрузка снята, ждём конца нагрузки"

kubectl -n loadtest wait --for=condition=complete job/loadgen --timeout=900s
mark "готово. Итог по волнам (клиентская сторона):"
kubectl -n loadtest logs job/loadgen | grep -E "cycle=|finished"
