# 12. Analysis Engine Design

## 12.1 Purpose

This section defines the architecture and behaviour of the TraceForge diagnostic analysis engine.

The analysis engine is the primary capability that differentiates TraceForge from a conventional distributed trace viewer.

Its responsibility is to transform reconstructed telemetry into:

```text
structured
evidence-backed
reproducible
diagnostic findings
```

The analysis engine SHALL NOT attempt to determine arbitrary source-code root causes.

Instead, it analyzes observable runtime behaviour and reduces the developer's investigation space.

The general model is:

```text
Canonical telemetry
        ↓
Reconstructed trace
        ↓
Shared derived analysis structures
        ↓
Independent diagnostic detectors
        ↓
Structured findings
        ↓
Evidence
```

---

## 12.2 Analysis Design Principles

The analysis engine SHALL follow these principles.

### Deterministic first

Given identical:

```text
trace revision
detector version
detector configuration
```

the engine SHOULD produce equivalent output.

---

### Evidence before explanation

A finding must first exist as structured data.

Human-readable explanation is derived from it.

---

### Observation and interpretation remain separate

Example:

```text
Observation:
34 structurally equivalent SQL operations occurred.
```

```text
Interpretation:
This may represent an N+1 access pattern.
```

The engine SHALL preserve this distinction.

---

### Detectors must fail independently

One detector failure SHOULD NOT prevent unrelated detectors from completing.

---

### Incomplete telemetry must affect certainty

A detector SHALL NOT produce strong conclusions if the telemetry required to support them is known to be missing.

---

### Analysis algorithms must be inspectable

The engine SHOULD favor algorithms that can be:

* understood;
* tested;
* benchmarked;
* explained;
* reproduced.

---

## 12.3 Analysis Pipeline

For each analysis job, the worker performs:

```text
Load trace revision
        ↓
Validate analysis eligibility
        ↓
Construct domain Trace
        ↓
Build shared derived structures
        ↓
Evaluate detector eligibility
        ↓
Execute detectors
        ↓
Collect DetectorResults
        ↓
Persist findings and evidence
        ↓
Publish analysis if revision remains current
```

---

## 12.4 Analysis Input

The analysis engine SHALL consume domain objects rather than:

```text
OTLP protobuf messages
SQLAlchemy entities
HTTP request objects
```

Conceptually:

```text
TraceAnalysisInput {
    trace
    spans
    structural_issues
    services
    trace_revision
}
```

The exact implementation type may differ.

---

## 12.5 Shared Analysis Context

Detectors frequently require the same derived information.

TraceForge SHOULD therefore construct a reusable:

```text
AnalysisContext
```

for each trace.

Conceptually:

```text
AnalysisContext {
    trace

    spans_by_id

    children_by_span_id
    parent_by_span_id

    root_candidates

    spans_by_service

    spans_by_operation_type

    error_observations

    temporal_index

    critical_path?

    structural_issues
}
```

This prevents individual detectors from repeatedly reconstructing the same structures.

---

## 12.6 Analysis Context Immutability

Once constructed for a trace revision, the `AnalysisContext` SHOULD be immutable during detector execution.

Detectors SHALL NOT modify:

```text
spans
parent relationships
normalized operations
critical path
```

shared with other detectors.

A detector produces output; it does not mutate the trace.

---

## 12.7 Detector Interface

Every detector SHALL implement a common conceptual contract.

For example:

```text
Detector {
    id
    version

    evaluate_eligibility(context)
    analyze(context)
}
```

The exact language-level interface will be defined during implementation.

A detector must expose:

```text
detector ID
detector version
eligibility requirements
configuration
output finding types
```

---

## 12.8 Detector Result

Every detector execution SHALL return an explicit result.

Possible outcomes:

```text
SUCCESS_WITH_FINDINGS
SUCCESS_NO_FINDINGS
SKIPPED_INSUFFICIENT_DATA
SKIPPED_NOT_APPLICABLE
FAILED
```

Conceptually:

```text
DetectorResult {
    detector_id
    detector_version

    state

    findings[]

    duration_ns

    failure_reason?
}
```

---

## 12.9 Detector Eligibility

A detector SHOULD determine whether sufficient telemetry exists before expensive analysis begins.

For example:

```text
RepeatedDatabaseOperationDetector
```

may require:

```text
at least two DATABASE operations
```

If a trace contains no database spans:

```text
SKIPPED_NOT_APPLICABLE
```

is preferable to:

```text
SUCCESS_NO_FINDINGS
```

because the detector did not meaningfully evaluate database repetition.

---

## 12.10 Insufficient Data

A detector should return:

```text
SKIPPED_INSUFFICIENT_DATA
```

when the relevant behaviour might exist but available telemetry cannot support reliable analysis.

