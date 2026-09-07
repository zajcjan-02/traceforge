# 8. Domain Model

## 8.1 Purpose

This section defines the conceptual model used internally by TraceForge.

The domain model provides a shared vocabulary for:

* telemetry ingestion;
* trace reconstruction;
* persistence;
* analysis;
* APIs;
* frontend presentation;
* testing.

TraceForge receives data structured according to OpenTelemetry, but its internal model SHOULD NOT simply mirror the incoming protocol representation.

OpenTelemetry describes telemetry transport and semantics.

TraceForge additionally needs to represent concepts such as:

* trace completeness;
* derived service dependencies;
* analysis state;
* critical paths;
* diagnostic findings;
* evidence;
* normalized operations.

These concepts belong to the TraceForge domain rather than directly to OpenTelemetry.

The intended transformation is therefore:

```text
OpenTelemetry representation
        ↓
validation
        ↓
canonical telemetry model
        ↓
TraceForge domain model
        ↓
derived analysis
```

---

## 8.2 Domain Model Principles

The domain model SHALL follow several principles.

#### Preserve source telemetry

TraceForge SHALL preserve the information required to inspect and verify the telemetry from which conclusions were derived.

Derived information SHALL NOT overwrite source telemetry.

---

#### Separate observed facts from derived interpretation

For example:

```text
Observed fact:
Span A called payment-service and lasted 2.1 seconds.
```

is different from:

```text
Derived conclusion:
payment-service was a major latency contributor.
```

The domain model SHALL preserve this distinction.

---

### Use stable internal concepts

External telemetry conventions may evolve.

Core TraceForge concepts such as:

```text
Trace
Span
Service
Finding
Evidence
Dependency
```

SHOULD remain stable even if ingestion normalization must adapt to changes in telemetry conventions.

---

### Avoid UI-specific domain objects

The domain model SHOULD describe the system being observed and TraceForge's interpretation of it.

It SHOULD NOT contain concepts created solely because a particular UI component exists.

For example:

```text
Finding
```

is a domain concept.

```text
FindingCard
```

is not.

---

## 8.3 High-Level Domain Relationships

The initial domain model can be represented conceptually as:

```text
Service
   ↑
   │
   │ associated with
   │
Span ────────────────┐
 ↑                   │
 │ parent/child      │
 │                   │
 └────── Trace ──────┘
           │
           │ analyzed into
           ↓
        Finding
           │
           ↓
        Evidence
           │
           └──── references Span(s)

Service
   │
   └──── observed relationship ──── Service
                    │
                    ↓
                Dependency
```

Additional derived concepts include:

```text
Operation
NormalizedOperation
CriticalPath
AnalysisRun
Detector
```

These concepts are defined below.

---

## 8.4 Trace

A **Trace** represents one observed distributed execution context.

In most cases, a trace corresponds approximately to one request or workflow that crosses one or more components.

Examples include:

```text
HTTP request
RPC request
background operation
message-processing workflow
```

For TraceForge v0.1, the primary focus is distributed request execution.

---

### 8.4.1 Trace Identity

A trace SHALL be identified primarily by its OpenTelemetry trace identifier.

Conceptually:

```text
Trace {
    trace_id
}
```

TraceForge MAY also use a separate internal database identifier.

If such an identifier exists, it SHALL NOT replace or mutate the original trace identifier.

---

### 8.4.2 Trace Properties

A Trace may contain:

```text
Trace {
    trace_id

    observed_start_time
    observed_end_time
    duration

    root_span_candidates[]

    spans[]

    participating_services[]

    status

    completeness_state
    analysis_state

    findings[]

    created_at
    updated_at
}
```

This structure is conceptual.

The eventual persistence schema MAY normalize these properties across multiple tables.

---

### 8.4.3 Trace Completeness

Trace completeness describes whether TraceForge believes the received span set sufficiently represents the observed execution.

Initial states:

```text
PROCESSING
COMPLETE
INCOMPLETE
```

