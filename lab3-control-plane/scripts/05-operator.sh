#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
helm upgrade --install cnpg cnpg/cloudnative-pg --version 0.23.2 \
  -n cnpg-system --create-namespace --wait --timeout 8m
kubectl wait --for=condition=Established crd/clusters.postgresql.cnpg.io --timeout=60s
