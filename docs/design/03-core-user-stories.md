# Core user stories

## 3.1 Purpose

The purpose of the user stories in this section is to describe the behaviour TraceForge must support from the perspective of the developer using the system.

These stories are intentionally written before detailed architecture and implementation decisions are made.

They define what the user should be able to accomplish without prescribing how TraceForge internally implements the capability.

Each user story is assigned one of four priorities:

```
MUST - required for the initial usable version of TraceForge;
SHOULD - strongly desirable, but the first usable version can exist without it;
COULD - valuable extension that may be implemented after the core product is stable;
NOT v0.1 - intentionally excluded from the initial version.
```

The collection of MUST stories defines the minimum product that can reasonably be described as TraceForge rather than merely as a distributed trace viewer.
<hr>

## 3.2 Trace Discovery and Inspection
### US-TRACE-001 - View Recent Traces

**Priority**: MUST

    As a developer, I want to see recently observed distributed traces so that I can locate requests related to the behaviour I am investigating.

The trace list should provide enough information to distinguish relevant requests without requiring the user to open every trace individually.

Relevant information may include:

- starting service;
- operation or route;
- start time;
- total duration;
- number of spans;
- number of participating services;
- final status;
- presence of errors;
- presence of TraceForge findings.

A developer investigating a recently failed request should be able to identify likely candidate traces quickly.

<hr>

### US-TRACE-002 - Filter and Search Traces

**Priority**: MUST

    As a developer, I want to filter traces by relevant execution properties so that I can isolate the requests associated with a particular problem.

Initial filtering should support properties such as:

- service;
- operation or route;
- time range;
- duration;
- success or failure status;
- trace ID;
- presence of diagnostic findings.

For example, a developer should be able to ask:

    Show failed traces involving payment-service during the last 15 minutes.
or:

    Show GET /orders requests slower than 1 second.

The purpose of filtering is not to reproduce a general-purpose telemetry query language in v0.1.

It is to provide the common investigation paths required by the primary target user.
<hr>

### US-TRACE-003 - Inspect Complete Trace Execution

**Priority**: MUST

    As a developer, I want to inspect the complete execution of a distributed request so that I can understand how work moved through the application.

TraceForge should reconstruct the logical relationship between spans and present their execution hierarchy.

For example:
```text
    GET /checkout
    │
    ├── auth-service
    │   └── Redis GET session
    │
    └── checkout-service
        ├── inventory-service
        │   └── PostgreSQL SELECT
        │
        └── payment-service
            └── POST payment-provider
```
The user should be able to determine:

- which services participated;
- which operations were nested;
- which operations executed sequentially;
- which operations overlapped;
- where errors occurred;
- how long each operation took.
<hr>

### US-TRACE-004 - Inspect Individual Span Details

**Priority**: MUST

    As a developer, I want to inspect the raw telemetry associated with an individual span so that I can verify TraceForge's interpretation of the request.

Span details should expose relevant OpenTelemetry information including, where available:

- trace ID;
- span ID;
- parent span ID;
- service;
- span name;
- span kind;
- start and end timestamps;
- duration;
- status;
- attributes;
- events;
- exception information;
- resource information;
- instrumentation scope.

TraceForge must not hide the original evidence behind simplified diagnostic messages.
<hr>

## 3.3 Latency Analysis
### US-LATENCY-001 - Identify Major Latency Contributors

**Priority**: MUST

    As a developer, I want TraceForge to identify which operations contributed most significantly to request latency so that I know where to begin a performance investigation.

A long-running span should not automatically be considered the cause of latency.

TraceForge should distinguish where possible between:

- active work;
- waiting on child operations;
- overlapping work;
- sequential dependencies.

For example:

    Trace duration: 2.80 s
    orders-service span:       2.65 s
    payment-service call:      2.31 s
    local DB operation:          84 ms
    serialization:               21 ms

TraceForge should avoid presenting orders-service as the primary latency source merely because its parent span encompasses most of the request.

Instead, the analysis should identify the downstream payment operation as the meaningful contributor.
<hr>

### US-LATENCY-002 - Identify the Effective Critical Path

**Priority**: MUST

    As a developer, I want to know which sequence of operations determined the total request duration so that I can distinguish critical work from operations that happened concurrently.

Consider:
```text
request
│
├── service-A      500 ms
├── service-B     1200 ms
└── service-C      700 ms
```
If the three calls execute concurrently, their durations should not be interpreted as contributing:

500 + 1200 + 700 = 2400 ms

to total request latency.

The request may instead complete in approximately:

`1200 ms`

plus surrounding work.

TraceForge should therefore model temporal relationships rather than simply summing span durations.
<hr>

### US-LATENCY-003 - Surface Suspicious Sequential Work

