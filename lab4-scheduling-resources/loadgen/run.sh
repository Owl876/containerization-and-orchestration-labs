#!/usr/bin/env bash
# Запуск волновой нагрузки по пути заказа (POST /orders) из кластера.
# Профиль волн: WAVES="rps:секунды,..." (rps=0 — пауза), повторяется CYCLES раз.
#   по умолчанию 5:60,20:120,50:120,10:60,0:60 = 7 минут на цикл, 10 циклов ~ 70 минут
set -euo pipefail
cd "$(dirname "$0")"

export WAVES="${WAVES:-5:60,20:120,50:120,10:60,0:60}"
export CYCLES="${CYCLES:-10}"

kubectl create namespace loadtest --dry-run=client -o yaml | kubectl apply -f -
kubectl -n loadtest create configmap loadgen --from-file=loadgen.py --dry-run=client -o yaml | kubectl apply -f -
kubectl -n loadtest delete job loadgen --ignore-not-found
envsubst '${WAVES} ${CYCLES}' < job.yaml | kubectl apply -f -

kubectl -n loadtest wait --for=condition=Ready pod -l app=loadgen --timeout=90s || true
kubectl -n loadtest logs -f job/loadgen
