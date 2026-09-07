# 6. Non-Functional Requirements

## 6.1 Purpose

This section defines the non-functional requirements of TraceForge.

Functional requirements describe **what the system must do**.

Non-functional requirements describe **how well the system must perform those functions and under what operational constraints**.

These requirements are especially important because architectural decisions should not be driven only by functionality.

For example, two designs may both satisfy:

> TraceForge SHALL ingest OpenTelemetry traces.

while differing significantly in:

* ingestion throughput;
* failure tolerance;
* operational complexity;
* storage efficiency;
* maintainability;
* deployment requirements.

The non-functional requirements in this section therefore provide constraints for later architecture and technology decisions.

Some numerical targets are intentionally provisional.

Where exact limits cannot yet be justified empirically, the requirement will define an initial design target that must later be validated through benchmarking.

---

# 6.2 Performance Requirements

## TF-NFR-PERF-001 — Interactive Trace List Response

Trace list operations intended for normal interactive use SHOULD complete quickly enough to preserve a responsive investigation workflow.

For the intended v0.1 deployment scale, common trace-list queries SHOULD target:

```text
p95 response time ≤ 500 ms
```

under normal local or development workloads.

This includes common filters such as:

* service;
* status;
* operation;
* duration;
* recent time range.

This target excludes network latency outside the TraceForge deployment itself.

---

## TF-NFR-PERF-002 — Trace Detail Response

Retrieval of a typical trace SHOULD target:

```text
p95 response time ≤ 500 ms
```

for traces within the normal expected size range.

A larger trace MAY require more time, but the system SHOULD avoid architectural designs where trace reconstruction requires repeated expensive database queries for each individual span.

---

## TF-NFR-PERF-003 — UI Interaction Responsiveness

Common client-side interactions SHOULD feel immediate.

Interactions such as:

* expanding a span;
* selecting a finding;
* highlighting related spans;
* navigating within an already loaded waterfall;

SHOULD generally not require a network round trip unless additional data is genuinely required.

The UI SHOULD target smooth interaction with traces containing at least several hundred spans.

---

## TF-NFR-PERF-004 — Telemetry Ingestion Throughput

TraceForge v0.1 SHOULD support sustained ingestion appropriate for small development and staging environments.

The initial benchmark target SHOULD be at least:

```text
1,000 spans / second sustained
```

on a typical modern development machine without data loss under healthy conditions.

A stretch target of:

```text
5,000 spans / second
```

MAY be used for performance evaluation.

These numbers are design targets rather than enterprise scalability claims.

They must be validated through benchmark testing before being treated as guaranteed limits.

---

## TF-NFR-PERF-005 — Analysis Delay

Diagnostic analysis SHOULD become available shortly after a trace becomes eligible for analysis.

Under normal load, TraceForge SHOULD target:

```text
p95 analysis completion ≤ 2 seconds
```

after a trace is considered complete or otherwise eligible for analysis.

The exact timing depends on the final trace completion policy.

The user SHOULD not normally perceive diagnostic analysis as a long-running asynchronous job.

---

## TF-NFR-PERF-006 — Analysis Complexity Awareness

Diagnostic algorithms SHOULD have defined computational complexity.

Algorithms operating on a trace SHOULD preferably remain near:

```text
O(n)
```

or:

```text
O(n log n)
```

with respect to the number of spans, where practical.

Algorithms requiring:

```text
O(n²)
```

or worse SHOULD be justified explicitly and evaluated against expected trace sizes.

---

# 6.3 Scalability Requirements

## TF-NFR-SCALE-001 — Initial Scale Target

TraceForge v0.1 SHALL optimize for small distributed applications rather than enterprise telemetry infrastructure.

A representative deployment target is approximately:

```text
3–20 application services
hundreds to thousands of requests during a development session
tens to hundreds of thousands of stored spans
```

The architecture SHOULD remain usable beyond these values where practical, but these represent the primary design environment.

---

## TF-NFR-SCALE-002 — Moderate Growth Without Architectural Rewrite

The v0.1 architecture SHOULD avoid unnecessary decisions that make moderate scaling impossible.

Increasing workload from:

```text
5 services
```

to:

```text
30–50 services
```

or from:

```text
100,000 stored spans
```

to:

```text
several million stored spans
```

SHOULD ideally require configuration, indexing, or infrastructure changes rather than a complete redesign of the system.