#### PROCESSING

Additional spans may reasonably still arrive.

#### COMPLETE

TraceForge's completion policy considers the trace sufficiently complete for normal analysis.

#### INCOMPLETE

The trace has exceeded the completion policy while containing known structural gaps or inconsistencies.

Completeness SHALL NOT imply success.

For example:

```text
COMPLETE + ERROR
```

is a valid state.

---

### 8.4.4 Trace Analysis State

Analysis state SHALL remain independent of trace completeness.

Possible states include:

```text
PENDING
RUNNING
COMPLETE
PARTIAL
FAILED
```

Examples:

```text
Trace:
COMPLETE

Analysis:
COMPLETE
```

means normal successful analysis.

```text
Trace:
INCOMPLETE

Analysis:
PARTIAL
```

means some detectors could still produce valid results.

```text
Trace:
COMPLETE

Analysis:
FAILED
```

means telemetry is available but analysis failed.

---

## 8.5 Span

A **Span** represents a single timed operation within a trace.

Examples include:

```text
HTTP server request
HTTP client request
database query
RPC call
cache access
internal application operation
```

A span is an observed telemetry object.

TraceForge SHALL NOT assume that one span necessarily represents one service call.

---

### 8.5.1 Span Identity

A span SHALL be identified within a trace by:

```text
trace_id
span_id
```

The pair:

```text
(trace_id, span_id)
```

SHALL uniquely identify a logical span within TraceForge.

---

### 8.5.2 Span Properties

A conceptual Span contains:

```text
Span {
    trace_id
    span_id
    parent_span_id?

    name
    kind

    start_time
    end_time
    duration

    status

    service_id?

    attributes
    events
    resource
    instrumentation_scope

    normalized_operation?
}
```

Additional derived fields MAY be added where useful.

---

### 8.5.3 Parent Relationship

A span MAY reference another span as its parent.

Conceptually:

```text
parent_span_id -> Span.span_id
```

TraceForge SHALL permit:

```text
parent_span_id exists
```

while:

```text
matching parent span is absent
```

because incomplete telemetry is a valid runtime condition.

---

### 8.5.4 Root Span

A span with no observed parent relationship may be a candidate root.

TraceForge SHALL NOT assume that every trace contains exactly one valid root span.

Possible situations include:

```text
one root
multiple roots
missing root
orphaned subtrees
```

These conditions may affect trace completeness and analysis confidence.

---

## 8.6 Span Timing Model

Timing is fundamental to TraceForge analysis.

Every span may define:

```text
start_time
end_time
duration
```

where:

```text
duration = end_time - start_time
```

for valid timestamps.

TraceForge SHALL distinguish several timing concepts.

---

### 8.6.1 Span Duration

The wall-clock duration of an individual span.

---

### 8.6.2 Trace Wall-Clock Duration

The elapsed time between the earliest relevant trace start and latest relevant trace completion.

This is not equivalent to accumulated span duration.

---

### 8.6.3 Accumulated Span Duration

The sum of durations of multiple spans.

For concurrent spans:

```text
Span A = 500 ms
Span B = 700 ms
```

the accumulated duration may be:

```text
1200 ms
```

while wall-clock contribution may be only:

```text
700 ms
```

if they execute completely in parallel.

---

### 8.6.4 Exclusive Span Time

TraceForge MAY derive the amount of time within a span not accounted for by child span execution.

Conceptually:

```text
exclusive_time =
span_duration
-
covered_child_intervals
```

This calculation must consider overlapping children.

It SHALL NOT simply subtract the sum of all child durations.

---

## 8.7 Service

A **Service** represents a logically named application component observed through telemetry.

Examples:

```text
gateway
orders-service
payment-service
inventory-service
```

Services are discovered dynamically from telemetry.

---

### 8.7.1 Service Identity

TraceForge SHOULD derive service identity from normalized telemetry metadata.

Conceptually:

