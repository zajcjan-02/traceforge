# 13. Core API Contracts

## 13.1 Purpose

This section defines the initial developer-facing API contracts used by the TraceForge web interface and other potential clients.

The API exists to expose:

* trace summaries;
* complete trace detail;
* span detail;
* findings;
* services;
* observed service dependencies;
* TraceForge system state.

The API SHALL NOT expose database entities directly.

Instead, it should expose stable representations aligned with the TraceForge domain and product workflows.

The API should provide enough information for the frontend to render the product without reproducing backend diagnostic logic.

---

## 13.2 API Design Principles

The API SHALL follow several principles.

### Domain-oriented responses

Responses should represent concepts such as:

```text
Trace
Span
Finding
Service
Dependency
```

rather than ORM tables or storage implementation details.

---

### Backend owns interpretation

The API SHALL provide already-derived values such as:

```text
trace completeness
analysis state
finding confidence
critical-path contribution
normalized finding evidence
```

where these concepts belong to TraceForge analysis.

The frontend SHALL NOT recreate these calculations.

---

### Raw telemetry remains accessible

Simplified responses must not prevent inspection of canonical span data.

Detailed endpoints SHALL expose:

* attributes;
* events;
* identifiers;
* timing;
* instrumentation metadata.

---

### API changes should be additive where practical

New optional fields SHOULD generally be preferred over breaking structural changes.

---

### The API should remain small

TraceForge v0.1 does not require dozens of specialized endpoints.

A small number of useful resources is preferable.

---

## 13.3 Base API Structure

The developer-facing API SHOULD use a dedicated prefix.

Conceptually:

```text
/api/v1
```

Example resources:

```text
/api/v1/traces
/api/v1/services
/api/v1/findings
/api/v1/system
```

The version prefix allows future incompatible API changes without coupling them to the application release version.

---

## 13.4 Telemetry API Is Separate

OTLP ingestion is not part of the developer-facing REST API.

Conceptually:

```text
OTLP ingestion
```

and:

```text
/api/v1/*
```

are separate logical interfaces.

The backend may host both in the same process, but their contracts and responsibilities SHALL remain independent.

---

## 13.5 Response Encoding

Developer-facing API responses SHOULD use:

```text
application/json
```

Identifiers such as Trace IDs and Span IDs SHALL be represented as lowercase hexadecimal strings.

Example:

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

Execution timestamps that must preserve nanosecond precision SHOULD use integer nanoseconds.

Human-facing timestamps MAY additionally be provided as ISO-8601 strings where convenient.

---

## 13.6 Standard Error Model

API errors SHOULD use a consistent representation.

Conceptually:

```json
{
  "error": {
    "code": "TRACE_NOT_FOUND",
    "message": "The requested trace does not exist.",
    "details": {}
  }
}
```

The response SHOULD contain:

```text
machine-readable code
human-readable message
optional structured details
```

Internal exceptions or stack traces SHALL NOT be exposed directly to the browser.

---

## 13.7 Common Error Categories

Initial API error codes may include:

```text
INVALID_REQUEST
INVALID_FILTER
INVALID_TRACE_ID
INVALID_SPAN_ID

TRACE_NOT_FOUND
SPAN_NOT_FOUND
SERVICE_NOT_FOUND
FINDING_NOT_FOUND

SYSTEM_UNAVAILABLE
STORAGE_UNAVAILABLE

INTERNAL_ERROR
```

The exact set may evolve.

---

## 13.8 Trace Summary Resource

A trace summary represents one trace in listing and search workflows.

Conceptually:

```text
TraceSummary {
    trace_id

    start_time_unix_ns
    duration_ns

    root_service?
    root_operation?

    status

    completeness_state
    analysis_state

    span_count
    service_count

    finding_count
    highest_finding_severity?

    revision
}
```

---

## 13.9 Trace Summary Example

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "start_time_unix_ns": 1788722400123456789,
  "duration_ns": 2810000000,

  "root_service": {
    "service_id": 1,
    "name": "gateway"
  },

  "root_operation": "GET /checkout",

  "status": "ERROR",

  "completeness_state": "COMPLETE",
  "analysis_state": "COMPLETE",

  "span_count": 23,
  "service_count": 4,

  "finding_count": 2,
  "highest_finding_severity": "HIGH",

  "revision": 7
}
```

---

## 13.10 List Traces Endpoint

Conceptually:

```http
GET /api/v1/traces
```

This endpoint SHALL support trace discovery and filtering.

Potential query parameters:

```text
from
to

service
operation

status

