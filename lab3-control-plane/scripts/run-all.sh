#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
for script in 01-cluster 02-monitoring 03-policies 05-operator 06-shop 12-smoke 07-reconciliation 08-rolling-update 09-broken-rollback 10-control-plane 11-alerts; do
  echo "Running $script"
  bash "$SCRIPT_DIR/$script.sh"
done
bash "$SCRIPT_DIR/13-final-check.sh"
