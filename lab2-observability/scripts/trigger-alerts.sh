#!/usr/bin/env bash
set -euo pipefail

echo ">>> 1) роняем error rate: долбим /fail полминуты"
for i in $(seq 1 60); do curl -s localhost:8000/fail > /dev/null; sleep 0.2; done &
PID1=$!

echo ">>> 2) роняем latency + energy: долбим /slow параллельно"
for i in $(seq 1 60); do curl -s localhost:8000/slow > /dev/null & sleep 0.3; done &
PID2=$!

wait $PID1 $PID2
echo ">>> готово, жди 1-2 минуты пока алерты перейдут pending -> firing"
