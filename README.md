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

## Trace search

`/traces` supports URL-shareable filters for exact trace ID, observed service,
single-root operation, lifecycle/analysis state, duration, current findings,
severity, and execution start time. Results are paginated by receipt recency;
execution-time filters intentionally differ from retention, which uses
`last_received_at`.

## Demo application

The independent, real OpenTelemetry demo proves an ordinary distributed app can
flow through the Collector into TraceForge. Start it alongside the local stack:

```sh
docker compose --profile demo up --build
```

Call its gateway at `http://127.0.0.1:8010`:

```sh
curl http://127.0.0.1:8010/demo/normal
curl http://127.0.0.1:8010/demo/repeated-db
curl http://127.0.0.1:8010/demo/slow-payment
curl http://127.0.0.1:8010/demo/error
curl http://127.0.0.1:8010/demo/repeated-downstream
curl http://127.0.0.1:8010/demo/concurrent
```

The scenarios respectively demonstrate a healthy request, repeated database
operations, a latency contributor, propagated error telemetry, repeated
downstream calls, and concurrent work. See [`demo/README.md`](demo/README.md)
for the standard OpenTelemetry attributes added where automatic instrumentation
cannot provide stable low-cardinality operation identity.

Each demo request also writes a concise Markdown report to `demo/reports/`.

## Configuration

Docker Compose provides working local defaults. The backend and worker use a
PostgreSQL `DATABASE_URL`; Compose also configures lifecycle timing, worker
polling/lease/retry settings, and detector repetition thresholds.

The UI uses `TRACEFORGE_API_URL`. `TRACEFORGE_DEBUG_UI=true` enables the
local debug fixture.

## Retention

TraceForge retains finalized traces for `TRACE_RETENTION_DAYS=7` by default.
Eligibility is based on `last_received_at`, never application execution time.
Set `TRACE_RETENTION_DAYS=0` to disable automatic cleanup. Inspect current
storage and run one bounded cleanup batch from the System page.

## Tests

```sh
cd apps/backend && uv run --extra dev pytest
cd apps/web && npm test && npm run build
cd demo && pip install ".[dev]" && pytest
```

## Current limitations

- No authentication, alerting, or production deployment workflow.
- No live updates, historical findings browser, or infrastructure topology.
- Service dependencies are observed direct cross-service relationships, not
  configured or transitive topology.