Example:

A critical-path detector may be unable to operate reliably if:

```text
essential timing information is invalid
```

or:

```text
large parts of the execution hierarchy are missing.
```

---

## 12.11 Detector Failure

A detector returns:

```text
FAILED
```

when an internal error prevents completion.

Examples include:

* unexpected algorithm failure;
* unsupported internal state;
* implementation bug.

A malformed trace SHOULD ideally produce:

```text
SKIPPED_INSUFFICIENT_DATA
```

rather than an exception where the condition can be recognized safely.

---

## 12.12 Finding Structure

Each detector produces zero or more structured findings.

Conceptually:

```text
Finding {
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

The storage representation was defined in Section 11.

---

## 12.13 Evidence Model

Evidence SHALL represent measurable or directly observable facts.

Examples:

```text
span count
duration
normalized operation
timestamps
service identity
error status
parent-child relationship
execution overlap
```

A finding should contain enough evidence that the developer can understand why it exists.

---

## 12.14 Analysis Ordering

Detectors MAY depend on shared derived structures but SHOULD avoid depending directly on findings from unrelated detectors.

Preferred:

```text
CriticalPath calculation
        ↓
LatencyContributorDetector
```

because critical path is a reusable analysis primitive.

Less desirable:

```text
LatencyContributorDetector
        ↓
Finding
        ↓
SomeOtherDetector parses that finding
```

Detectors should consume structured analysis data rather than each other's presentation output.

---

## 12.15 Shared Derived Structures

TraceForge v0.1 SHOULD support several reusable analysis structures.

These include:

```text
parent-child graph
temporal interval representation
critical path
exclusive-time estimates
normalized-operation groups
error observation graph
service transition graph
```

These are not necessarily persisted.

They may be constructed during each AnalysisRun.

---

## 12.16 Parent-Child Graph

The trace hierarchy forms a directed graph:

```text
parent span → child span
```

Under healthy telemetry, the graph should normally resemble a tree.

However, analysis SHALL tolerate:

```text
multiple roots
missing parents
orphaned subtrees
```

The implementation SHOULD protect against impossible cycles even though valid OpenTelemetry data should not contain them.

If a cycle is observed:

```text
STRUCTURAL ISSUE
```

should be recorded and affected graph analysis may be skipped.

---

## 12.17 Temporal Interval Representation

Each valid span can be represented as:

```text
[start_ns, end_ns)
```

The half-open interval convention is preferred.

This simplifies overlap calculations.

Two spans overlap when approximately:

```text
max(startA, startB) < min(endA, endB)
```

subject to clock-skew tolerance rules.

---

## 12.18 Exclusive Time

A span's exclusive time estimates how much of its duration is not covered by child execution.

Naively:

```text
exclusive =
parent duration
-
sum(child durations)
```

is incorrect when children overlap.

Instead:

```text
exclusive =
parent duration
-
union_duration(child intervals clipped to parent)
```

Example:

```text
Parent: 1000 ms

Child A:
100–700 ms

Child B:
400–900 ms
```

Their accumulated duration is:

```text
1200 ms
```

but the union is:

```text
800 ms
```

so parent exclusive time is approximately:

```text
200 ms
```

---

## 12.19 Interval Union Algorithm

For child intervals:

```text
I1...In
```

TraceForge can calculate union coverage by:

```text
1. clip intervals to parent bounds
2. sort by start
3. merge overlapping intervals
4. sum merged lengths
```

Complexity:

```text
O(n log n)
```

per child set.

This is acceptable for intended trace sizes.

---

## 12.20 Critical Path Definition

For TraceForge, the **critical path** is the sequence of observed execution intervals that most directly determines the wall-clock completion time of the distributed request.

It is not:

```text
the sum of all spans
```

and not necessarily:

```text
the deepest parent-child tree path.
```

Concurrency must be considered.

---

## 12.21 v0.1 Critical Path Model

For v0.1, TraceForge SHOULD use a pragmatic span-timeline critical-path model rather than attempting to perfectly reconstruct arbitrary asynchronous causal systems.

The algorithm should answer:

> Which observed execution sequence best explains the trace's end-to-end wall-clock duration?

The initial implementation should prioritize:

```text
HTTP/RPC-style nested traces
```

which match the primary product scope.

---

## 12.22 Critical Path Assumptions

The initial algorithm may assume:

* valid span timestamps are mostly comparable;
* parent-child relationships represent causal nesting reasonably well;
* asynchronous messaging is not the primary v0.1 focus;
* extreme clock skew may reduce confidence.

These assumptions SHALL be documented.

---

## 12.23 Proposed Critical Path Algorithm

For each parent span:

1. identify valid child intervals;
2. sort children by execution time;
3. determine which child or sequence of children covers the latest completion dependency;
4. recursively follow the child execution responsible for extending the parent's observed completion;
5. attribute uncovered intervals to the parent itself.

Conceptually:

```text
request
│
├── A  [0–300]
├── B  [50–900]
│     └── D [100–850]
└── C  [100–500]
```

The dominant downstream branch is:

```text
request
    ↓