This requirement does not imply that TraceForge must support enterprise scale.

---

## TF-NFR-SCALE-003 — No Premature Distributed Architecture

TraceForge SHALL NOT introduce distributed infrastructure solely to satisfy hypothetical future scale.

Examples include introducing:

* Kafka;
* distributed databases;
* clustered caches;
* service meshes;
* multi-node analysis workers;

without demonstrated requirements.

Scale-related complexity must be justified through observed bottlenecks or clearly defined future product requirements.

---

# 6.4 Reliability Requirements

## TF-NFR-REL-001 — Graceful Subsystem Failure

Failure of one subsystem SHOULD NOT unnecessarily make unrelated capabilities unavailable.

Examples:

* analysis failure SHOULD NOT prevent raw trace inspection;
* UI failure SHOULD NOT affect telemetry ingestion;
* one detector failure SHOULD NOT invalidate all analysis;
* one malformed telemetry batch SHOULD NOT crash the ingestion process.

---

## TF-NFR-REL-002 — No Silent Data Corruption

TraceForge SHALL prefer explicit failure over silent corruption.

If telemetry cannot be interpreted safely, the system SHOULD:

```text
reject it
mark it incomplete
record an error
```

rather than silently inventing structural relationships.

---

## TF-NFR-REL-003 — Duplicate Safety

Retrying telemetry delivery SHALL NOT normally create duplicate logical spans.

The system SHOULD be idempotent with respect to repeated ingestion of identical:

```text
trace_id + span_id
```

pairs.

The exact conflict policy for non-identical duplicates will be defined later.

---

## TF-NFR-REL-004 — Partial Availability

Where possible, TraceForge SHOULD degrade gracefully.

For example:

```text
analysis unavailable
```

should still permit:

```text
trace retrieval
span inspection
service inspection
```

if storage remains healthy.

Similarly, temporary ingestion failure SHOULD NOT prevent viewing already persisted traces.

---

## TF-NFR-REL-005 — Restart Recovery

TraceForge components SHOULD recover safely after process restart.

Persisted telemetry SHALL remain available.

Pending analysis SHOULD either:

* resume;
* be safely retried;
* or be marked clearly as incomplete.

A restart SHALL NOT silently leave traces permanently stuck in an indeterminate state.

---

## TF-NFR-REL-006 — Persistent State Consistency

Persistent state transitions SHALL be designed to prevent logically impossible states where practical.

For example:

```text
analysis_state = COMPLETE
```

SHALL NOT exist if no analysis result or explicit no-finding result was successfully persisted.

---

# 6.5 Data Integrity Requirements

## TF-NFR-DATA-001 — Identifier Integrity

Trace IDs and span IDs SHALL be preserved exactly.

TraceForge SHALL NOT generate replacement identifiers for valid incoming telemetry unless creating an explicitly separate internal identifier.

---

## TF-NFR-DATA-002 — Timestamp Precision

TraceForge SHALL preserve sufficient timestamp precision to accurately reconstruct span ordering and overlap.

The internal representation SHOULD avoid unnecessary loss of OpenTelemetry timestamp precision.

---

## TF-NFR-DATA-003 — Source Evidence Preservation

Derived analysis SHALL NOT overwrite or mutate the original telemetry used as evidence.

Normalization and derived values SHOULD be stored separately from raw or canonical span data.

---

## TF-NFR-DATA-004 — Deterministic Re-analysis

Given:

* identical telemetry;
* identical detector configuration;
* identical detector version;

TraceForge SHOULD produce equivalent deterministic findings.

This requirement supports:

* reproducibility;
* debugging;
* regression testing;
* future re-analysis.

---

# 6.6 Security Requirements

## TF-NFR-SEC-001 — Secure Defaults

TraceForge SHOULD use conservative defaults.

Features that expose TraceForge outside the local machine or trusted development network SHOULD require explicit configuration.

The initial deployment SHOULD assume a development-oriented trust boundary rather than unrestricted public internet exposure.

---

## TF-NFR-SEC-002 — No Proprietary Application Credentials

TraceForge SHOULD NOT require application credentials that are unrelated to telemetry collection.

Instrumentation SHOULD use standard OpenTelemetry mechanisms wherever possible.

---

## TF-NFR-SEC-003 — Sensitive Telemetry Awareness

TraceForge SHALL treat telemetry as potentially sensitive.