**Priority**: SHOULD

    As a developer, I want TraceForge to identify operations that execute sequentially when their telemetry suggests potentially independent repeated work so that I can investigate avoidable serialization.

TraceForge must not claim that operations could definitely execute concurrently without application-level evidence.

Instead, it may report an observation such as:
```
17 similar downstream requests executed sequentially.

Combined elapsed time: 1.43 s.

Consider investigating whether this access pattern is expected.
```

The finding should describe observable behaviour rather than infer implementation details that telemetry cannot prove.
<hr>

## 3.4 Repeated Operation Detection
### US-REPEAT-001 - Detect Repeated Database Operations

**Priority**: MUST

    As a developer, I want TraceForge to identify unusually repeated database operations within a request so that I can investigate possible N+1 or redundant-query behaviour.

TraceForge should group database spans according to a normalized representation rather than requiring the raw statement text to be identical.

For example:
```text
SELECT name FROM product WHERE id = 18;
SELECT name FROM product WHERE id = 21;
SELECT name FROM product WHERE id = 27;
```

may represent the same structural operation despite containing different parameter values.

A possible finding could be:

```
Repeated database operation

34 structurally equivalent SELECT operations
were observed in orders-service.

Combined span duration: 2.07 s
```
TraceForge should describe this as a potential repeated-query pattern rather than automatically declaring that the application's source code contains an N+1 bug.
<hr>


### US-REPEAT-002 - Detect Repeated Downstream Requests

**Priority**: SHOULD

    As a developer, I want TraceForge to identify repeated calls to the same downstream operation so that I can investigate redundant network activity or inefficient request patterns.

For example:
```text
orders-service
├── GET product-service/products/14
├── GET product-service/products/21
├── GET product-service/products/27
├── GET product-service/products/32
└── ...
```

TraceForge should be capable of recognizing the structural similarity between these operations.
<hr>

### US-REPEAT-003 - Distinguish Repetition from Retries

**Priority**: SHOULD

    As a developer, I want TraceForge to distinguish likely retries from general repeated operations where sufficient telemetry exists so that different behaviours are not reported as the same problem.

Possible retry evidence may include:

- repeated requests to the same normalized destination;
- close temporal proximity;
- preceding failures;
- similar request metadata;
- known retry-related semantic attributes.

When evidence is insufficient, TraceForge should classify the behaviour conservatively as repeated execution rather than asserting that a retry occurred.
<hr>

## 3.5 Error Analysis
### US-ERROR-001 - Identify Error Origin

**Priority**: MUST

    As a developer, I want TraceForge to identify the earliest relevant failure within a distributed request so that I can distinguish the originating error from propagated failures.

For example:
```text
gateway               ERROR
└── orders-service    ERROR
└── payment       ERROR
└── database  ERROR
```
If the database span contains the first observed failure and subsequent services merely propagate it, TraceForge should direct attention toward the database operation.

A finding might state:
```text
Likely originating failure

payment-database operation reported an error before
subsequent failures in payment-service, orders-service,
and gateway.

4 downstream/parent spans subsequently reported errors.
```
This must remain evidence-based.

TraceForge cannot guarantee that the earliest recorded error is always the true source-code root cause.
<hr>

### US-ERROR-002 - Visualize Error Propagation

Priority: MUST

As a developer, I want to see how an error propagated through the request so that I can understand its effect on upstream services.

The trace view should make it possible to distinguish:

- originating error candidates;
- subsequently failed operations;
- unaffected branches;
- recovered failures where execution continued successfully.
<hr>

### US-ERROR-003 - Inspect Exception Evidence

**Priority**: MUST

    As a developer, I want direct access to exception telemetry associated with a failure so that I can investigate the underlying application error.

Where available, this may include:

- exception type;
- message;
- stack trace;
- exception-related span events;
- service;
- operation;
- timestamp.

Potentially sensitive information must be considered later in the security and privacy design.
<hr>

## 3.6 Service Dependency Understanding
### US-SERVICE-001 - View Observed Service Dependencies

**Priority**: MUST

    As a developer, I want to see which services communicate with one another based on observed telemetry so that I can understand the application's runtime architecture.

TraceForge should derive this graph from observed service interactions rather than requiring the user to manually configure an architecture diagram.

Example:
```mermaid
gateway
    │
    ├── auth-service
    │
    └── orders-service
        │
        ├── inventory-service
        └── payment-service
```
The graph represents observed runtime dependencies, not necessarily every dependency that exists in source code or configuration.
<hr>

### US-SERVICE-002 - Inspect Dependency Behaviour

**Priority**: SHOULD

    As a developer, I want to inspect observed behaviour between two services so that I can understand whether a dependency is associated with latency or failures.

Potential information may include:

- request count;
- observed latency;
- error count;
- operations used;
- recent traces containing the dependency.