```text
Service {
    service_id
    service_name
}
```

The exact identity rules will be defined during normalization design.

TraceForge SHALL tolerate spans for which no reliable service identity is available.

Such spans MAY be associated with an:

```text
unknown
```

or equivalent internal state rather than rejected.

---

### 8.7.2 Service Properties

A Service may expose derived information such as:

```text
Service {
    service_id
    name

    first_seen
    last_seen

    observed_operations[]
    dependencies[]

    recent_trace_count
    recent_error_count
}
```

Many of these values may be calculated dynamically rather than stored directly.

---

## 8.8 Operation

An **Operation** represents the logical activity performed by a span.

Examples:

```text
GET /orders/{id}
POST /charge
SELECT product
Redis GET
```

The operation concept allows TraceForge to reason about structurally similar work across spans.

---

### 8.8.1 Raw Operation

The raw operation corresponds closely to telemetry received from the application.

Example:

```text
GET /products/142
```

---

### 8.8.2 Normalized Operation

A **NormalizedOperation** represents structurally equivalent operations using a stable generalized representation.

For example:

```text
GET /products/142
GET /products/871
GET /products/992
```

may normalize to:

```text
GET /products/{id}
```

Similarly:

```sql
SELECT name FROM product WHERE id = 142
SELECT name FROM product WHERE id = 871
```

may normalize to a common structural form.

The precise normalization algorithm SHALL depend on operation type.

---

### 8.8.3 Operation Type

TraceForge SHOULD categorize operations where sufficient evidence exists.

Example categories:

```text
HTTP
RPC
DATABASE
CACHE
MESSAGING
INTERNAL
UNKNOWN
```

This classification enables detector-specific behaviour.

For example:

```text
RepeatedDatabaseOperationDetector
```

should normally operate only on database-like operations.

---

## 8.9 Service Dependency

A **ServiceDependency** represents an observed runtime interaction between two services.

Conceptually:

```text
ServiceDependency {
    source_service
    target_service
}
```

For example:

```text
orders-service
        ↓
payment-service
```

The relationship exists because telemetry provided evidence that one service invoked another.

---

### 8.9.1 Observed, Not Configured

A dependency means:

> TraceForge observed this relationship in telemetry.

It does not mean:

> This relationship is guaranteed to exist in every deployment.

The graph is therefore an **observed runtime topology**.

---

### 8.9.2 Dependency Evidence

Every dependency SHOULD be derivable from one or more span relationships.

Conceptually:

```text
ServiceDependency
        ↓
supporting trace(s)
        ↓
supporting span relationship(s)
```

The dependency graph must remain explainable.

---

### 8.9.3 Dependency Direction

Dependencies SHALL be directional.

```text
orders-service → payment-service
```

is different from:

```text
payment-service → orders-service
```

Both relationships MAY exist independently.

---

## 8.10 Finding

A **Finding** represents a diagnostic conclusion generated by TraceForge analysis.

Findings are not raw telemetry.

They are derived objects.

Examples:

```text
Major latency contributor
Repeated database operation
Likely originating failure
Repeated downstream operation
```

---

#### 8.10.1 Finding Properties

A conceptual Finding contains:

```text
Finding {
    finding_id

    trace_id

    type

    severity
    confidence

    title
    summary

    evidence[]

    related_span_ids[]

    detector_id
    detector_version

    created_at
}
```

Additional structured fields MAY be specific to finding types.

---

### 8.10.2 Finding Type

Finding type identifies the class of detected behaviour.

Possible v0.1 values include:

```text
MAJOR_LATENCY_CONTRIBUTOR
REPEATED_DATABASE_OPERATION
LIKELY_ERROR_ORIGIN
ERROR_PROPAGATION
REPEATED_DOWNSTREAM_OPERATION
```

The final enum or type system will be defined during analysis-engine design.

---

## 8.11 Severity

**Severity** represents the potential importance of a finding.

It answers approximately:

> If this finding is correct, how significant is the observed behaviour?

A possible model is:

```text
INFO
LOW
MEDIUM
HIGH
CRITICAL
```

The final severity scale is not yet fixed.

Severity SHALL NOT represent confidence.

---

## 8.12 Confidence

**Confidence** represents how strongly the available telemetry supports a finding's interpretation.

It answers approximately:

> How certain is TraceForge that this interpretation follows from the available evidence?

A possible representation is:

```text
LOW
MEDIUM
HIGH
```

or a numeric score.

The exact model will be decided during analysis design.

---

### 8.12.1 Severity and Confidence Are Independent

The following must be representable:

```text
Severity: HIGH
Confidence: LOW
```

Example:

A suspicious operation could potentially explain a serious failure, but incomplete telemetry makes the conclusion uncertain.

Similarly:

```text
Severity: LOW
Confidence: HIGH
```

may describe a minor inefficiency observed with very strong evidence.

---

## 8.13 Evidence

**Evidence** represents the observable facts supporting a finding.

Evidence is essential because TraceForge's diagnostic philosophy requires every conclusion to be verifiable.

Conceptually:

```text
Evidence {
    evidence_type

    related_span_ids[]

    observed_values

    description
}
```

---

### 8.13.1 Evidence Examples

For repeated database operations:

```text
count = 34
normalized_operation = SELECT product WHERE id = ?
combined_duration = 2070 ms
sequential_count = 31
```

For latency analysis:

```text
span_id = ...
critical_path_contribution = 2310 ms
trace_duration = 2810 ms
```

For error origin:

```text
first_error_timestamp = ...
originating_span_id = ...
propagated_error_span_ids = [...]
```

---

### 8.13.2 Structured Evidence

Evidence SHOULD be structured wherever practical.

The system SHOULD prefer:

```text
{
    count: 34,
    combined_duration_ms: 2070
}
```

over storing only:

```text
"34 repeated queries took around two seconds."
```

Human-readable text can be generated from structured evidence.

Structured evidence improves:

* reproducibility;
* API stability;
* frontend flexibility;
* testing;
* future explanation systems.

---

## 8.14 Analysis Run

An **AnalysisRun** represents one execution of the TraceForge analysis process against a trace.

Conceptually:

```text
AnalysisRun {
    analysis_run_id
    trace_id

    started_at
    completed_at

    state

    detector_results[]
}
```

This concept allows TraceForge to distinguish findings produced:

* at different times;
* by different detector versions;
* after late-arriving spans;
* after re-analysis.

---

### 8.14.1 Re-analysis

A trace MAY be analyzed more than once.

Example:

```text
Trace initially received
        ↓
analysis run 1
        ↓
late span arrives
        ↓
trace changes
        ↓
analysis run 2
```

The domain model SHALL allow findings from outdated analysis runs to be replaced, superseded, or otherwise distinguished from current findings.

The precise persistence policy will be defined later.

---

## 8.15 Detector

A **Detector** represents one independent diagnostic algorithm.

Examples:

```text
CriticalPathDetector
LatencyContributorDetector
RepeatedDatabaseOperationDetector
ErrorOriginDetector
```

The domain concept is:

```text
Detector {
    detector_id
    version

    required_input
    configuration
}
```

A detector consumes trace data and produces:

```text
zero or more Findings
```

or an explicit execution failure.

---

### 8.15.1 Detector Contract

Each detector SHALL eventually define:

```text
required telemetry
eligibility conditions
analysis algorithm
finding output
confidence rules
failure behaviour
computational complexity
```

This prevents detector behaviour from becoming undocumented application logic.

---

## 8.16 Detector Result

A detector execution should have an explicit result even when it produces no finding.

Conceptually:

```text
DetectorResult {
    detector_id

    state

    findings[]

    failure_reason?
}
```

Possible states may include:

```text
SUCCESS_WITH_FINDINGS
SUCCESS_NO_FINDINGS
SKIPPED_INSUFFICIENT_DATA
FAILED
```