Attributes, events, SQL statements, URLs, headers, exception messages, and resource metadata MAY contain:

* authentication tokens;
* user identifiers;
* email addresses;
* internal hostnames;
* database values;
* API keys;
* personally identifiable information.

The security design SHALL therefore include a future redaction and filtering strategy before TraceForge is recommended for sensitive production workloads.

---

## TF-NFR-SEC-004 — Secret Handling

TraceForge configuration secrets SHALL NOT be:

* hardcoded in source code;
* committed to the repository;
* displayed unnecessarily in the UI;
* written into ordinary application logs.

Secrets SHOULD be provided using environment variables, secret files, or another documented configuration mechanism.

---

## TF-NFR-SEC-005 — Dependency Security

Third-party dependencies SHOULD be minimized where practical and kept current.

Security scanning SHOULD eventually be integrated into CI.

Dependency choices SHOULD consider:

* maintenance activity;
* vulnerability history;
* ecosystem maturity;
* transitive dependency cost.

---

## TF-NFR-SEC-006 — Input Validation

All externally supplied input SHALL be treated as untrusted.

This includes:

* OTLP payloads;
* API query parameters;
* trace identifiers;
* filter values;
* configuration values.

Input SHALL be validated before use in database queries, file access, rendering, or analysis.

---

## TF-NFR-SEC-007 — Safe Telemetry Rendering

Telemetry attributes and exception data displayed in the browser SHALL be rendered safely.

Untrusted telemetry text SHALL NOT be capable of introducing executable browser content.

---

# 6.7 Privacy Requirements

## TF-NFR-PRIV-001 — Data Minimization

TraceForge SHOULD store only telemetry required for its defined functionality.

The system SHOULD NOT persist additional application data merely because it is available.

---

## TF-NFR-PRIV-002 — Retention Awareness

Telemetry SHALL have a configurable retention strategy before TraceForge is considered appropriate for long-running deployments.

Automatic retention MAY be deferred from the earliest implementation milestone, but the storage design SHOULD not assume permanent retention.

---

## TF-NFR-PRIV-003 — Deletion Capability

The architecture SHOULD allow stored telemetry to be deleted by time range or through a defined retention process.

This capability does not need to be exposed as an advanced administrative interface in the first release.

---

# 6.8 Portability Requirements

## TF-NFR-PORT-001 — Containerized Deployment

TraceForge v0.1 SHALL support container-based deployment.

The primary supported environment SHALL be Docker Compose.

---

## TF-NFR-PORT-002 — Host Operating Systems

The development and deployment workflow SHOULD remain usable on common development environments including:

* Linux;
* Windows through Docker;
* macOS through Docker.

Platform-specific application logic SHOULD be avoided.

---

## TF-NFR-PORT-003 — Standard Configuration

Runtime configuration SHOULD use broadly supported mechanisms such as:

* environment variables;
* configuration files;
* Docker Compose configuration.

TraceForge SHOULD avoid requiring a proprietary external configuration service.

---

## TF-NFR-PORT-004 — No Kubernetes Requirement

Kubernetes SHALL NOT be required for v0.1.

A developer SHOULD be able to use the full initial TraceForge feature set without access to a Kubernetes cluster.

---

# 6.9 Operability Requirements

## TF-NFR-OPS-001 — Single-Command Development Startup

The development environment SHOULD aim to provide a workflow approximately equivalent to:

```text
docker compose up
```

for required infrastructure.

Application development processes MAY run separately where this improves developer experience.

---

## TF-NFR-OPS-002 — Health Checks

Major runtime components SHALL expose machine-readable health information where appropriate.

Health checks SHOULD distinguish between:

```text
process alive
```

and:

```text
required dependencies available
```

where technically useful.

---

## TF-NFR-OPS-003 — Actionable Internal Logging

TraceForge SHALL produce structured or consistently formatted internal logs sufficient to diagnose its own failures.

Logs SHOULD contain:

* component;
* timestamp;
* severity;
* relevant internal identifiers;
* error context.

Logs SHOULD avoid unnecessarily reproducing sensitive telemetry payloads.

---

## TF-NFR-OPS-004 — Clear Configuration Errors

Invalid startup configuration SHOULD fail clearly.

For example:

```text
DATABASE_URL is missing
```

is preferable to:

```text
internal connection error
```

after partial startup.

---

## TF-NFR-OPS-005 — Database Migration Safety