B
    ↓
D
```

rather than:

```text
A + B + C + D
```

---

## 12.24 Critical Path Segments

The derived model SHOULD represent intervals rather than only span IDs.

Conceptually:

```text
CriticalPathSegment {
    span_id
    start_ns
    end_ns
    contribution_ns
}
```

This is important because a parent span may contribute exclusive work before or after child execution.

---

## 12.25 Critical Path Validation

The calculated critical-path contribution SHALL NOT exceed trace wall-clock duration beyond defined timing tolerance.

If:

```text
critical_path_duration >> trace_duration
```

the result is invalid and should not generate strong latency findings.

---

## 12.26 Clock Skew Tolerance

A configurable timing tolerance MAY be introduced.

For example:

```text
CLOCK_SKEW_TOLERANCE_NS
```

Small parent-child timing violations within tolerance may be treated conservatively.

Larger inconsistencies may cause:

```text
TIMING_INCONSISTENCY
```

and reduced confidence.

The exact default will be determined experimentally.

---

## 12.27 Critical Path Confidence

## 12.27.1 Implemented v0.1 Wall-Clock Attribution Path

TraceForge v0.1 implements a deterministic wall-clock critical-path
approximation. It attributes every instant in the single valid root span to
either that parent span's exclusive execution or one active direct child.

For overlapping sibling intervals, the active child with the latest effective
end time is selected; equal end times use the stable span ID ordering. The
selected child is then evaluated recursively. This can switch attribution
between concurrent sibling branches as their observed intervals change.

This is an attribution rule, not proof of a causal dependency between sibling
operations. Parent/child links are observed telemetry structure; they are used
as a pragmatic nesting model, while causal relationships in arbitrary
asynchronous systems may be unavailable.

Intervals are half-open and child intervals are clipped only in the derived
calculation. The result is unavailable for incomplete traces, invalid timing,
missing parents, root ambiguity, cycles, or children that do not overlap their
parent. Available results have ordered, non-overlapping segments whose
contributions exactly cover the root interval.

Critical-path confidence may be reduced by:

```text
missing parents
multiple roots
invalid timestamps
significant clock skew
large orphaned subtrees
```

The algorithm may still produce a useful estimate, but findings depending on it should inherit appropriate uncertainty.

---

## 12.28 Latency Contributor Detector

The `LatencyContributorDetector` identifies operations that materially contribute to request wall-clock duration.

It consumes:

```text
CriticalPath
exclusive-time information
trace duration
```

---

## 12.29 Latency Contribution

For a span, TraceForge should prefer:

```text
critical_path_contribution
```

over:

```text
raw span duration
```

because a long parent may mostly represent time spent waiting on children.

Example:

```text
orders-service span:
2500 ms

payment child:
2200 ms

orders-service exclusive:
200 ms
```

The primary latency finding should normally emphasize:

```text
payment
```

rather than the enclosing `orders-service` span.

---

## 12.30 Latency Thresholds

A finding should not be generated for every span on the critical path.

A configurable threshold should determine significance.

For example, a span may qualify when:

```text
contribution >= absolute_threshold
```

and/or:

```text
contribution / trace_duration >= relative_threshold
```

Illustrative values:

```text
absolute >= 100 ms
relative >= 25%
```

These values are NOT yet final.

They should be validated using demo traces.

---

## 12.31 Latency Finding Example

```text
Major latency contributor

payment-service / POST /charge

Critical-path contribution:
2.31 s

Trace duration:
2.81 s

Contribution:
82.2%
```

Evidence references the relevant span and derived critical-path segment.

---

## 12.32 Repeated Database Operation Detector

The `RepeatedDatabaseOperationDetector` identifies multiple structurally equivalent database operations within one trace.

Its primary purpose is to surface patterns such as:

```text
repeated per-item database access
redundant query execution
possible N+1 behaviour
```

---

# 12.33 Detector Input

The detector considers spans classified as:

```text
operation_type = DATABASE
```

with a usable normalized operation.

The detector groups by a key resembling:

```text
service
+
database system
+
normalized operation
```

Potential future dimensions may include:

```text
database namespace
peer target
```

---

## 12.34 SQL Normalization

The normalization process SHOULD attempt to remove parameter-value differences while preserving query structure.

Example:

```sql
SELECT name FROM product WHERE id = 18
SELECT name FROM product WHERE id = 21
```

normalize to conceptually:

```sql
SELECT name FROM product WHERE id = ?
```

The implementation SHOULD NOT initially attempt to build a full SQL optimizer or semantic query planner.

---

## 12.35 SQL Normalization Strategy

Preferred hierarchy:

```text
1. use structured semantic attributes if available