min_duration_ns
max_duration_ns

has_findings

limit
cursor
```

---

## 13.11 Trace Filter Example

```http
GET /api/v1/traces
    ?service=payment-service
    &status=ERROR
    &min_duration_ns=1000000000
```

The API should return matching traces in descending recency order by default.

---

## 13.12 Trace List Response

Conceptually:

```json
{
  "items": [
    {
      "...": "TraceSummary"
    }
  ],

  "next_cursor": "opaque-value-or-null"
}
```

The frontend SHALL treat the cursor as opaque.

The API should not require clients to construct database-specific pagination values.

---

## 13.13 Pagination

Cursor-based pagination is preferred.

The API SHOULD avoid exposing:

```text
OFFSET 50000
```

style semantics as the long-term contract.

The cursor may internally encode:

```text
sort timestamp
trace ID
```

but its internal representation is not part of the public API contract.

---

## 13.14 Get Trace Endpoint

Conceptually:

```http
GET /api/v1/traces/{trace_id}
```

This endpoint returns the complete product-level representation of a trace.

It should provide enough information for the UI to render:

* trace overview;
* span hierarchy;
* waterfall;
* structural warnings;
* findings;
* finding navigation.

---

## 13.15 Trace Detail Resource

Conceptually:

```text
TraceDetail {
    trace

    spans[]
    structural_issues[]

    current_analysis?
}
```

Where:

```text
trace
```

contains trace-level metadata.

---

## 13.16 Trace Metadata

Conceptually:

```text
TraceMetadata {
    trace_id
    revision

    start_time_unix_ns
    end_time_unix_ns
    duration_ns

    status
    completeness_state
    analysis_state

    root_span_ids[]

    services[]

    span_count

    first_received_at
    last_received_at
}
```

---

## 13.17 Span Summary Within Trace Detail

For rendering the waterfall, each span should expose at least:

```text
SpanSummary {
    span_id
    parent_span_id?

    service

    name
    operation_type
    normalized_operation?

    span_kind

    start_time_unix_ns
    end_time_unix_ns?
    duration_ns?

    status

    has_error

    structural_flags[]
}
```

The response SHOULD contain sufficient information to build the parent-child structure without additional requests.

---

## 13.18 Span Ordering

The trace-detail API SHOULD return spans in a deterministic order.

Preferred default:

```text
start_time ascending
```

with a deterministic secondary key such as:

```text
span_id
```

The frontend must not rely on transport order for parent-child reconstruction.

---

## 13.19 Span Detail Endpoint

The initial frontend may receive enough data from the trace-detail response to inspect most span information.

However, large attribute/event payloads may justify a dedicated endpoint.

Conceptually:

```http
GET /api/v1/traces/{trace_id}/spans/{span_id}
```

This endpoint returns canonical detailed telemetry for one span.

---

## 13.20 Span Detail Resource

Conceptually:

```text
SpanDetail {
    trace_id
    span_id
    parent_span_id?

    service?

    name
    span_kind
    operation_type
    normalized_operation?

    start_time_unix_ns
    end_time_unix_ns?
    duration_ns?

    status

    attributes
    resource_attributes

    instrumentation_scope

    events[]

    structural_flags[]
}
```

---

## 13.21 Span Event Resource

Conceptually:

```text
SpanEvent {
    name
    timestamp_unix_ns

    attributes
}
```

Exception events remain represented using their underlying telemetry values.

The backend MAY additionally expose normalized error information separately.

---

## 13.22 Current Analysis Resource

The trace-detail response SHOULD include the current analysis state.

Conceptually:

```text
TraceAnalysis {
    analysis_run_id
    trace_revision

    state

    started_at
    completed_at?

    findings[]

    detector_results_summary?
}
```

The API SHALL only expose an analysis as current when:

```text
analysis.trace_revision == trace.revision
```

and it has been successfully published.

---

## 13.23 Analysis State With No Current Run

For:

```text
PENDING
RUNNING
FAILED
```

there may be no complete current analysis output.

The response should still represent the state clearly.

Example:

```json
{
  "analysis": {
    "state": "PENDING",
    "current_run": null
  }
}
```

---

## 13.24 Finding Resource

A finding represents one diagnostic conclusion.

Conceptually:

```text
Finding {
    finding_id

    type

    severity
    confidence

    title
    summary

    observation

    interpretation?

    related_span_ids[]

    evidence[]

    structured_data
}
```

---

## 13.25 Finding Example

```json
{
  "finding_id": "20ca38ad-14f9-4bd4-b9a4-a73bf1d9ef89",

  "type": "REPEATED_DATABASE_OPERATION",

  "severity": "MEDIUM",
  "confidence": "HIGH",

  "title": "Repeated database operation",

  "summary": "34 structurally equivalent database operations were observed in orders-service.",

  "observation": "34 equivalent operations were observed.",

  "interpretation": "This pattern may indicate redundant database access or an N+1 query pattern.",

  "related_span_ids": [
    "0011223344556677",
    "1122334455667788"
  ],

  "structured_data": {
    "count": 34,
    "sequential_count": 31,
    "combined_duration_ns": 2070000000,
    "trace_duration_ns": 2810000000
  },

  "evidence": [
    {
      "type": "OPERATION_COUNT",
      "structured_data": {
        "count": 34
      }
    }
  ]
}
```

---

## 13.26 Evidence Resource

Conceptually:

```text
Evidence {
    type

    description?

    related_span_ids[]

    structured_data
}
```

Evidence values SHOULD remain machine-readable.

The frontend may create richer presentation from structured values.

---

## 13.27 Finding Navigation

Every span referenced by:

```text
related_span_ids
```

SHOULD exist within the same trace response.

The frontend can therefore perform:

```text
Finding selected
    ↓
