# TraceForge

TraceForge is a self-hosted developer tool that ingests OpenTelemetry traces,
reconstructs observed execution, and produces deterministic findings backed by
the spans and events that support them.

## Status

TraceForge is an early v0.1 developer and staging tool. It supports local
Docker Compose deployment, OTLP trace ingestion, PostgreSQL persistence,
lifecycle and analysis processing, and a Next.js investigation UI.

## Current capabilities

- OTLP/gRPC and OTLP/HTTP trace ingestion through the OpenTelemetry Collector.
- Trace waterfall and span/event inspection.
- Deterministic findings for repeated database operations, latency
  contributors, likely error origins, and repeated downstream operations.
- Observed direct service dependencies, global findings, and system status.
- Deterministic local debug scenarios at `/debug`.

## Architecture

```text
Instrumented application → OpenTelemetry Collector → TraceForge backend
                                                    ├→ PostgreSQL
                                                    └→ analysis worker
Next.js UI → TraceForge API
```

The design source of truth is [`docs/design/`](docs/design/), especially the
[architecture](docs/design/09-system-architecture.md),
[analysis engine](docs/design/12-analysis-engine-design.md), and
[API contracts](docs/design/13-core-api-contracts.md).

## Quick start

Prerequisite: Docker Desktop with Docker Compose.

```sh
docker compose up --build
```

- Product UI: `http://127.0.0.1:3000`
- Backend health: `http://127.0.0.1:8000/health/ready`
- Debug fixtures: `http://127.0.0.1:8000/debug`
- OTLP/gRPC receiver: `127.0.0.1:4317`
- OTLP/HTTP receiver: `http://127.0.0.1:4318`

Generate a trace through the Collector:

```sh
telemetrygen traces --otlp-insecure --otlp-endpoint localhost:4317 --traces 1
```

Use `/debug` for deterministic detector scenarios, then investigate generated
traces, findings, services, and system status in the product UI.

## Configuration

Docker Compose provides working local defaults. The backend and worker use a
PostgreSQL `DATABASE_URL`; Compose also configures lifecycle timing, worker
polling/lease/retry settings, and detector repetition thresholds.

The UI uses `TRACEFORGE_API_URL`. `TRACEFORGE_DEBUG_UI=true` enables the
local debug fixture.

## Tests

```sh
cd apps/backend && uv run --extra dev pytest
cd apps/web && npm test && npm run build
```

## Current limitations

- No authentication, retention, alerting, or production deployment workflow.
- No live updates, historical findings browser, or infrastructure topology.
- Service dependencies are observed direct cross-service relationships, not
  configured or transitive topology.