2. use database statement/query summary if instrumentation provides one

3. normalize raw statement conservatively

4. if normalization reliability is low:
   do not group aggressively
```

False-positive grouping is worse than failing to detect a pattern.

---

## 12.36 SQL Literal Normalization

A basic normalization layer may replace:

```text
numeric literals
quoted string literals
UUID-like values
```

with placeholders.

Example:

```sql
SELECT *
FROM users
WHERE id = '25cb8d3c-...'
```

becomes:

```sql
SELECT *
FROM users
WHERE id = ?
```

However, normalization must avoid changing structural SQL identifiers.

---

## 12.37 SQL Parsing vs Regex

A pure-regex normalizer is simple but fragile.

A full SQL parser provides better structure but adds dependency and dialect complexity.

The v0.1 implementation may begin with a conservative normalizer while documenting limitations.

A parser SHOULD be introduced if benchmark/demo cases show that reliable grouping requires it.

This decision may become an ADR.

---

## 12.38 Repetition Threshold

Two equivalent operations are technically repeated, but a finding for every pair would produce noise.

The detector therefore requires a configurable minimum count.

Initial default threshold:

```text
count >= 5
```

The final value will be validated against demo scenarios.

---

## 12.39 Sequential Repetition

Sequential repeated operations are often more diagnostically interesting than concurrent batch work.

The detector SHOULD therefore calculate:

```text
total count
sequential count
overlap characteristics
combined duration
```

---

## 12.40 Sequential Classification

Two operations can be considered sequential when their execution intervals do not materially overlap.

For example:

```text
Q1 [0–50]
Q2 [55–100]
Q3 [105–160]
```

are sequential.

Whereas:

```text
Q1 [0–100]
Q2 [10–110]
Q3 [20–120]
```

are predominantly concurrent.

---

# 12.41 Repeated Database Finding

Example:

```text
Repeated database operation

34 structurally equivalent operations observed.

Service:
orders-service

Sequential:
31 / 34

Combined span duration:
2.07 s

Trace duration:
2.81 s
```

Interpretation:

```text
This pattern may indicate redundant database access
or an N+1 query pattern.
```

---

## 12.42 Repeated HTTP / RPC Detector

The same grouping model can later support:

```text
RepeatedDownstreamOperationDetector
```

Possible grouping key:

```text
source service
+
target service
+
HTTP/RPC method
+
normalized route/operation
```

Example:

```text
GET /products/12
GET /products/17
GET /products/31
```

may normalize to:

```text
GET /products/{id}
```

---

## 12.43 Route Normalization

TraceForge SHOULD prefer instrumented route templates where available.

For example:

```text
http.route = /products/{id}
```

is preferable to trying to infer a template from:

```text
/products/142
```

Heuristic path normalization should be used only when reliable semantic attributes are unavailable.

---

## 12.44 Retry Detection

Retry detection is more difficult than general repetition.

Repeated equivalent calls are not necessarily retries.

A future or v0.1-target retry classifier may consider:

```text
same source
same target
same normalized operation
close temporal proximity
preceding failure
similar request attributes
retry semantic attributes
```

Without sufficient evidence, the system SHALL report:

```text
Repeated downstream operation
```

rather than:

```text
Retry storm
```

---

## 12.45 Error Observation Normalization

Error analysis requires a normalized representation of observed failures.

Potential evidence includes:

```text
span status = ERROR
exception event
HTTP 5xx
RPC failure status
database error metadata
```

Normalization produces:

```text
ErrorObservation {
    span_id
    timestamp?
    error_class
    source
    details
}
```

---

## 12.46 Error Origin Detector

The `ErrorOriginDetector` attempts to identify the earliest relevant failure in a causal execution chain.

It does NOT claim to identify the ultimate source-code root cause.

Its output is approximately:

> Which observed error appears to precede and explain subsequent propagated failures?

---

## 12.47 Error Candidate Selection

The detector identifies spans containing normalized error observations.

For each candidate, it considers:

```text
trace hierarchy
error timing
ancestor/descendant relationships
later errors
```

---

## 12.48 Basic Error Propagation Model

Example:

```text
gateway ERROR
└── orders ERROR
    └── payment ERROR
        └── DB ERROR
```

If the DB error occurs first and ancestor errors occur afterward, the DB span becomes a strong origin candidate.

---

## 12.49 Error Origin Scoring

Rather than using arbitrary machine-learning scoring, v0.1 SHOULD use deterministic rules.

Evidence increasing confidence may include:

```text
candidate is deepest relevant failing descendant