related span IDs
    ↓
highlight spans
```

without querying the backend again.

---

## 13.28 Global Findings Endpoint

Conceptually:

```http
GET /api/v1/findings
```

This endpoint provides recent current findings across traces.

Potential filters:

```text
type
severity
confidence
service
from
to
limit
cursor
```

---

## 13.29 Current Findings Only

Ordinary findings APIs SHALL expose only findings belonging to the trace's current analysis run.

Stale historical findings SHALL NOT appear unless an explicit historical-analysis endpoint is introduced later.

---

## 13.30 Findings List Resource

A global finding summary may contain:

```text
FindingSummary {
    finding_id
    trace_id

    type
    severity
    confidence

    title
    summary

    service?

    trace_operation?
    trace_start_time

    created_at
}
```

The complete evidence can remain available through trace detail.

---

## 13.31 Get Finding Endpoint

A dedicated endpoint MAY exist:

```http
GET /api/v1/findings/{finding_id}
```

but it is not strictly required if trace-detail responses already contain full finding information.

The initial implementation SHOULD avoid unnecessary endpoint proliferation.

---

## 13.32 Service Summary Resource

Conceptually:

```text
ServiceSummary {
    service_id
    name
    namespace?

    first_seen_at
    last_seen_at

    recent_trace_count
    recent_error_trace_count

    observed_operation_count

    dependency_count
}
```

Some aggregate fields MAY be calculated dynamically.

---

## 13.33 List Services Endpoint

Conceptually:

```http
GET /api/v1/services
```

Potential query parameters may include:

```text
search
limit
cursor
```

For v0.1, the service inventory is expected to remain small enough that aggressive pagination may not initially be necessary.

---

## 13.34 Get Service Endpoint

Conceptually:

```http
GET /api/v1/services/{service_id}
```

Response:

```text
ServiceDetail {
    service

    recent_traces[]
    dependencies[]

    observed_operations[]
}
```

The endpoint should support the product workflow:

```text
service
    ↓
suspicious trace
    ↓
trace investigation
```

---

## 13.35 Service Identity in URLs

The API SHOULD prefer stable internal service IDs for resource paths rather than raw service names.

Preferred:

```text
/services/17
```

over:

```text
/services/orders-service
```

Reasons include:

* service names may contain characters requiring escaping;
* namespace may participate in identity;
* names may evolve.

The service name remains visible in the response.

---

## 13.36 Service Dependency Resource

Conceptually:

```text
ServiceDependency {
    source_service
    target_service

    first_seen_at
    last_seen_at

    observation_count
}
```

If aggregate counts are not materialized, they may be derived from dependency observations.

The initial endpoint returns directed incoming and outgoing service relationships
with telemetry-derived first/last observation times.

---

## 13.37 Service Dependency Endpoint

Possible design:

```http
GET /api/v1/services/{service_id}/dependencies
```

This should return both:

```text
outgoing
incoming
```

relationships.

Example:

```json
{
  "outgoing": [],
  "incoming": []
}
```

---

## 13.38 Dependency Trace Navigation

The developer should be able to investigate:

```text
orders-service → payment-service
```

through traces that demonstrated the relationship.

This MAY use the ordinary trace endpoint with filters:

```http
GET /api/v1/traces
    ?source_service=orders-service
    &target_service=payment-service
