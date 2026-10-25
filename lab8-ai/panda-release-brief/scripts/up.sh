#!/usr/bin/env bash
set -euo pipefail
LAB_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$LAB_DIR"
[[ -f .env ]] || cp .env.example .env
echo 'Building the stack and downloading the local model (first run may take several minutes)...'
# CLI import/publication changes the SQLite database. Stop this stack's n8n
# before importing, then start it so the published version is loaded reliably.
docker compose stop n8n
docker compose up -d --build --wait --wait-timeout 1200
echo 'Ready. n8n: http://localhost:15678; Grafana: http://localhost:13008/d/panda-release'
echo 'If ports were changed in .env, use those values.'