candidate error occurs before ancestor errors

ancestors fail shortly after candidate

ancestor errors are generic propagated statuses

candidate contains concrete exception event
```

Evidence reducing confidence may include:

```text
multiple independent failing branches

missing parent relationships

timestamps inconsistent

errors appear simultaneously

upstream error occurs first
```

---

## 12.50 Multiple Error Origins

A trace may contain independent failures.

Example:

```text
request
├── inventory ERROR
└── payment ERROR
```

TraceForge SHALL NOT force these into a single artificial propagation chain.

The detector MAY produce:

```text
multiple candidate originating failures
```

or multiple findings.

---

## 12.51 Error Propagation Chain

A derived chain may look like:

```text
DB timeout
    ↓
payment-service ERROR
    ↓
orders-service ERROR
    ↓
gateway HTTP 500
```

Evidence should preserve the span IDs participating in the chain.

---

## 12.52 Error Finding Example

```text
Likely originating failure

Database operation in payment-service

Observed first error:
22:14:31.482

Subsequent related failures:
payment-service
orders-service
gateway

Confidence:
HIGH
```

Interpretation:

```text
This is the earliest observed failure in the
associated propagation chain.
```

Not:

```text
The database is definitely the root cause.
```

---

## 12.53 Severity Model

Severity measures potential impact.

A preliminary model is:

```text
INFO
LOW
MEDIUM
HIGH
CRITICAL
```

For v0.1, `CRITICAL` may be unnecessary.

A simpler model may be preferable:

```text
INFO
LOW
MEDIUM
HIGH
```

The final enum should remain small.

---

## 12.54 Severity Inputs

Severity MAY consider:

```text
did the trace fail?
percentage of trace latency affected
number of repeated operations
duration impact
breadth of propagated failure
```

Severity must remain detector-specific.

There should not be one opaque universal formula.

---

## 12.55 Confidence Model

Confidence expresses strength of evidence.

The recommended v0.1 representation is:

```text
LOW
MEDIUM
HIGH
```

rather than a numeric percentage.

A value such as:

```text
83% confidence
```

would imply a calibrated probabilistic interpretation that TraceForge cannot initially justify.

---

## 12.56 Confidence Rules

Each detector SHALL document deterministic rules for confidence.

Example for repeated database operations:

```text
HIGH
- operation came from `db.query.summary`
- trace is COMPLETE
```

```text
MEDIUM
- raw `db.query.text` normalization was used and trace is COMPLETE
- or `db.query.summary` was used and trace is INCOMPLETE
```

```text
LOW
- raw `db.query.text` normalization was used
- trace is INCOMPLETE
```

---

## 12.57 Finding Threshold Philosophy

TraceForge should prefer:

```text
fewer useful findings
```

over:

```text
large quantities of technically true observations.
```

The system should not report every:

* slow span;
* repeated pair;
* HTTP error;
* database call.

A finding should represent behaviour sufficiently significant to justify developer attention.

---

## 12.58 Detector Configuration

Detector thresholds SHOULD be configurable.

Conceptually:

```text
analysis:
  repeated_database:
    min_count: 5

  latency_contributor:
    min_duration_ms: 100
    min_trace_fraction: 0.25
```

The exact configuration format is deferred.

Defaults must provide useful behaviour without configuration.

---

## 12.59 Configuration Versioning

Because configuration affects findings, each AnalysisRun SHOULD have enough metadata to identify the configuration used.

This may be represented through:

```text
detector_set_version
```

and potentially a configuration hash.

Exact persistence may be simplified in v0.1.

---

## 12.60 Detector Versioning

Each detector SHALL expose a version.

Example:

```text
repeated_database_operation
version 1
```

When algorithm semantics change meaningfully:

```text
version 2
```

should be used.

This allows findings from different algorithm versions to be distinguished.

---

## 12.61 Re-analysis After Detector Changes

TraceForge MAY eventually support re-analyzing historical traces after detector updates.

Example:

```text
stored trace revision 7

Detector v1
    ↓
historical Finding A

Detector v2
    ↓
new AnalysisRun
```

This is not required for initial UI functionality but should remain architecturally possible.

---

## 12.62 Analysis Run Atomicity

Detector results may be written during execution, but findings SHOULD become current only after the run is published successfully.

The preferred product-level behaviour is:

```text
old current analysis
        ↓
new run executes invisibly
        ↓
new run completes
        ↓
