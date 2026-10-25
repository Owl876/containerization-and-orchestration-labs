#!/usr/bin/env bash
set -euo pipefail
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$LAB_DIR"
mkdir -p outputs report/evidence
for release in 1.1.0 1.2.0; do
  echo "Reviewing release $release with a real local model..."
  docker compose exec -T -e REVIEW_RELEASE="$release" agent python - <<'PY'
import json, os, urllib.request
release = os.environ['REVIEW_RELEASE']
request = urllib.request.Request('http://n8n:5678/webhook/panda-release-brief',
    data=json.dumps({'release_id': release}).encode(), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request, timeout=660) as response:
    result = json.load(response)
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
done | tee report/evidence/demo-console.txt
# Reuse actual saved reports; this does not fabricate any model responses.
docker compose cp knowledge-mcp:/reports/. outputs/
echo 'Saved reports copied to outputs/. Evidence: report/evidence/demo-console.txt'
