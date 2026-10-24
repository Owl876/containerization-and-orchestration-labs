#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
check_context
# Optional upgrade hooks in this pinned chart use an unavailable old Bitnami
# image. A fresh pinned lab needs no legacy CRD migration or report cleanup.
helm upgrade --install kyverno kyverno/kyverno --version 3.4.4 \
  -n kyverno --create-namespace --wait --timeout 8m \
  --set admissionController.replicas=1 \
  --set backgroundController.replicas=1 \
  --set cleanupController.replicas=1 \
  --set reportsController.replicas=1 \
  --set policyReportsCleanup.enabled=false \
  --set crds.migration.enabled=false
kubectl apply -f "$LAB_DIR/policies"
kubectl wait --for=condition=Ready clusterpolicy --all --timeout=120s
kubectl create namespace shop --dry-run=client -o yaml | kubectl apply -f -
bash "$LAB_DIR/scripts/04-test-policies.sh"