```

or a dedicated dependency-traces route.

The preferred v0.1 choice is to extend trace filtering only if the query remains conceptually clean.

---

## 13.39 Observed Operations

A service detail view MAY expose operations such as:

```text
GET /orders/{id}
POST /orders
SELECT product WHERE id = ?
```

Conceptually:

```text
ObservedOperation {
    operation_type
    normalized_operation

    observed_count
    last_seen_at
}
```

This is a supporting investigation feature, not a major analytics API.

---

## 13.40 System Health Endpoint

Conceptually:

```http
GET /api/v1/system/health
```

This endpoint represents TraceForge's operational state.

It should not be confused with a simple container liveness probe.

---

## 13.41 System Health Resource

Conceptually:

```text
SystemHealth {
    overall_status

    backend
    storage
    ingestion
    analysis

    last_telemetry_received_at?

    analysis_queue

    recent_errors[]
}
```

Example:

```json
{
  "overall_status": "DEGRADED",

  "backend": {
    "status": "HEALTHY"
  },

  "storage": {
    "status": "HEALTHY"
  },

  "ingestion": {
    "status": "HEALTHY",
    "last_telemetry_received_at": "2026-09-07T01:42:13Z"
  },

  "analysis": {
    "status": "DEGRADED",
    "pending_jobs": 42,
    "oldest_pending_job_age_ms": 18500
  }
}
```

---

## 13.42 Liveness and Readiness Endpoints

Container/orchestration health checks SHOULD remain separate from product system health.

Conceptually:

```http
GET /health/live
GET /health/ready
```

### Liveness

Answers:

> Is the process running?

### Readiness

Answers:

> Can the process perform its required responsibilities?

For example, the backend may be alive but not ready if PostgreSQL is unavailable.

---

## 13.43 First-Run Status

When no telemetry has been received, the system endpoint should make this explicit.

Example:

```json
{
  "ingestion": {
    "status": "WAITING_FOR_TELEMETRY",
    "last_telemetry_received_at": null
  }
}
```

This allows the UI to distinguish:

```text
healthy but empty
```

from:

```text
broken ingestion
```

---

## 13.44 Analysis Queue State

The System API SHOULD eventually expose approximately:

```text
pending_jobs
running_jobs
failed_jobs_recent
oldest_pending_job_age
```

This supports diagnosis of:

```text
analysis is delayed
```

rather than merely displaying:

```text
PENDING
```

forever.

---

## 13.45 Trace Structural Issues Resource

The trace detail response SHALL expose known structural issues.

Conceptually:

```text
TraceStructuralIssue {
    type

    affected_span_ids[]

    summary

    details
}
```

Example:

```json
{
  "type": "MISSING_PARENT",
  "affected_span_ids": [
    "0011223344556677"
  ],
  "summary": "One span references a parent that was not observed."
}
```

---

## 13.46 Product-Level State Enums

The API SHOULD use stable explicit values for core states.

### Trace completeness

```text
PROCESSING
COMPLETE
INCOMPLETE
```

### Analysis

```text
PENDING
RUNNING
COMPLETE
PARTIAL
FAILED
```

### Detector

```text
SUCCESS_WITH_FINDINGS
SUCCESS_NO_FINDINGS
SKIPPED_INSUFFICIENT_DATA
SKIPPED_NOT_APPLICABLE
FAILED
```

These definitions SHALL match backend domain semantics.

---

## 13.47 Trace Status

Trace execution status and analysis status SHALL remain separate.

Possible trace execution states may include:

```text
UNSET
OK
ERROR
```

or an equivalent normalized model.

The exact mapping from OpenTelemetry status and protocol-specific error indicators will be defined during implementation.

---

## 13.48 Severity API Model

v0.1 SHOULD expose:

```text
INFO
LOW
MEDIUM
HIGH
```

unless analysis design later demonstrates a need for `CRITICAL`.

The ordering semantics should remain defined.

---

## 13.49 Confidence API Model

v0.1 SHALL use:

```text
LOW
MEDIUM
HIGH
```

Confidence SHALL NOT be represented as a fabricated percentage.

---

## 13.50 API Time Semantics

The API SHALL distinguish:

```text
execution timestamps
```

from:

```text
TraceForge ingestion/analysis timestamps
```

Execution timing:

```text
*_unix_ns
```

should preserve canonical precision.

System timestamps such as:

```text
created_at
completed_at
last_received_at
```

may use ISO-8601 strings.

---

## 13.51 Large Integer Serialization

Nanosecond timestamps may exceed JavaScript's safe integer range.

The API therefore SHALL NOT assume all 64-bit integer values can be safely represented as JavaScript JSON numbers.

Preferred representations include:

```text
decimal strings
```

for canonical 64-bit nanosecond timestamps and durations where exact precision is required.

Example:

```json
{
  "start_time_unix_ns": "1788722400123456789",
  "duration_ns": "2810000000"
}
```

The frontend can convert these to:

```text
BigInt
```

where necessary.

---

## 13.52 Why This Matters

JavaScript's ordinary numeric representation cannot exactly represent every integer above:

```text
2^53 - 1
```

TraceForge SHALL NOT lose telemetry timing precision accidentally at the API boundary.

This decision should be applied consistently to nanosecond values.

---

## 13.53 Duration Presentation

The backend SHOULD provide canonical:

```text
duration_ns
```

while the frontend owns human formatting such as:

```text
2.81 s
184 ms
61 µs
```

This keeps API values precise and presentation flexible.

---

## 13.54 Attribute Representation

OpenTelemetry attributes may contain several value types.

The API SHOULD preserve type information where practical.

Example:

```json
{
  "http.response.status_code": 500,
  "server.address": "payment-service",
  "cache.hit": false
}
```

If OpenTelemetry arrays or other supported values require normalization, the representation must remain lossless enough for inspection.

---

## 13.55 Attribute Size Limits

The API MAY impose response-size protections for unusually large telemetry attributes.

If truncation is ever performed:

```text
the user must be told.
```

Silent telemetry truncation in the inspection API is undesirable.

For v0.1, normal intended workloads should generally return attributes directly.

---

## 13.56 Trace Detail Response Size

A typical trace containing hundreds of spans can reasonably be returned in one response.

TraceForge v0.1 SHOULD optimize for:

```text
one trace detail request
```

rather than requiring dozens of lazy requests.

Extremely large traces may later require:

* partial loading;
* span pagination;
* virtualization-friendly APIs.

These are not initial requirements.

---

## 13.57 Frontend Waterfall Contract

The trace-detail API must provide everything required to calculate presentation coordinates.

For each span:

```text
start_time_unix_ns
end_time_unix_ns
duration_ns
parent_span_id
```

The frontend may calculate:

```text
relative_start =
span.start - trace.start
```

for visualization.

The backend does not need to return pixel positions or UI coordinates.

---

## 13.58 Frontend Hierarchy Contract

The frontend may construct the hierarchy using:

```text
span_id
parent_span_id
```

because these are canonical relationships.

Alternatively, the backend may provide precomputed:

```text
children
```

but this is not necessary initially.

Avoid duplicating structural representations unless it clearly improves the API.

---

## 13.59 Analysis-Specific Span Annotations

The trace response MAY include derived annotations such as:

```text
on_critical_path
critical_path_contribution_ns
```

if these materially simplify presentation.

However, such values belong to the current analysis revision.

They SHALL NOT be presented as canonical span properties.

A possible representation is:

```text
analysis_annotations
```

separate from span telemetry.

---

## 13.60 Preferred Analysis Annotation Model

Rather than mutate each `SpanSummary`, the response MAY provide:

```text
span_analysis: {
    "<span_id>": {
        "critical_path_contribution_ns": "...",
        "on_critical_path": true
    }
}
```

This keeps:

```text
canonical span
```

and:

```text
derived analysis
```

visibly distinct.

The exact JSON shape may be refined during frontend implementation.

---

## 13.61 Filtering by Service

The public API SHOULD prefer service IDs when the frontend already knows them.

Example:

```text
service_id=17
```

For onboarding and convenience, service-name filtering MAY also be supported.

The contract should avoid ambiguous service-name resolution where namespaces exist.

---

## 13.62 Operation Filtering

Operation filtering should initially be exact or structured rather than a full-text query language.

Possible semantics:

```text
operation=GET /checkout
```

or:

```text
operation_contains=checkout
```

The final filter names should be kept minimal.

---

## 13.63 Duration Filters

Duration filters SHALL use a clearly documented unit.

Preferred:

```text
min_duration_ns
max_duration_ns
```

This avoids hidden conversions.

Frontend controls may work in milliseconds or seconds and convert before sending.

---

## 13.64 Time Range Filters

Execution-time filtering SHOULD accept ISO-8601 timestamps for developer convenience.

Example:

```text
from=2026-09-07T00:00:00Z
to=2026-09-07T01:00:00Z
```

The backend converts these to the canonical query representation.

---

## 13.65 API Sorting

Trace listing SHOULD default to:

```text
newest first
```

Potential explicit sort options may later include:

```text
duration
finding severity
```

v0.1 does not require a general arbitrary sorting system.

---

## 13.66 Request Limits

List endpoints SHALL enforce maximum page sizes.

For example:

```text
default limit = 50
maximum limit = 200
```

Exact values may be tuned.

Unbounded result requests SHALL not be allowed.

---

## 13.67 API Validation

The backend SHALL validate:

* trace ID length/format;
* span ID length/format;
* pagination values;
* enum values;
* duration bounds;
* time ranges;
* service identifiers.

Invalid input should produce:

```text
4xx
```

rather than an internal error.

---

## 13.68 Not-Found Semantics

Requesting a validly formatted but unknown trace:

```http
GET /api/v1/traces/{trace_id}
```

SHOULD return:

```text
404
```

with:

```text
TRACE_NOT_FOUND
```

A malformed trace identifier SHOULD return:

```text
400
```

with:

```text
INVALID_TRACE_ID
```

These states should remain distinct.

---

## 13.69 Analysis-Pending Trace Response

A trace that exists but is not yet analyzed SHOULD still return normally.

Example:

```json
{
  "trace": {
    "...": "..."
  },

  "analysis": {
    "state": "PENDING",
    "current_run": null
  }
}
```

The API SHALL NOT return an error merely because diagnostic results are not ready.

---

## 13.70 Incomplete Trace Response

An incomplete trace should similarly remain a successful resource response.

Example:

```json
{
  "trace": {
    "completeness_state": "INCOMPLETE"
  },

  "structural_issues": [
    {
      "type": "MISSING_PARENT"
    }
  ]
}
```

Incomplete telemetry is a domain state, not an HTTP failure.

---

## 13.71 Partial Analysis Response

If analysis completed partially:

```json
{
  "analysis": {
    "state": "PARTIAL",
    "findings": [
      "..."
    ],

    "detector_results": [
      {
        "detector_id": "critical_path",
        "state": "SKIPPED_INSUFFICIENT_DATA"
      },
      {
        "detector_id": "error_origin",
        "state": "SUCCESS_WITH_FINDINGS"
      }
    ]
  }
}
```

The UI can therefore explain why some analysis is missing.

---

## 13.72 Detector Results Exposure

The UI does not need full detector-debug information during ordinary use.

However, enough summary information SHOULD be exposed to distinguish:

```text
no finding
not applicable
insufficient data
failure
```

Detailed detector diagnostics may later belong in a developer/debug view.

---

## 13.73 Historical Analysis API

Historical stale analysis runs are stored but are NOT part of the ordinary v0.1 API.

A future endpoint may expose:

```http
GET /api/v1/traces/{trace_id}/analysis-runs
```

This is deferred.

The current API always emphasizes the analysis corresponding to the current trace revision.

---

## 13.74 Mutation APIs

TraceForge v0.1 is predominantly read-oriented from the browser.

The frontend does not initially need APIs for:

```text
editing traces
editing spans
editing findings
acknowledging incidents
changing telemetry
```

Canonical telemetry and findings are system-generated.

---

## 13.75 Configuration API

Runtime configuration management through the UI is not required for v0.1.

Detector thresholds and system configuration may initially come from:

```text
environment/configuration files
```

A future administrative configuration API may be added.

---

## 13.76 Manual Re-analysis

A manual endpoint such as:

```http
POST /api/v1/traces/{trace_id}/reanalyze
```

could be useful during development.

However, it is NOT required for the core product flow.

If added, it must:

* schedule a new analysis safely;
* respect trace revision;
* avoid duplicate active jobs.

This is a likely developer convenience rather than a core API requirement.

---

## 13.77 API Authentication

The v0.1 API assumes the trusted development deployment model established earlier.

Enterprise authentication is out of scope.

The API architecture SHOULD nevertheless avoid assumptions that make future authentication impossible.

For example, endpoint design should not depend on client-supplied trusted identity values.

---

## 13.78 CORS

If frontend and backend are served from different local origins, CORS configuration may be required.

CORS SHALL use explicit configured origins rather than unrestricted wildcard exposure by default when credentials or future authentication are introduced.

Deployment design will determine the final development configuration.

---

## 13.79 API Documentation

The backend SHOULD expose generated API documentation during development.

Using FastAPI makes:

```text
OpenAPI
```

a natural contract representation.

The OpenAPI document should become useful for:

* frontend integration;
* debugging;
* generated clients if desired;
* contract testing.

---

## 13.80 OpenAPI Is Not the Domain Model

Generated OpenAPI schemas describe transport representations.

They SHALL NOT replace the domain model defined in Section 8.

The intended mapping remains:

```text
Domain model
    ↓
