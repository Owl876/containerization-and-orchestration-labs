#!/usr/bin/env bash
set -euo pipefail
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$LAB_DIR/.tools"
TMP_TOOLS=$(mktemp -d)
trap 'rm -rf "$TMP_TOOLS"' EXIT
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'Linux amd64 required'; exit 1; }
curl -fsSL --retry 3 https://get.helm.sh/helm-v3.17.3-linux-amd64.tar.gz -o "$TMP_TOOLS/helm.tgz"
curl -fsSL --retry 3 https://get.helm.sh/helm-v3.17.3-linux-amd64.tar.gz.sha256sum -o "$TMP_TOOLS/helm.sha256"
printf '%s  %s\n' "$(cut -d ' ' -f 1 "$TMP_TOOLS/helm.sha256")" "$TMP_TOOLS/helm.tgz" | sha256sum -c -
tar -xzf "$TMP_TOOLS/helm.tgz" -C "$TMP_TOOLS"
install -m 755 "$TMP_TOOLS/linux-amd64/helm" "$LAB_DIR/.tools/helm"
curl -fsSL --retry 3 https://dl.k8s.io/release/v1.32.2/bin/linux/amd64/kubectl -o "$LAB_DIR/.tools/kubectl"
curl -fsSL --retry 3 https://dl.k8s.io/release/v1.32.2/bin/linux/amd64/kubectl.sha256 -o "$TMP_TOOLS/kubectl.sha256"
printf '%s  %s\n' "$(cat "$TMP_TOOLS/kubectl.sha256")" "$LAB_DIR/.tools/kubectl" | sha256sum -c -
curl -fsSL --retry 3 https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64 -o "$LAB_DIR/.tools/kind"
curl -fsSL --retry 3 https://kind.sigs.k8s.io/dl/v0.27.0/kind-linux-amd64.sha256sum -o "$TMP_TOOLS/kind.sha256"
printf '%s  %s\n' "$(cut -d ' ' -f 1 "$TMP_TOOLS/kind.sha256")" "$LAB_DIR/.tools/kind" | sha256sum -c -
chmod +x "$LAB_DIR/.tools/kubectl" "$LAB_DIR/.tools/kind"