Persistent schema changes SHALL use a repeatable migration mechanism.

The database schema SHALL NOT depend on developers manually executing undocumented SQL changes.

---

# 6.10 Maintainability Requirements

## TF-NFR-MAINT-001 — Clear Component Boundaries

Major system responsibilities SHOULD have explicit boundaries.

Likely responsibilities include:

```text
ingestion
normalization
persistence
trace reconstruction
analysis
query API
frontend
```

The exact component structure will be defined later.

A change to one responsibility SHOULD not unnecessarily require changes throughout the entire codebase.

---

## TF-NFR-MAINT-002 — Detector Extensibility

The analysis engine SHOULD allow additional detectors to be introduced without modifying unrelated diagnostic algorithms.

A detector SHOULD have a clear contract defining:

```text
required input
execution
finding output
failure behaviour
```

---

## TF-NFR-MAINT-003 — Shared Domain Definitions

Core concepts such as:

* trace states;
* finding types;
* severity;
* confidence;
* span relationships;

SHOULD have canonical definitions.

Different components SHOULD NOT independently invent conflicting interpretations of these concepts.

---

## TF-NFR-MAINT-004 — Limited Hidden Behaviour

Important system behaviour SHOULD be explicit in code and configuration.

TraceForge SHOULD avoid excessive reliance on framework magic that makes critical data flow difficult to understand or test.

---

## TF-NFR-MAINT-005 — Documentation Synchronization

Architecture-affecting implementation changes SHOULD update the corresponding design documentation or ADR.

The codebase and design document SHOULD not intentionally diverge without documenting why.

---

# 6.11 Testability Requirements

## TF-NFR-TEST-001 — Deterministic Test Scenarios

Core diagnostic behaviour SHALL be testable using deterministic telemetry fixtures or reproducible demo scenarios.

---

## TF-NFR-TEST-002 — Detector Unit Testing

Each diagnostic detector SHALL be independently testable.

Tests SHOULD include:

```text
positive detection
negative detection
boundary conditions
incomplete telemetry
malformed input
```

where applicable.

---

## TF-NFR-TEST-003 — Integration Testing

TraceForge SHALL support automated integration tests covering important flows such as:

```text
OTLP input
    ↓
persistence
    ↓
trace reconstruction
    ↓
analysis
    ↓
API result
```

---

## TF-NFR-TEST-004 — Performance Testing

The project SHOULD contain repeatable benchmarks for at least:

* span ingestion throughput;
* trace retrieval;
* analysis execution.

Performance claims SHOULD be supported by measurements rather than assumptions.

---

## TF-NFR-TEST-005 — Failure Injection

Important failure scenarios SHOULD be reproducible in testing.

Examples include:

* database unavailable;
* malformed telemetry;
* duplicate spans;
* missing parents;
* detector exception;
* delayed spans.

---

# 6.12 Observability Requirements

TraceForge is itself an observability product and SHALL therefore be observable.

## TF-NFR-OBS-001 — Internal Metrics

TraceForge SHOULD expose operational metrics including, where appropriate:

```text
spans received
spans rejected
ingestion rate
traces created
traces awaiting completion
analysis count
analysis failures
analysis duration
database query duration
```

---

## TF-NFR-OBS-002 — Distributed Tracing of TraceForge

TraceForge SHOULD eventually support instrumentation of its own internal request flows using OpenTelemetry.

Where practical, TraceForge SHOULD be capable of producing telemetry compatible with its own ingestion model.

---

## TF-NFR-OBS-003 — Self-Diagnostic Visibility

System failures SHOULD be visible through the TraceForge System interface where useful.

Users SHOULD NOT need to inspect container logs for every ordinary operational issue.

---

# 6.13 Usability Requirements

## TF-NFR-UX-001 — Diagnostic-First Presentation

The UI SHALL prioritize:

```text
meaning
```

before:

```text
raw telemetry complexity
```

while preserving access to the underlying telemetry.

---

## TF-NFR-UX-002 — Consistent Terminology

Terms such as:

```text
trace
span
finding
service
severity
confidence
incomplete
analysis failed
```

SHALL have consistent meanings throughout the product.

---

## TF-NFR-UX-003 — Clear System States

The interface SHALL clearly distinguish important states such as:

```text
no telemetry
telemetry processing
trace incomplete
analysis pending
analysis complete with no findings
analysis complete with findings
analysis failed
system unhealthy
```