application/API mapping
    ↓
API schema
```

not:

```text
OpenAPI-generated type
    ↓
used as domain everywhere.
```

---

## 13.81 Frontend Type Generation

Because the frontend uses TypeScript, TraceForge MAY generate TypeScript API types from OpenAPI.

This can reduce drift between:

```text
FastAPI schemas
```

and:

```text
frontend API types
```

If used, generated API models should remain separate from UI/domain presentation types where necessary.

---

## 13.82 API Client Boundary

The frontend SHOULD use a dedicated API client layer.

Conceptually:

```text
UI Components
      ↓
frontend domain/hooks
      ↓
TraceForge API client
      ↓
HTTP
```

Components should not contain arbitrary raw `fetch()` calls spread throughout the application.

This improves:

* error handling;
* typing;
* testing;
* future API evolution.

---

## 13.83 API Contract Tests

Core endpoints SHOULD have contract/integration tests.

Examples:

```text
GET /traces returns valid TraceSummary

GET /traces/{id} returns all required spans

finding.related_span_ids reference existing spans

64-bit nanosecond values preserve exact precision

incomplete trace remains HTTP 200

unknown trace returns 404

malformed trace ID returns 400
```

---

## 13.84 Trace Detail Consistency Invariant

For one `TraceDetail` response:

```text
trace.revision
```

and:

```text
analysis.trace_revision
```

must either match or no current analysis should be presented.

The API SHALL NOT combine:

```text
revision 8 spans
```

with:

```text
revision 7 findings
```

as if both were current.

---

## 13.85 Finding Reference Invariant

For every current finding returned with a trace:

```text
finding.trace_id == trace.trace_id
```

and every:

```text
related_span_id
```

must reference a span belonging to that trace revision's canonical telemetry.

---

## 13.86 API Read Consistency

Trace detail should represent a coherent logical snapshot.

If late telemetry arrives during a query, the API SHOULD avoid mixing partially updated:

```text
trace metadata
spans
analysis
```

where practical.

PostgreSQL transaction isolation and explicit revision checks can support this.

The implementation does not need heavy distributed snapshot machinery.

---

## 13.87 Trace List Eventual Freshness

Trace lists do not need strict transactional synchronization with every incoming span at browser-refresh precision.

Small delays in derived summary updates are acceptable provided:

* trace detail remains authoritative;
* no misleading stale analysis is shown;
* eventually the list reflects the latest canonical state.

---

## 13.88 API Performance Goals

The API should support the NFR targets established earlier:

```text
trace list p95 ≤ 500 ms