atomic switch to new current analysis
```

The UI should not observe half-updated findings from multiple runs.

---

## 12.63 Partial Analysis

A trace may produce:

```text
CriticalPathDetector      SUCCESS
LatencyDetector           SUCCESS
RepeatedDBDetector        FAILED
ErrorOriginDetector       SUCCESS
```

The overall run becomes:

```text
PARTIAL
```

Successful findings remain usable.

The UI should indicate that analysis was incomplete.

---

## 12.64 Analysis on Incomplete Traces

Incomplete traces are not automatically excluded from analysis.

Each detector declares requirements.

Example:

```text
RepeatedDatabaseOperationDetector
```

may still be valid if all relevant database spans are present.

Meanwhile:

```text
CriticalPathDetector
```

may be unreliable if a major parent subtree is missing.

---

## 12.65 Detector Requirement Metadata

Each detector SHOULD conceptually define requirements such as:

```text
requires_valid_timestamps
requires_single_root
requires_complete_parent_relationships
required_operation_types
minimum_span_count
```

This metadata may be encoded in code rather than a declarative configuration.

The requirement is conceptual clarity.

---

## 12.66 Structural Issue Effects

Known structural issues may influence detector eligibility.

Example mapping:

```text
MISSING_PARENT
    → reduce/disable critical path confidence

INVALID_TIMESTAMPS
    → disable temporal analysis for affected spans

MULTIPLE_ROOTS
    → critical path may require multi-root handling

DUPLICATE_SPAN_CONFLICT
    → reduce confidence where affected spans matter
```

---

## 12.67 Analysis Guardrails

The worker SHALL enforce bounded resource usage.

Potential guardrails include:

```text
maximum spans per trace
maximum events per trace
maximum normalized operation length
maximum detector execution duration
```

These protect the worker from pathological telemetry.

---

## 12.68 Detector Timeout

Individual detector timeout support SHOULD be possible.

A detector exceeding its allowed runtime may return:

```text
FAILED
reason = TIMEOUT
```

The rest of the analysis can continue.

The exact timeout mechanism depends on Python execution architecture and may not be implemented in the earliest milestone.

---

## 12.69 Analysis Complexity Targets

Core detectors SHOULD target approximately:

```text
O(n)
```

or:

```text
O(n log n)
```

where `n` is number of spans.

Expected examples:

```text
build parent map          O(n)
group operations          O(n)
sort temporal intervals   O(n log n)
error traversal           O(n)
```

---

## 12.70 Avoiding Pairwise Comparisons

Naive repeated-operation detection might compare every span with every other span:

```text
O(n²)
```

Instead:

```text
normalized_key → group
```

allows grouping approximately in:

```text
O(n)
```

after normalization.

---

## 12.71 Analysis Caching Within One Run

Derived calculations may be cached inside `AnalysisContext`.

Examples:

```text
critical path
exclusive time
normalized grouping
error observations
```

The cache is scoped to one immutable trace revision.

No distributed cache is required.

---

## 12.72 No Cross-Trace Baseline in Core v0.1

Core detectors should operate on:

```text
one trace
```

where possible.

This avoids requiring historical statistical models for initial diagnosis.

A later analysis layer may introduce:

```text
operation baseline
service baseline
historical distribution
```

without replacing deterministic per-trace analysis.

---

## 12.73 Future Historical Analysis

Future detectors may answer:

```text
Is this request unusual compared with previous
GET /orders traces?
```

Potential metrics include:

```text
duration percentile
child span count
dependency changes
repeated-operation count
```

This is deferred.

---

## 12.74 Finding Deduplication

Within one AnalysisRun, detectors SHOULD avoid generating redundant findings describing the exact same behaviour.

Example:

34 repeated queries should normally produce:

```text
one finding referencing 34 spans
```

not:

```text
34 separate findings.
```

---

## 12.75 Cross-Detector Finding Relationships

v0.1 does not require sophisticated finding correlation.

However, findings MAY reference related entities that naturally overlap.

Example:

```text
Repeated DB operation
```

may involve the same spans as:

```text
Major latency contributor.
```

Both findings remain separately valid because they describe different behaviour.

---

## 12.76 Future Finding Correlation

Future versions may create a higher-level diagnostic grouping:

```text
Repeated database access
        ↓
caused major latency contribution
```

This should not be implemented until individual detectors are reliable.

---

## 12.77 Human-Readable Summary Generation

Each detector MAY generate deterministic presentation text from structured data.

Example:

```text
34 structurally equivalent database operations
were observed in orders-service.
```

This text should be generated from the same structured evidence stored with the finding.

---

## 12.78 Optional LLM Explanation Boundary

A future language-model integration may consume:

```text
Finding
Evidence
Trace summary
```

and produce:

```text
natural-language explanation
```

The model SHALL NOT become part of detector execution.

Core flow remains:

```text
Trace
    ↓
Detector
    ↓
Finding
```

not:

```text
Trace
    ↓
LLM
    ↓
