#!/usr/bin/env bash
set -euo pipefail

docker compose down -v --remove-orphans
docker compose up --build -d postgres

for _ in {1..30}; do
  if docker compose exec -T postgres pg_isready -U traceforge -d traceforge; then break; fi
  sleep 1
done

docker compose run --rm traceforge-backend alembic upgrade head
docker compose run --rm traceforge-backend python -c "from traceforge.database import engine; engine.connect().close()"
docker compose run --rm traceforge-worker python -c "from traceforge.database import engine; engine.connect().close()"
