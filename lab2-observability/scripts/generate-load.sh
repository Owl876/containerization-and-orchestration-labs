#!/usr/bin/env bash
set -euo pipefail

# Нужен открытый port-forward на panda-api (kubectl port-forward svc/panda-api 8000:8000)
BASE_URL="${1:-http://localhost:8000}"
WAVES="${2:-6}"

for i in $(seq 1 "$WAVES"); do
  n=$(( (RANDOM % 150) + 50 ))
  echo "--- волна $i/$WAVES: /load?n=$n ---"
  curl -s "${BASE_URL}/load?n=${n}&concurrency=30" > /dev/null

  curl -s "${BASE_URL}/fail" > /dev/null || true
  curl -s "${BASE_URL}/slow" > /dev/null

  sleep 10
done

echo "готово, можно смотреть на графики"
