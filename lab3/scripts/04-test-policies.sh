#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
exec > >(tee "$LAB_DIR/report/evidence/01-policies.txt") 2>&1
date -Is
kubectl get clusterpolicy
kubectl create -n shop --dry-run=server -f "$LAB_DIR/policy-tests/valid.yaml"
for rule in require-resources trusted-images require-labels disallow-privileged disallow-host-namespaces; do
  echo "Testing exactly one violation: $rule"
  if result=$(kubectl create -n shop --dry-run=server -f "$LAB_DIR/policy-tests/$rule.yaml" 2>&1); then
    echo "FAIL: invalid Pod was accepted"; exit 1
  fi
  echo "$result"
  [[ "$result" == *"$rule"* && "$result" == *"admission webhook"* ]] || exit 1
done
echo 'PASS: valid Pod accepted, all five invalid Pods rejected by admission.'