This distinction is important.

The following are not equivalent:

```text
No repeated query detected.
```

```text
Repeated query detector could not run.
```

```text
Repeated query detector was not applicable.
```

---

## 8.17 Critical Path

A **CriticalPath** is a derived representation of the sequence or set of execution intervals that determine the observed completion time of a trace.

Conceptually:

```text
CriticalPath {
    trace_id
    segments[]
    duration
}
```

Each segment references one or more spans or derived execution intervals.

The critical path SHALL be treated as derived analysis rather than original telemetry.

---

### 8.17.1 Critical Path Is Not Necessarily a Simple Tree Path

Because spans may:

* overlap;
* represent asynchronous execution;
* contain sibling concurrency;

the effective latency path may require temporal reasoning rather than simple parent traversal.

The exact algorithm is intentionally deferred to the analysis-engine design section.

---

## 8.18 Error Observation

An **ErrorObservation** represents an observed indication of failure associated with a span.

Potential evidence may include:

```text
span error status
exception event
HTTP error status
RPC failure status
```

TraceForge MAY normalize these representations internally.

Conceptually:

```text
ErrorObservation {
    span_id

    error_type
    timestamp?

    source
    details
}
```

A normalized error observation allows error-analysis logic to operate without depending directly on every protocol-specific representation.

---

## 8.19 Error Propagation Chain

An **ErrorPropagationChain** is a derived relationship between one candidate originating error and subsequent errors associated with the same execution path.

Conceptually:

```text
ErrorPropagationChain {
    candidate_origin

    propagated_errors[]

    confidence
}
```

This representation is derived.

TraceForge SHALL NOT claim that propagation has occurred solely because multiple spans contain errors.

Temporal and structural relationships must support the conclusion.

---

## 8.20 Trace Structural Issue

TraceForge SHOULD explicitly represent structural problems discovered while reconstructing telemetry.

Examples:

```text
MISSING_PARENT
MULTIPLE_ROOTS
INVALID_TIMESTAMPS
DUPLICATE_SPAN_CONFLICT
ORPHANED_SUBTREE
```

Conceptually:

```text
TraceStructuralIssue {
    type
    affected_spans[]
    details
}
```

These issues may influence:

* completeness state;
* detector eligibility;
* analysis confidence;
* UI warnings.

---

## 8.21 Canonical vs Derived Data

The TraceForge domain SHALL distinguish two broad categories of data.

#### Canonical telemetry data

Information directly received or faithfully normalized from telemetry.

Examples:

```text
trace ID
span ID
parent span ID
timestamps
attributes
events
resource metadata
```

#### Derived TraceForge data

Information calculated by TraceForge.

Examples:

```text
trace completeness
normalized operations
service dependencies
critical path
findings
severity
confidence
error propagation
```

The distinction should remain explicit in implementation and persistence.

---

## 8.22 Domain Invariants

The following invariants SHOULD hold throughout the system.

#### Span identity is stable

For a valid span:

```text
(trace_id, span_id)
```

uniquely identifies its logical telemetry object.

---

#### A span belongs to exactly one trace

A span SHALL NOT be associated with multiple trace IDs.

---

#### Parent relationships remain within a trace

If Span B is the parent of Span A:

```text
A.trace_id == B.trace_id
```

must hold.

A cross-trace parent reference SHALL be treated as invalid or structurally inconsistent telemetry.

---

#### Source telemetry is immutable

Derived analysis SHALL NOT modify the canonical span data on which it depends.

---

#### Every finding belongs to a trace

A diagnostic finding SHALL reference exactly one trace.

Cross-trace analysis MAY exist in future versions, but findings remain anchored to a specific investigation context unless the domain model is explicitly expanded.

---

#### Every finding has evidence

A finding SHALL NOT exist without structured or referenceable supporting evidence.

---

#### Detector failure is not equivalent to no finding

