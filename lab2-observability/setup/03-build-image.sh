#!/usr/bin/env bash
set -euo pipefail

# minikube поднимает kubernetes-ноду как отдельный Docker-контейнер со своим
# изолированным containerd/Docker внутри — образы с хоста туда не видны.
# `minikube image build` собирает образ сразу внутри этого изолированного
# рантайма, без лишней возни с docker-env/экспортом/импортом тарболов.
cd "$(dirname "$0")/../api"
minikube image build -t panda-api:local .

echo "--- образы внутри minikube ---"
minikube image ls | grep panda-api