---

## TF-NFR-UX-004 — Investigation Continuity

Navigation SHOULD preserve investigation context where practical.

For example, moving from:

```text
finding
    ↓
related span
```

SHOULD not require the developer to reconstruct the original filtering or trace context manually.

---

## TF-NFR-UX-005 — Technical Precision

TraceForge is a developer tool.

The interface SHOULD prefer technically accurate language over oversimplified terminology.

Simplification SHOULD improve comprehension without misrepresenting distributed-system behaviour.

---

# 6.14 Compatibility Requirements

## TF-NFR-COMPAT-001 — OpenTelemetry Standards Alignment

TraceForge SHOULD follow OpenTelemetry specifications and semantic conventions wherever doing so is practical.

TraceForge SHOULD avoid proprietary reinterpretation of standard telemetry fields unless necessary for internal derived data.

---

## TF-NFR-COMPAT-002 — Version Evolution

The ingestion architecture SHOULD tolerate reasonable evolution of OpenTelemetry semantic conventions.

Analysis logic SHOULD avoid unnecessary coupling to one exact attribute name where semantic evolution can be handled safely through normalization.

---

## TF-NFR-COMPAT-003 — API Evolution

Public TraceForge APIs SHOULD be designed so that common additions do not require breaking changes.

Explicit API versioning MAY be introduced if needed.

The v0.1 internal development stage does not require premature version proliferation.

---

# 6.15 Resource Usage Requirements

## TF-NFR-RESOURCE-001 — Development Machine Suitability

TraceForge v0.1 SHOULD be practical to run on a developer workstation.

A typical development deployment SHOULD NOT require unusually large CPU or memory resources when processing the intended workload.

---

## TF-NFR-RESOURCE-002 — Bounded Background Work

Background processes such as analysis and cleanup SHOULD operate with bounded resource consumption.

TraceForge SHOULD avoid unlimited:

* worker creation;
* in-memory queues;
* cached traces;
* retry loops.

---

## TF-NFR-RESOURCE-003 — Storage Growth Visibility

TraceForge SHOULD make storage growth understandable.

The system SHOULD eventually expose at least:

```text
stored trace count
stored span count
database/storage size
```

or equivalent information.

---

# 6.16 Development Quality Requirements

## TF-NFR-DEV-001 — Static Analysis

The project SHOULD use appropriate static analysis and linting for each implementation language.

---

## TF-NFR-DEV-002 — Automated Formatting

Code formatting SHOULD be deterministic and automated.

Formatting disagreements SHOULD not consume code review effort.

---

## TF-NFR-DEV-003 — CI Validation

The repository SHOULD include automated CI validation covering at least:

```text
build
lint/static analysis
tests
```

before v0.1 is considered publishable.

---

## TF-NFR-DEV-004 — Reproducible Development Environment

The repository SHOULD contain enough configuration and documentation for another developer to build and run TraceForge without relying on undocumented local state.

---

## TF-NFR-DEV-005 — Intentional Dependencies

New major dependencies SHOULD solve an explicit requirement.

A library or infrastructure component SHOULD NOT be introduced solely because it is common in similar systems.

---

# 6.17 v0.1 Non-Functional Priorities

The highest-priority non-functional goals for v0.1 are:

```text
1. Correctness
2. Evidence integrity
3. Maintainability
4. Reliable local operation
5. Testability
6. Interactive performance
7. Moderate scalability
8. Operational simplicity
```

This ordering is intentional.

For example:

```text
A detector that runs in 20 ms but produces unreliable conclusions
```

is worse than:

```text
A detector that runs in 100 ms and produces reproducible,
evidence-backed results.
```

Likewise:

```text
A horizontally scalable architecture requiring seven infrastructure
services
```

is worse for the initial product than:

```text
A simpler architecture that comfortably handles the intended workload.
```

TraceForge should optimize for the requirements of the product that exists rather than the hypothetical requirements of a future enterprise platform.

---

# 6.18 Non-Functional Acceptance Principle

A technically working feature is not automatically a successful feature.

For any core TraceForge capability, the implementation should eventually be evaluated against three questions:

```text
Does it produce the correct result?

Does it remain understandable and verifiable?

Does it operate reliably within the intended workload?
```

If the answer to any of these is consistently no, the feature should not be considered complete even if its functional requirement is technically satisfied.