The domain SHALL preserve this distinction explicitly.

---

#### Analysis state and trace state are independent

A complete trace may have failed analysis.

An incomplete trace may have partial successful analysis.

---

## 8.23 Conceptual Aggregate Boundaries

The initial domain suggests several logical aggregates.

These are conceptual and do not yet prescribe database transaction boundaries.

#### Trace Aggregate

```text
Trace
├── Span[]
├── StructuralIssue[]
└── current analysis state
```

#### Analysis Aggregate

```text
AnalysisRun
├── DetectorResult[]
└── Finding[]
     └── Evidence[]
```

#### Service Aggregate

```text
Service
└── observed relationships
```

This separation may help prevent trace ingestion and diagnostic analysis from becoming one tightly coupled model.

---

## 8.24 Example Domain Representation

Consider the following request:

```text
gateway
  ↓
orders-service
  ↓
34 repeated product queries
```

Canonical telemetry might conceptually produce:

```text
Trace T1

Span S1
service = gateway
operation = GET /orders

Span S2
service = orders-service
parent = S1

Span S3...S36
service = orders-service
type = DATABASE
parent = S2
```

Normalization produces:

```text
S3...S36

normalized_operation =
SELECT product WHERE id = ?
```

Analysis produces:

```text
AnalysisRun A1

Detector:
RepeatedDatabaseOperationDetector

Finding F1:
type = REPEATED_DATABASE_OPERATION
severity = MEDIUM
confidence = HIGH

Evidence:
span_count = 34
combined_duration = 2070 ms
related_spans = S3...S36
```

The important distinction is:

```text
Spans S3...S36
```

are observed telemetry.

```text
normalized_operation
```

is derived normalization.

```text
Finding F1
```

is diagnostic interpretation.

These layers SHALL remain conceptually separate.

---

## 8.25 Domain Model Extension Rules

New domain concepts SHOULD be introduced only when they represent a meaningful product or analysis concept.

A new entity SHOULD NOT be created merely because:

* a database table would be convenient;
* a framework encourages it;
* the frontend needs a temporary presentation shape.

Before introducing a new domain concept, the design should answer:

```text
What real concept does this represent?

Is it observed or derived?

Who owns its lifecycle?

What other domain objects reference it?

Does it need persistent identity?

Can it be reproduced from existing information?
```

---

## 8.26 Open Domain Questions

The following questions remain intentionally unresolved.

### Q-DOMAIN-001 — Trace completion

What exact conditions cause a trace to transition from:

```text
PROCESSING
```

to:

```text
COMPLETE
```

or:

```text
INCOMPLETE
```

?

---

### Q-DOMAIN-002 — Service identity

What combination of telemetry attributes defines a unique service?

How should multiple instances of the same service be represented?

---

### Q-DOMAIN-003 — Operation normalization

Should normalized operations be:

* calculated during ingestion;
* calculated lazily during analysis;
* persisted after first calculation?

---

### Q-DOMAIN-004 — Finding lifecycle

When a late span changes analysis results, should old findings be:

* deleted;
* marked superseded;
* retained as historical analysis output?

---

### Q-DOMAIN-005 — Confidence representation

Should confidence use:

```text
LOW / MEDIUM / HIGH
```

or:

```text
0.0–1.0
```

or both?

---

### Q-DOMAIN-006 — Aggregate persistence

Should Trace metadata be stored explicitly or derived primarily from spans?

This decision has significant query and consistency implications and belongs in storage design.

---

## 8.27 Domain Model Principle

The core domain model can be summarized as:

```text
Telemetry describes what was observed.

TraceForge reconstruction describes how those
observations relate.

TraceForge analysis describes what those
relationships may mean.
```

These three layers should remain distinct throughout the architecture.

Doing so allows TraceForge to remain:

* explainable;
* testable;
* adaptable to telemetry changes;
* resistant to accidental coupling between ingestion, analysis, storage, and UI.
