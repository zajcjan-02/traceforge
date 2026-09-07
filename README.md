# TraceForge

TraceForge is a self-hosted developer observability tool focused on **automated, evidence-backed analysis of distributed traces**.

The project aims to reduce the amount of telemetry developers must interpret manually when debugging distributed applications.

Instead of only showing what happened during a request, TraceForge is designed to help answer questions such as:

* Which operation contributed most to request latency?
* Where did an error most likely originate?
* Did a service perform suspiciously repeated database operations?
* Which services participated in the request?
* Which execution behaviour deserves investigation first?

## Project Status

TraceForge is currently in **early development**.

The product, architecture, data flow, storage model, analysis engine, and API contracts were designed before implementation began.

The full design specification is available at:

```text
docs/DESIGN.md
```

## Planned v0.1

The initial version is focused on:

* OpenTelemetry trace ingestion;
* distributed trace reconstruction;
* trace inspection and waterfall visualization;
* observed service dependency discovery;
* deterministic diagnostic analysis;
* critical-path and latency analysis;
* repeated database-operation detection;
* error-origin and propagation analysis;
* structured findings with supporting telemetry evidence.

TraceForge v0.1 is intended primarily for local development, shared development environments, and small staging environments.

## Planned Architecture

```text
Instrumented Application
        ↓
OpenTelemetry Collector
        ↓
TraceForge Backend
        ↓
PostgreSQL
        ↓
Analysis Worker
        ↓
TraceForge API
        ↓
Web UI
```

The initial implementation will use a modular backend architecture with asynchronous diagnostic analysis and PostgreSQL-backed persistence and job scheduling.

## Technology Direction

Planned technologies include:

* **Python / FastAPI** — backend and analysis engine
* **PostgreSQL** — telemetry and analysis persistence
* **OpenTelemetry** — telemetry standard and ingestion
* **Next.js / TypeScript** — web interface
* **Docker Compose** — initial deployment environment

Technology choices may evolve where implementation evidence justifies a change.

## Design Philosophy

TraceForge follows one central principle:

> **Do not merely show developers more telemetry. Reduce the amount of telemetry they have to understand manually.**

Diagnostic findings should be deterministic, reproducible, and linked directly to the telemetry that supports them.

AI-generated explanations may be explored later, but core diagnosis will not depend on a language model.


