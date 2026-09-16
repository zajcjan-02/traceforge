#!/usr/bin/env bash
set -euo pipefail

wait_for() {
  local url=$1
  for _ in {1..60}; do
    if curl --fail --silent "$url" >/dev/null; then return 0; fi
    sleep 1
  done
  echo "Timed out waiting for $url" >&2
  return 1
}

finding() {
  local type=$1
  for _ in {1..90}; do
    if curl --fail --silent "http://127.0.0.1:8000/api/v1/findings?type=$type" | jq -e '.items | length > 0' >/dev/null; then return 0; fi
    sleep 1
  done
  echo "Timed out waiting for finding $type" >&2
  return 1
}

docker compose down -v --remove-orphans
docker compose --profile demo up --build -d
wait_for http://127.0.0.1:8000/health/live
wait_for http://127.0.0.1:8000/health/ready
wait_for http://127.0.0.1:8010/demo/normal
curl --fail --silent http://127.0.0.1:8010/demo/repeated-db >/dev/null
finding REPEATED_DATABASE_OPERATION

service_id=$(curl --fail --silent http://127.0.0.1:8000/api/v1/services | jq -r '.items[] | select(.name == "demo-gateway") | .service_id')
traces=$(curl --fail --silent "http://127.0.0.1:8000/api/v1/traces?service_id=$service_id&limit=10")
echo "$traces" | jq -e '.items | length >= 2' >/dev/null
trace_id=$(echo "$traces" | jq -r '.items[0].trace_id')
test "$trace_id" != "null"
curl --fail --silent "http://127.0.0.1:8000/api/v1/traces/$trace_id" | jq -e '.trace.completeness_state == "COMPLETE" and .trace.analysis_state == "COMPLETE"' >/dev/null