typical trace detail p95 ≤ 500 ms
```

under intended v0.1 workload.

Responses should avoid unnecessary computation of diagnostics during request handling.

---

## 13.89 No N+1 API Queries

Backend implementations SHALL avoid patterns such as:

```text
load 100 traces

for every trace:
    query service
    query finding count
    query span count
```

Trace summary queries should use:

* materialized metadata;
* bounded joins;
* aggregate queries.

It would be particularly embarrassing for TraceForge to detect N+1 queries while implementing one in its own trace list.

---

## 13.90 API Caching

No external cache is required for v0.1.

Browser/client caching and normal HTTP semantics MAY be used where helpful.

PostgreSQL-backed query performance should be validated before introducing Redis or other caching infrastructure.

---

## 13.91 Future Live Updates

The first implementation MAY use normal polling for:

```text
new traces
analysis completion
system state
```

Future versions may introduce:

```text
Server-Sent Events
WebSockets
```

for live updates.

Real-time streaming is not required before coding begins.

---

## 13.92 Polling-Friendly Analysis State

The API should make polling simple.

Example:

```text
GET /traces/{id}
```

returns:

```text
analysis_state = PENDING
```

and a later call returns:

```text
analysis_state = COMPLETE
```

No separate asynchronous job token is required for ordinary trace investigation.

---

## 13.93 Suggested v0.1 Endpoint Set

The minimal initial developer-facing API is:

```text
GET /api/v1/traces

