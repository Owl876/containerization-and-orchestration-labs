#!/usr/bin/env bash
set -euo pipefail
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
K=(kubectl --kubeconfig "${LAB5_KUBECONFIG:-$HOME/.kube/lab5.yaml}" --context kind-lab5)
mkdir -p "$LAB_DIR/report/evidence"
exec > >(tee "$LAB_DIR/report/evidence/01-network-check.txt") 2>&1

date -Is
"${K[@]}" -n shop get pods -o wide
selector='app.kubernetes.io/instance=shop,app.kubernetes.io/name=api'
source_pod=$("${K[@]}" -n shop get pods -l "$selector" --field-selector spec.nodeName=lab5-worker -o jsonpath='{.items[0].metadata.name}')
target_pod=$("${K[@]}" -n shop get pods -l "$selector" --field-selector spec.nodeName=lab5-worker2 -o jsonpath='{.items[0].metadata.name}')
target_ip=$("${K[@]}" -n shop get pod "$target_pod" -o jsonpath='{.status.podIP}')

printf '\nSource: %s on lab5-worker\nTarget: %s on lab5-worker2 (%s)\n' "$source_pod" "$target_pod" "$target_ip"
"${K[@]}" -n shop exec "$source_pod" -- python -c '
import fcntl, socket, struct
from pathlib import Path

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip = socket.inet_ntoa(
    fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", b"eth0"))[20:24]
)
print("Inside pod: eth0 IP=" + ip)
for name in ("ifindex", "iflink", "address"):
    print(name + "=" + Path("/sys/class/net/eth0/" + name).read_text().strip())
'
peer_index=$("${K[@]}" -n shop exec "$source_pod" -- python -c 'from pathlib import Path; print(Path("/sys/class/net/eth0/iflink").read_text().strip())')
printf '\nPeer interface on lab5-worker (index %s):\n' "$peer_index"
docker --context panda-host exec lab5-worker ip -o link show | awk -v peer="$peer_index:" '$1 == peer {print; found=1} END {if (!found) exit 1}'

printf '\nDirect cross-node request (without Service):\n'
"${K[@]}" -n shop exec "$source_pod" -- python -c '
import sys, urllib.request

url = "http://" + sys.argv[1] + ":8000/health"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(url, timeout=10) as response:
    print(url, "HTTP", response.status, response.read().decode())
' "$target_ip"
