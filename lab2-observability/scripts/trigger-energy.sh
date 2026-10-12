#!/usr/bin/env bash
set -euo pipefail
echo ">>> непрерывно долбим /slow 90 секунд, чтобы энергия не успевала восстановиться"
end=$((SECONDS + 90))
while [ $SECONDS -lt $end ]; do
  curl -s localhost:8000/slow > /dev/null &
  sleep 0.2
done
wait
echo ">>> готово, энергия должна была всё это время сидеть у нуля, жди ~1 минуту на firing"