GET /api/v1/traces/{trace_id}

GET /api/v1/traces/{trace_id}/spans/{span_id}

GET /api/v1/findings

GET /api/v1/services

GET /api/v1/services/{service_id}

GET /api/v1/services/{service_id}/dependencies

GET /api/v1/system/health

GET /health/live

GET /health/ready
```

Additional endpoints SHALL be added only when a concrete workflow requires them.

---

## 13.94 First Implementation Slice

The API does not need to be implemented all at once.

The first useful vertical slice SHOULD require only:

```text
GET /api/v1/traces

GET /api/v1/traces/{trace_id}

GET /health/live

GET /health/ready
```

alongside OTLP ingestion.

This is sufficient to validate:

```text
telemetry
    ↓
database
    ↓
trace reconstruction
    ↓
API
```

before analysis functionality is added.

---

## 13.95 Second Implementation Slice

Once analysis exists:

```text
TraceDetail
```

can be expanded to include:

```text
analysis state
findings
evidence
analysis annotations
```

The API contract is deliberately designed so these can be additive fields.

---

## 13.96 Resolved API Decisions

The initial API design makes the following decisions:

```text
API-001
Use a versioned developer-facing HTTP JSON API.

API-002
Keep OTLP ingestion separate from the developer REST API.

API-003
Expose domain-oriented resources rather than database rows.

