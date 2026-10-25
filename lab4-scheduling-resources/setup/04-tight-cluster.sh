#!/usr/bin/env bash
# Делает minikube-ноды по-настоящему «тесными» (часть 2 и 7 лабы).
#
# Проблема: minikube на docker-драйвере отдаёт kubelet'у ресурсы ХОСТА. Планировщик видит
# 12 CPU и ~30 ГБ на ноду, хотя память ноды-контейнера ограничена 6 ГБ, а CPU не ограничен
# вовсе. Плюс minikube не задаёт eviction по памяти (в evictionHard только диск), так что
# kubelet не заметит реальной нехватки памяти.
#
# Что делаем на каждой ноде:
#   1. docker update --cpus: реальный лимит CPU на ноду-контейнер;
#   2. kubeReserved.cpu = (CPU хоста - CPUS): планировщик видит ровно CPUS ядер;
#   3. evictionHard memory.available = capacity - NODE_MEM_GI: allocatable памяти становится
#      NODE_MEM_GI, и eviction срабатывает, когда занято больше NODE_MEM_GI (раньше, чем
#      docker упрётся в свой лимит и убьёт процессы грубо).
# После `minikube start` конфиг kubelet может сброситься: запусти скрипт ещё раз.
set -euo pipefail

CPUS="${CPUS:-3}"
NODE_MEM_GI="${NODE_MEM_GI:-5}"

NODES=$(kubectl get nodes -o name | sed 's|node/||')
HOST_CPUS=$(kubectl get node minikube -o jsonpath='{.status.capacity.cpu}')
CAP_MEM_KI=$(kubectl get node minikube -o jsonpath='{.status.capacity.memory}' | sed 's/Ki$//')
RESERVED_CPU=$((HOST_CPUS - CPUS))
EVICT_KI=$((CAP_MEM_KI - NODE_MEM_GI * 1024 * 1024))

echo ">>> CPU хоста: $HOST_CPUS, хотим на ноду: $CPUS (kubeReserved.cpu=$RESERVED_CPU)"
echo ">>> память хоста: ${CAP_MEM_KI}Ki, хотим на ноду: ${NODE_MEM_GI}Gi (evictionHard memory.available=${EVICT_KI}Ki)"

for n in $NODES; do
  echo ">>> $n: docker update --cpus=$CPUS"
  docker update --cpus="$CPUS" "$n" >/dev/null

  echo ">>> $n: правим /var/lib/kubelet/config.yaml"
  docker exec -i "$n" env EVICT_KI="$EVICT_KI" RESERVED_CPU="$RESERVED_CPU" python3 - <<'PY'
import os, shutil

path = "/var/lib/kubelet/config.yaml"
try:
    shutil.copy(path, path + ".orig")  # при повторном запуске перезапишет, но конфиг идемпотентен
except OSError:
    pass

lines = open(path).read().splitlines()
out = []
skip_block = False
for line in lines:
    if line.startswith("kubeReserved:"):
        skip_block = True
        continue
    if skip_block:
        if line.startswith(" ") or line.startswith("\t"):
            continue
        skip_block = False
    if line.strip().startswith("memory.available:"):
        continue
    out.append(line)

res = []
for line in out:
    res.append(line)
    if line.startswith("evictionHard:"):
        res.append('  memory.available: "%sKi"' % os.environ["EVICT_KI"])
res += ["kubeReserved:", '  cpu: "%s"' % os.environ["RESERVED_CPU"]]
open(path, "w").write("\n".join(res) + "\n")
PY

  echo ">>> $n: systemctl restart kubelet"
  docker exec "$n" systemctl restart kubelet
done

echo ">>> ждём Ready и обновлённый allocatable"
sleep 20
kubectl wait --for=condition=Ready node --all --timeout=120s
kubectl get node -o custom-columns=NAME:.metadata.name,CAP_CPU:.status.capacity.cpu,ALLOC_CPU:.status.allocatable.cpu,CAP_MEM:.status.capacity.memory,ALLOC_MEM:.status.allocatable.memory