Finding
```

---

## 12.79 Initial Detector Set

The mandatory initial detector set is:

```text
CriticalPath analysis primitive

LatencyContributorDetector

RepeatedDatabaseOperationDetector

ErrorOriginDetector
```

Additionally:

```text
RepeatedDownstreamOperationDetector
```

is a v0.1 target.

---

## 12.80 Critical Path as Primitive, Not Finding Detector

The critical path is primarily a shared derived structure.

It does not necessarily need to create a user-visible finding by itself.

Instead:

```text
CriticalPathCalculator
        ↓
LatencyContributorDetector
```

is the preferred relationship.

This distinction is important.

Not every analysis algorithm must directly emit findings.

---

## 12.81 Proposed Analysis Package Structure

A possible backend layout is:

```text
analysis/
│
├── context.py
├── orchestrator.py
├── result.py
│
├── primitives/
│   ├── intervals.py
│   ├── critical_path.py
│   ├── exclusive_time.py
│   └── error_graph.py
│
├── normalization/
│   ├── sql.py
│   ├── http.py
│   └── operations.py
│
└── detectors/
    ├── base.py
    ├── latency_contributor.py
    ├── repeated_database.py
    ├── error_origin.py
    └── repeated_downstream.py
```

This is illustrative rather than mandatory.

---

## 12.82 Unit Testing Strategy

Every detector SHALL have focused unit tests using synthetic domain traces.

Tests SHOULD avoid requiring:

```text
FastAPI
PostgreSQL
OTLP Collector
```

Example:

```text
Trace(
    spans=[
        ...
    ]
)
```

passed directly to:

```text
RepeatedDatabaseOperationDetector
```

---

## 12.83 Detector Test Categories

Each detector SHOULD include:

```text
positive detection
negative case
threshold boundary
incomplete telemetry
invalid timing
concurrent operations
large input
```

where relevant.

---

## 12.84 Critical Path Test Cases

Minimum scenarios include:

#### Sequential children

```text
A → B → C
```

Expected path:

```text
A/B/C execution chain
```

#### Concurrent children

```text
A
├── B 500ms
└── C 900ms
```

Expected downstream contributor:

```text
C
```

#### Overlapping children

Partial overlap must not double-count time.

#### Parent exclusive work

Parent time outside child coverage must remain attributable.

#### Missing parent

Algorithm must fail or degrade predictably.

---

## 12.85 Repeated Database Tests

Required examples:

```text
same SQL + different numeric IDs
```

should group.

```text
different table
```

should not group.

```text
same operation across different services
```

should normally form separate groups.

```text
4 repetitions below threshold
```

should not produce a finding if threshold is 5.

---

## 12.86 Error Origin Tests

Required scenarios:

```text
single downstream error propagated upward
```

```text
two independent error branches
```

```text
upstream error occurs before downstream error
```

```text
exception event with ancestor HTTP 500
```

```text
missing parent relationship
```

The detector must avoid inventing a single origin where evidence is ambiguous.

---

## 12.87 Golden Trace Fixtures

TraceForge SHOULD maintain a set of deterministic trace fixtures.

Examples:

```text
normal_trace.json

slow_dependency.json

repeated_database.json

concurrent_children.json

propagated_error.json

multiple_error_origins.json

incomplete_trace.json

clock_skew_trace.json
```

These can validate algorithm behaviour independently from the demo application.

---

## 12.88 Demo Application Validation

The demo application should produce equivalent real OpenTelemetry traces for important patterns.

This creates two test layers:

```text
synthetic domain fixtures
```

for precise algorithm testing;

and:

```text
real instrumented demo application
```

for end-to-end validation.

---

## 12.89 Benchmarking

The analysis package SHOULD include repeatable benchmarks.

Representative trace sizes:

```text
10 spans
100 spans
1,000 spans
10,000 spans
```

where practical.

Benchmarks should measure:

```text
context construction
critical path
repeated operation grouping
error analysis
full analysis run
```

---

## 12.90 Analysis Performance Acceptance

For normal development traces containing hundreds of spans, analysis should comfortably satisfy the previously defined:

```text
p95 ≤ 2 seconds
```

target.

Ideally, most individual trace analyses should complete far below this limit.

---

## 12.91 Detector Logging

Detector failures SHOULD log:

```text
trace ID
trace revision
detector ID
detector version
failure category
```

Logs SHOULD NOT unnecessarily include full sensitive span attributes.

---

## 12.92 Detector Metrics

TraceForge SHOULD eventually expose:

```text
detector runs
detector findings
detector skips
detector failures
detector duration
```

per detector type.

This makes noisy, slow, or unreliable detectors visible.

---

## 12.93 Finding Quality Evaluation

Detector quality cannot be judged only by unit-test correctness.

The demo environment should be used to evaluate:

```text
false positives
false negatives
finding usefulness
finding noise
confidence appropriateness
```

Threshold tuning should be driven by observed behaviour.

---

## 12.94 No Hidden Global Score

TraceForge SHALL NOT initially assign one opaque:

```text
trace health score = 73
```

Such scores conceal the evidence and combine unrelated concepts.

The product should show individual meaningful findings.

---

## 12.95 No Automatic Remediation

Detectors SHALL NOT modify observed applications.

TraceForge reports:

```text
what happened
why it may matter
where to investigate
```

It does not:

```text
rewrite SQL
change application concurrency
restart services
modify deployment configuration
```

---

## 12.96 Analysis Security

Analysis code SHALL treat telemetry values as untrusted input.

Normalization logic must handle:

```text
extremely long strings
unexpected Unicode
malformed SQL
strange route values
large attribute sets
```

without unsafe execution.

Telemetry text SHALL never be executed as code or SQL against TraceForge's own database.

---

## 12.97 Resolved Analysis Decisions

The initial design makes the following decisions:

```text
AN-001
Core analysis is deterministic.