API-004
Use hexadecimal strings for trace/span IDs over JSON.

API-005
Use exact string representations for nanosecond integer
values that exceed JavaScript safe integer precision.

API-006
Return complete ordinary traces in one trace-detail response.

API-007
Keep findings structured and evidence-backed.

API-008
Include related span references directly in findings.

API-009
Expose only findings from the current trace revision in
ordinary APIs.

API-010
Represent incomplete traces and pending/partial analysis
as valid domain states rather than HTTP errors.

API-011
Use cursor-based pagination as the preferred list model.

API-012
Use internal service IDs for stable service resource paths.

API-013
Keep API-side diagnostic computation minimal.

API-014
Do not expose mutation-heavy product APIs in v0.1.

API-015
Use OpenAPI as the transport contract.

API-016
Keep API schemas separate from core domain objects.
```

---

## 13.97 Open API Questions

### Q-API-001 — Trace detail size

At what span count should the API stop returning the complete trace in one response?

No limit needs to be imposed until real trace sizes justify one.

---

### Q-API-002 — Span detail duplication

Should full span attributes/events be included directly in the trace response, or loaded only when a span is opened?

Likely initial approach:

```text
lightweight span summaries in TraceDetail
+
dedicated SpanDetail endpoint
```

This keeps trace responses manageable.

---

### Q-API-003 — Current detector result visibility

How much detector execution state should ordinary users see?

At minimum enough to explain:

```text
analysis partial
detector lacked data
```

without exposing internal debugging noise.

---

### Q-API-004 — Frontend-generated client

Should TypeScript types/client code be generated automatically from OpenAPI?

Likely:

```text
yes
```

if the generated output remains clean and maintainable.

---

### Q-API-005 — Live updates

Should early UI polling eventually be replaced by:

```text
SSE
```

or:

```text
WebSockets
```

?

This is explicitly deferred until polling becomes a product limitation.

---

# 13.98 API Acceptance Criteria

Before implementation proceeds far into frontend development, the contracts must support:

```text
List recent traces.

Filter traces.

Open one trace.

Render its waterfall.

Inspect one span.

Show whether the trace is complete.

Show whether analysis is pending.

Display current findings.

Highlight every span referenced by a finding.

Navigate from service to related traces.

Render the observed dependency graph.

Show when TraceForge itself is unhealthy.
```

No frontend requirement in the defined v0.1 workflow should require direct database knowledge or duplicate diagnostic computation.

---

## 13.99 API Principle

The API boundary should preserve the same separation used throughout TraceForge:

```text
canonical telemetry
        ↓
backend domain
        ↓
deterministic analysis
        ↓
structured API representation
        ↓
frontend presentation
```

The browser should receive enough information to understand and present TraceForge's conclusions.

It should not be responsible for inventing those conclusions itself.

---

## 13.100 Pre-Implementation Gate

With Sections 1–13 defined, TraceForge now has documented:

```text
product purpose
target users
user stories
product workflows

functional requirements
non-functional requirements
scope and non-goals

domain model
system architecture
data flow
storage model
analysis engine
core API contracts
```

This is sufficient to begin implementation without relying on architecture-by-accident.

Later sections may continue defining:

```text
failure handling details
security and privacy
testing strategy
deployment details
operational observability
technology ADRs
future evolution
```

but these no longer need to block the creation of the production codebase.

From this point onward, implementation changes that contradict the documented architecture SHOULD cause either:

```text
the implementation to change
```

or:

```text
the design document to be updated deliberately.
```

They should not silently diverge.
