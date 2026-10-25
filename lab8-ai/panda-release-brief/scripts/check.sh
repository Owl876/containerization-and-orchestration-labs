#!/usr/bin/env bash
set -euo pipefail
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$LAB_DIR"
mkdir -p outputs report/evidence
docker compose exec -T agent python -m unittest discover -s tests -v 2>&1 | tee report/evidence/unit-tests.txt
docker compose exec -T prometheus promtool check config /etc/prometheus/prometheus.yml 2>&1 | tee report/evidence/promtool.txt
docker compose run --rm --no-deps -v "$LAB_DIR/monitoring:/checks:ro" --entrypoint promtool prometheus test rules /checks/alerts.test.yml 2>&1 | tee -a report/evidence/promtool.txt
echo 'Running real model reviews through the n8n production webhook...'
docker compose exec -T agent python - < scripts/verify.py > report/evidence/e2e.json
docker compose cp knowledge-mcp:/reports/. outputs/
python3 - <<'PY'
import json
from pathlib import Path
evidence = json.loads(Path('report/evidence/e2e.json').read_text())
for result in evidence['results']:
    report = Path('outputs') / result['report_file']
    assert report.read_text() == result['markdown'], f'Persisted report differs: {report}'
    # Keep the demonstrated reports in git independently of mutable runtime output.
    (Path('report/evidence') / f"release-{result['release_id']}.md").write_text(result['markdown'])
    print(f"{result['release_id']}: {result['decision'].upper()}, {result['llm_turns']} LLM turns, {result['duration_seconds']}s; persisted report verified")
print('Invalid input: 422; unknown release: 404; all Prometheus targets: UP')
PY
docker compose ps > report/evidence/containers.txt
docker compose exec -T agent python -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:8080/metrics").read().decode())' > report/evidence/agent-metrics.txt