This is intended as an investigation aid rather than as a full metrics platform.
<hr>

## 3.7 Diagnostic Findings
### US-FINDING-001 - Receive Automated Diagnostic Findings

**Priority**: MUST

    As a developer, I want TraceForge to automatically identify significant execution behaviour so that I do not have to manually inspect every span in every trace.

Initial finding categories may include:

- major latency contributor;
- repeated database operation;
- repeated downstream operation;
- likely error origin;
- unusual retry-like behaviour;
- incomplete trace;
- abnormal operation relative to comparable traces.

Not all categories are required for the first implementation milestone.

However, automated findings are a defining capability of TraceForge.
<hr>

### US-FINDING-002 - See Evidence for Every Finding

**Priority**: MUST

    As a developer, I want every diagnostic finding to include the evidence that produced it so that I can independently evaluate whether the conclusion is useful.

A finding should reference relevant spans and include measurable evidence where possible.

For example:
```text
Potential repeated-query pattern

Evidence:
- 34 matching database spans
- same service: orders-service
- same normalized operation
- 31 executed sequentially
- combined duration: 2.07 s
- trace duration: 2.81 s
```
The user should be able to navigate directly from the finding to the affected spans.
<hr>

### US-FINDING-003 - Express Diagnostic Uncertainty

**Priority**: MUST

    As a developer, I want TraceForge to distinguish observations from uncertain interpretations so that diagnostic output does not imply more certainty than the telemetry supports.

TraceForge should differentiate between statements such as:

    34 structurally equivalent SQL operations were observed.

and:

    This may indicate an N+1 query pattern.

The first statement is an observed fact.

The second is an interpretation.

The product must preserve that distinction.
<hr>

### US-FINDING-004 - View Traces Without Findings

**Priority**: MUST

    As a developer, I want TraceForge to explicitly indicate when no configured diagnostic pattern was detected so that absence of findings is not confused with failed analysis.

A result such as:
```
No significant findings detected.

should indicate successful analysis.

This must remain distinct from:

Analysis unavailable.
```

or:

    Trace incomplete.
<hr>

## 3.8 Comparison and Historical Context

### US-COMPARE-001 - Compare Similar Requests

**Priority**: SHOULD

    As a developer, I want to compare a suspicious trace against similar successful or typical traces so that I can identify what changed.

For example:

```text
Typical GET /orders:
median duration: 184 ms

Selected trace:
duration: 2.81 s

Difference:
+2.63 s

Primary changed behaviour:
34 product queries instead of typical 1–3.
```

This capability may substantially improve diagnosis but requires enough historical telemetry to establish meaningful comparisons.

It is therefore not required for the smallest viable implementation.
<hr>

### US-COMPARE-002 - Detect Unusual Behaviour Relative to Baseline

**Priority**: COULD

    As a developer, I want TraceForge to identify when an operation behaves unusually compared with previous observations so that problems without fixed thresholds can still be surfaced.

Examples may include:

- unusually high span duration;
- unusually high number of child operations;
- newly observed service dependency;
- unusual error frequency;
- unusual repeated-operation count.

This functionality introduces statistical and baseline-model design questions and should not block the deterministic single-trace analysis required for v0.1.
<hr>

## 3.9 Instrumentation and Onboarding

### US-SETUP-001 - Connect an OpenTelemetry Application

**Priority**: MUST

    As a developer, I want clear instructions for sending OpenTelemetry traces to TraceForge so that I can begin using the system without learning TraceForge-specific instrumentation.

TraceForge should consume standard OpenTelemetry telemetry.

Users should not be required to install a proprietary TraceForge SDK into their application.
<hr>

### US-SETUP-002 - Verify Telemetry Reception

**Priority**: MUST

As a developer, I want to verify that TraceForge is receiving telemetry from my services so that configuration problems can be distinguished from application problems.

The system should provide clear visibility into:

- whether telemetry has been received;
- which services have been observed;
- when each service was last seen;
- whether incoming telemetry is malformed or rejected.
<hr>

### US-SETUP-003 - Run TraceForge Locally

**Priority**: MUST

    As a developer, I want to run TraceForge locally using a documented container-based setup so that evaluating the tool does not require building substantial infrastructure.

The initial deployment experience should aim to be approximately:
```text 
configure application OTLP exporter
        ↓
start TraceForge
        ↓
generate application traffic
        ↓
open TraceForge UI
        ↓
inspect traces
```
Deployment complexity should remain proportional to the needs of the primary target user.
<hr>

## 3.10 Demo and Reproducibility
### US-DEMO-001 - Reproduce Known Failure Patterns

**Priority**: MUST

    As a developer evaluating or developing TraceForge, I want a demonstration application capable of intentionally producing known distributed-system behaviours so that diagnostic functionality can be tested reproducibly.

