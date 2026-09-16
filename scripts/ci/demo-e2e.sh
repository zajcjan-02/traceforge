#!/usr/bin/env bash
set -euo pipefail

wait_for() {
  local url=$1
  for _ in {1..60}; do curl --fail --silent "$url" >/dev/null && return 0; sleep 1; done
  return 1
}

finding() {
  local type=$1
  for _ in {1..90}; do curl --fail --silent "http://127.0.0.1:8000/api/v1/findings?type=$type" | jq -e '.items | length > 0' >/dev/null && return 0; sleep 1; done
  echo "Missing finding $type" >&2
  return 1
}

docker compose down -v --remove-orphans
docker compose --profile demo up --build -d
wait_for http://127.0.0.1:8000/health/ready
for scenario in normal repeated-db slow-payment repeated-downstream concurrent; do curl --fail --silent "http://127.0.0.1:8010/demo/$scenario" >/dev/null; done
curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8010/demo/error | grep -qx 500
finding REPEATED_DATABASE_OPERATION
finding MAJOR_LATENCY_CONTRIBUTOR
finding LIKELY_ERROR_ORIGIN
finding REPEATED_DOWNSTREAM_OPERATION
curl --fail --silent http://127.0.0.1:8000/api/v1/services | jq -e '.items | map(.name) | inside(["demo-gateway", "demo-orders", "demo-inventory", "demo-payment"])' >/dev/null