AN-002
Detectors consume domain objects, not OTLP or ORM models.

AN-003
A shared immutable AnalysisContext is built per trace revision.

AN-004
Detector results distinguish findings, no findings,
insufficient data, non-applicability, and failure.

AN-005
Critical path is a shared analysis primitive.

AN-006
Latency attribution uses critical-path contribution
rather than raw parent-span duration.

AN-007
Repeated database operations are grouped using
normalized operation structure.

AN-008
Repeated-operation findings require configurable
noise thresholds.

AN-009
Sequential and concurrent repetition are distinguished.

AN-010
Error origin analysis uses structural and temporal
evidence.

AN-011
Multiple independent error origins are permitted.

AN-012
Severity and confidence are separate.

AN-013
Confidence uses LOW / MEDIUM / HIGH in v0.1.

AN-014
Incomplete traces may receive partial analysis.

AN-015
Each detector documents telemetry requirements.

AN-016
Analysis algorithms should generally target O(n)
or O(n log n).

AN-017
Findings remain structured and evidence-backed.

AN-018
LLMs are not part of primary diagnostic analysis.

AN-019
Critical path, latency contribution, repeated DB
operations, and error origin form the mandatory
initial analysis set.
```

---

## 12.98 Open Analysis Questions

### Q-ANALYSIS-001 — Critical path algorithm details

The exact recursive/interval algorithm must be finalized and proven against test fixtures before implementation is considered complete.

---

### Q-ANALYSIS-002 — Critical-path handling of asynchronous spans

How should spans that violate normal parent-child nesting be treated?

v0.1 may intentionally support only conservative interpretation.

---

### Q-ANALYSIS-003 — SQL normalization implementation

Should v0.1 use:

```text
conservative custom normalization
```

or a:

```text
SQL parser library
```

?

This should be decided through prototype evaluation.

---

### Q-ANALYSIS-004 — Initial repetition threshold

What default repeated-operation count produces useful findings without noise?

Candidate:

```text
5
```

but this requires validation.

---

### Q-ANALYSIS-005 — Latency thresholds

What combination of:

```text
absolute duration
relative trace contribution
```

should trigger a latency finding?

---

### Q-ANALYSIS-006 — Confidence propagation

If critical-path confidence is MEDIUM, should dependent latency findings be capped at MEDIUM?

Current preference:

```text
yes
```

---

### Q-ANALYSIS-007 — Detector set version

Should the full detector-set configuration use:

```text
semantic version
hash
```

or both?

---

## 12.99 Analysis Engine Acceptance Criteria

Before the analysis layer is considered implementation-ready, it must be possible to define expected output for the following traces.

```text
healthy sequential request

healthy concurrent request

single slow downstream dependency

slow parent caused mostly by slow child

repeated parameterized SQL queries

repeated queries executed concurrently

repeated HTTP operations

single downstream error propagated upward

multiple independent errors

missing-parent trace

late-span revised trace

trace with timing inconsistency
```

For every scenario, the expected:

```text
detector eligibility
detector state
findings
evidence
confidence
```

should be predictable.

---

## 12.100 Analysis Principle

The analysis engine should obey one final rule:

> **TraceForge should never claim more than the telemetry can support.**

It may say:

```text
34 repeated queries were observed.
```

It may say:

```text
Those queries contributed substantially to latency.
```

It may say:

```text
This pattern may represent an N+1 query problem.
```

It should not say:

```text
Your repository implementation is definitely wrong.
```

unless the system possesses evidence capable of supporting that conclusion.

The value of TraceForge comes not from sounding certain.

It comes from being **usefully precise about what the telemetry actually shows**.