The demo environment should eventually include controlled scenarios such as:

- Normal request
- Slow downstream dependency
- Repeated database query pattern
- Repeated downstream calls
- Retry-like behaviour
- Propagated service failure
- Database exception
- Concurrent downstream operations

The demo application is not merely a presentation component.

It serves as:

- an integration-test environment;
- a source of predictable telemetry;
- a development fixture for the analysis engine;
- an onboarding example;
- a portfolio demonstration.
<hr>

## 3.11 Optional Explanation Layer
### US-EXPLAIN-001 - Generate Human-Friendly Finding Explanations

**Priority**: COULD

    As a developer, I want complex diagnostic findings summarized in concise natural language so that I can understand them quickly.

Any such explanation mechanism must operate on structured findings and supporting evidence.

The intended flow is:
```text
Telemetry
        ↓
Deterministic analysis
        ↓
Structured finding
        ↓
Optional explanation
```
The explanation layer must not be required to discover the underlying finding.

For example, the deterministic system may produce:
```text
type: repeated_db_operation
count: 34
combined_duration_ms: 2070
trace_duration_ms: 2810
service: orders-service
```
An optional explanation layer may transform this into:
```text
orders-service executed the same logical database
operation 34 times during this request. Together these
operations accounted for approximately 74% of the
request duration.
```
If the explanation layer is unavailable, the underlying finding must remain fully usable.
<hr>

## 3.12 Explicitly Deferred User Stories

_The following stories represent plausible future directions but are intentionally outside the initial product scope._

### US-DEFER-001 - Production Alerting

**Priority**: NOT v0.1

    As an operator, I want TraceForge to notify me automatically when diagnostic conditions are detected.

Initial TraceForge usage is investigation-driven rather than alert-driven.
<hr>

### US-DEFER-002 - Full Log Search

**Priority**: NOT v0.1

    As a developer, I want TraceForge to ingest, index, and search arbitrary application logs.

TraceForge may eventually correlate logs with traces, but becoming a general log-management system is not an initial goal.
<hr>

### US-DEFER-003 - Infrastructure Metrics Monitoring

**Priority**: NOT v0.1

    As an operator, I want dashboards for CPU, memory, disk, network, and infrastructure health.

Such metrics may later provide useful diagnostic context, but infrastructure monitoring is not part of the initial product definition.

### US-DEFER-004 - Multi-Tenant Organizations

**Priority**: NOT v0.1

    As an organization administrator, I want isolated teams, projects, users, permissions, and telemetry environments.

This would introduce significant authentication, authorization, storage-isolation, and operational requirements unrelated to the initial problem.
<hr>

### US-DEFER-005 - Kubernetes-Native Deployment

**Priority**: NOT v0.1

    As a platform engineer, I want to deploy and operate TraceForge as a Kubernetes-native observability service.

Kubernetes support is a potential future capability, but Docker Compose remains the initial deployment target.
<hr>

## 3.13 v0.1 User Story Set

The following user stories define the initial mandatory product boundary:
```text
US-TRACE-001     View recent traces
US-TRACE-002     Filter and search traces
US-TRACE-003     Inspect complete trace execution
US-TRACE-004     Inspect individual span details

US-LATENCY-001   Identify major latency contributors
US-LATENCY-002   Identify the effective critical path

US-REPEAT-001    Detect repeated database operations

US-ERROR-001     Identify error origin
US-ERROR-002     Visualize error propagation
US-ERROR-003     Inspect exception evidence

US-SERVICE-001   View observed service dependencies

US-FINDING-001   Receive automated diagnostic findings
US-FINDING-002   See evidence for every finding
US-FINDING-003   Express diagnostic uncertainty
US-FINDING-004   View traces without findings

US-SETUP-001     Connect an OpenTelemetry application
US-SETUP-002     Verify telemetry reception
US-SETUP-003     Run TraceForge locally

US-DEMO-001      Reproduce known failure patterns
```

These stories represent the minimum intended TraceForge experience.

A system capable of ingesting and visualizing traces but incapable of producing evidence-backed diagnostic findings does not satisfy the v0.1 product definition.

Conversely, v0.1 does not need to implement every possible diagnostic technique.

The initial release succeeds if it can ingest real distributed traces, reconstruct their execution accurately, expose the underlying telemetry, and reliably identify a small number of useful diagnostic patterns.
<hr>

## 3.14 User Story Design Principle

The user stories in this section should be evaluated against one recurring question:

    Does this capability reduce the amount of distributed-system behaviour the developer must reconstruct manually?

Trace visualization, filtering, service graphs, and span inspection remain essential because they provide context and allow findings to be verified.

However, these capabilities support the central objective rather than replace it.

TraceForge should become more valuable as its ability to extract trustworthy meaning from telemetry improves, not simply as the number of dashboards it provides increases.