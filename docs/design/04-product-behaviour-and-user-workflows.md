# Product Behaviour and User Workflows

## 4.1 Purpose

This section defines how TraceForge should behave from the user's perspective.

The objective is to describe the expected interaction between the developer and the system before implementation details such as APIs, databases, queues, or internal services are designed.

The workflows in this section define the expected product experience for common scenarios.

They are not intended to prescribe the internal architecture.
<hr>

## 4.2 Core Product Workflow

The primary TraceForge workflow is:
```
Application produces telemetry
            ↓
TraceForge receives and processes it
            ↓
Developer observes unexpected behaviour
            ↓
Developer locates the relevant trace
            ↓
TraceForge presents execution structure
            ↓
TraceForge presents diagnostic findings
            ↓
Developer inspects supporting evidence
            ↓
Developer investigates the relevant application code
```

TraceForge should minimize unnecessary steps between:

    "Something behaved incorrectly."

and:

    "This specific execution behaviour is worth investigating."

The system should not require the developer to begin every investigation by manually examining raw telemetry.
<hr>

## 4.3 Initial Setup Workflow

A developer should be able to begin using TraceForge without installing a proprietary application SDK.

The intended setup workflow is:
```
Developer has an application
            ↓
Application is instrumented with OpenTelemetry
            ↓
Developer configures OTLP export
            ↓
Developer starts TraceForge
            ↓
Application generates traffic
            ↓
TraceForge receives telemetry
            ↓
Observed services appear in the interface
```
The exact configuration mechanism will depend on the user's application language and OpenTelemetry setup.

TraceForge documentation should provide examples for common environments, but instrumentation remains based on standard OpenTelemetry components.

The user should not need to modify application code specifically for TraceForge beyond what is necessary to produce compatible telemetry.
<hr>

## 4.4 First-Run Experience

When TraceForge is opened for the first time and no telemetry has been received, the interface should clearly communicate that the system is operational but currently has no data.

The user should not encounter an empty dashboard that could be interpreted as a malfunction.

A first-run state may display:
`No telemetry received yet.`

TraceForge is running and waiting for OpenTelemetry traces.

Expected OTLP endpoint:
`http://localhost:<configured-port>`

Next steps:
1. Configure your application's OTLP exporter.
2. Generate application traffic.
3. Return here to verify received services.

The page may additionally expose:

- TraceForge system status;
- telemetry receiver status;
- configured OTLP endpoints;
- links to instrumentation examples;
- last ingestion error, if one exists.

The objective is to distinguish clearly between:

    TraceForge is working but has no telemetry.
and:

    TraceForge is not receiving telemetry because something is misconfigured.
<hr>

## 4.5 Telemetry Arrival Workflow

When telemetry begins arriving, TraceForge should provide visible confirmation.

For example:
```
Telemetry received

Observed services:

gateway             last seen 2s ago
orders-service      last seen 2s ago
payment-service     last seen 3s ago
inventory-service   last seen 3s ago
```
The user should be able to determine immediately that:

- TraceForge is receiving data;
- specific services are being observed;
- traces are being processed.

The system should not require the developer to inspect internal logs merely to confirm successful ingestion.
<hr>

## 4.6 Trace Investigation Workflow

The most important user workflow begins when the developer observes problematic application behaviour.

Example:

    GET /checkout returned HTTP 500

or:

    GET /orders took 2.8 seconds

The developer opens TraceForge and navigates to the trace list.

### 4.6.1 Locate the Relevant Trace

The trace list should display recent requests in a form suitable for rapid scanning.

Example:
```
TIME       OPERATION          SERVICE       DURATION   STATUS   FINDINGS

14:42:16   GET /products      gateway        143 ms    OK       -
14:42:18   GET /checkout      gateway       2.81 s     ERROR    3
14:42:20   POST /login        gateway        212 ms    OK       -
14:42:21   GET /orders        gateway        184 ms    OK       -
```

A developer investigating the failed checkout can immediately identify the likely trace.

When the relevant trace is not obvious, the developer can apply filters.

For example:
```
Service: gateway
Route: GET /checkout
Status: ERROR
Time: last 15 minutes
```

Trace filtering should progressively narrow the investigation rather than require construction of an advanced query.

The trace list orders by most recently received telemetry. Execution-time range
filters are separate: they constrain the trace start timestamp rather than the
receipt timestamp used for list recency and retention.
<hr>

### 4.6.2 Open Trace Overview

Selecting a trace should initially present a high-level summary.

Example:
```text
GET /checkout

Duration:            2.81 s
Status:              ERROR
Services:            4
Spans:               23
Errors:              4
Diagnostic findings: 2
```
The overview should immediately answer:

- Did the request succeed?
- How long did it take?
- Which services participated?
- Were errors observed?
- Did TraceForge detect significant behaviour?

The user should not initially be overwhelmed by every span attribute.
<hr>

### 4.6.3 Present Diagnostic Findings Early

Diagnostic findings should be visible near the top of the trace investigation experience.

For example:
```text
Findings

HIGH
Likely originating failure
payment-service/database reported the first observed error.

MEDIUM
Major latency contributor
payment-service accounted for approximately 78% of the critical-path duration.
```

TraceForge should not force the user to manually inspect the entire waterfall before showing available analysis.

Each finding should be selectable.

Selecting a finding should highlight or navigate to the telemetry that supports it.
<hr>

### 4.6.4 Inspect Execution Waterfall

The developer should be able to inspect the complete request execution using a timeline or waterfall representation.

Example:
```text
gateway              ███████████████████████████  2.81 s

auth-service           ██                           180 ms

checkout-service         ███████████████████████   2.42 s

inventory-service         ███                       310 ms

payment-service              ████████████████████  2.19 s

payment-db                    ██                    190 ms
```

The exact visual representation will be defined later.

The essential product behaviour is that the developer can understand:
- parent-child relationships;
- temporal ordering;
- concurrent execution;
- latency;
- service boundaries;
- errors.
<hr>

### 4.6.5 Inspect Relevant Span

Selecting a span should expose detailed telemetry.

For example:
```text
payment-service
POST /charge

Duration: 2.19 s
Status: ERROR

Span ID:
86f71c...

Parent Span:
checkout-service / checkout

Attributes:
http.request.method = POST
server.address = payment-service
http.response.status_code = 500

Events:
exception

Exception:
DatabaseTimeoutException
```
The user should be able to move from a high-level finding to raw evidence without leaving the investigation context.
<hr>

## 4.7 Slow Request Workflow

Consider a successful request that is unexpectedly slow:

```text
GET /orders
Expected duration: approximately 200 ms
Observed duration: 2.81 s
```
The developer locates and opens the trace.

TraceForge may present:
```text
Finding: Major latency contributor

34 repeated database operations in orders-service
contributed approximately 2.07 seconds to this trace.
```
The trace visualization shows:
```mermaid
orders-service
    │
    ├── SELECT product...    61 ms
    ├── SELECT product...    58 ms
    ├── SELECT product...    63 ms
    ├── SELECT product...    62 ms
    ├── ...
    └── SELECT product...    59 ms
```

The developer selects the finding.

TraceForge highlights the matching spans.

The finding evidence may display:

Repeated database operation
```text
Observed count:        34
Sequential operations: 31
Combined duration:     2.07 s
Trace duration:        2.81 s
Service:               orders-service
```
TraceForge may additionally state:
```text
This pattern may indicate redundant database access
or an N+1 query pattern.
```
The developer then investigates orders-service.

TraceForge has reduced the investigation from:

    Why is this request slow?

to:

    Why does orders-service execute this logical database operation 34 times?

That reduction in problem space represents the intended product value.

<hr>

## 4.8 Error Propagation Workflow

Consider:
```text
Client
    ↓
gateway
    ↓
orders-service
    ↓
payment-service
    ↓
payment database
```
The database operation fails.

The resulting trace contains:
```text
payment database      ERROR
payment-service       ERROR
orders-service        ERROR
gateway               ERROR
```
A conventional trace may visually display four failed spans.

TraceForge should attempt to identify their relationship.

Example finding:
```text
Likely originating failure

The earliest observed error occurred in:

payment-service
Database operation

Subsequent propagated errors:
payment-service
orders-service
gateway
```
The waterfall should visually distinguish the candidate originating error from failures that occurred later.

This distinction should remain conservative.

TraceForge should not claim:

    The database is definitely the root cause.

unless the available telemetry actually supports such certainty.

The preferred wording is:

    Likely originating failure based on observed telemetry.
<hr>

## 4.9 Repeated Downstream Operation Workflow

Consider:
```mermaid
orders-service
│
├── GET product-service/products/12
├── GET product-service/products/19
├── GET product-service/products/32
├── GET product-service/products/45
├── ...
└── GET product-service/products/91
```
TraceForge recognizes that the destination and normalized route are structurally equivalent.

The user may receive:
```text
Repeated downstream operation

18 structurally similar requests were made from
orders-service to product-service.

16 were executed sequentially.

Combined elapsed contribution:
1.32 s
```
TraceForge should avoid asserting that these requests are unnecessary.

The correct product behaviour is to surface the pattern and allow the developer to determine whether the behaviour is intentional.
<hr>

## 4.10 Concurrent Operations Workflow

Consider a request that executes:
```text
inventory-service  600 ms
recommendation     500 ms
pricing-service    700 ms
```
concurrently.

A naive system might report:

    Total downstream work: 1.8 s

Although technically true as accumulated span duration, this is misleading when explaining request latency.

TraceForge should instead identify that these operations overlap.

For example:
```text
Three downstream operations executed concurrently.

Longest critical-path operation:
pricing-service - 700 ms
```

This prevents accumulated span duration from being confused with wall-clock request duration.
<hr>

## 4.11 Successful Request with No Findings

TraceForge must also handle normal requests cleanly.

Example:
```text
GET /products

Duration: 112 ms
Status: OK
Spans: 8

Analysis:
No significant findings detected.
```
This state means:

- analysis completed successfully;
- the trace was sufficiently complete for analysis;
- none of the enabled detectors produced significant findings.

It must remain visually and semantically distinct from:
    
    Analysis pending
    Analysis failed
and:

    Trace incomplete
<hr>

## 4.12 Incomplete Trace Workflow

Distributed traces may be incomplete.

For example, TraceForge may receive:
```text
gateway
    ↓
orders-service
    ↓
missing parent
    ↓
payment-service
```
or a child span may arrive before its parent.

TraceForge should not immediately classify such telemetry as invalid.

The system may temporarily display:

    Trace processing
    Waiting for additional spans.

If the trace remains incomplete after the configured completion policy has been reached, the user should see:

    Trace incomplete

One or more expected parent spans were not observed.

    Analysis may be limited.

Where possible, TraceForge should still display the available telemetry.

Some diagnostic detectors may continue operating if their requirements are satisfied, while others may be disabled for that trace.

The user should be able to distinguish between:

    Finding absent because behaviour was not detected.

and:

    Finding unavailable because required telemetry is missing.
<hr>

## 4.13 Analysis Failure Workflow

The analysis system itself may fail.

For example:
```text
detector throws an internal error;
unsupported telemetry causes processing failure;
analysis worker becomes unavailable.
```
TraceForge must not confuse this with a healthy trace.

The UI should display:
```text
Analysis unavailable

Trace telemetry was received successfully,
but diagnostic analysis could not be completed.
```
Raw trace inspection should remain available wherever possible.

A failure in automated analysis should not make collected telemetry inaccessible.
<hr>

## 4.14 Telemetry Ingestion Failure Workflow

If TraceForge rejects incoming telemetry, the user should receive enough information to diagnose the configuration problem.

Examples include:

- malformed OTLP payload;
- unsupported protocol configuration;
- invalid identifiers;
- schema incompatibility;
- resource exhaustion;
- receiver unavailable.

TraceForge should expose ingestion health information separately from application trace data.

Example:
```
Telemetry ingestion warning

Last rejected batch: 14:52:17
Source: unknown
Reason: malformed span identifier
Rejected spans: 12
```
Detailed internal errors may be available in system logs, but basic diagnosis should be possible from the product interface.
<hr>

## 4.15 Service Discovery Workflow

TraceForge should construct its service inventory dynamically from received telemetry.

The user should not be required to manually register every application service.

When a previously unseen service appears:

    shipping-service

TraceForge should add it to the observed service list.

A service page may show:
```text
shipping-service

First observed:  14:02
Last observed:   14:58
Operations:      8
Dependencies:    3
Recent traces:   124
Recent errors:   2
```
These values represent observed telemetry rather than configured infrastructure state.
<hr>

## 4.16 Service Dependency Workflow

TraceForge should construct a runtime dependency graph from observed spans.

Example:
```mermaid
                 auth-service
                     ▲
                     │
gateway ───────► orders-service ───────► inventory-service
│
└──────────────► payment-service
```
Selecting a dependency should allow the developer to investigate the traffic responsible for the relationship.

For example:
```text
orders-service → payment-service

Observed operations:
POST /charge
POST /refund

Recent traces: 147

Observed errors: 8
```
The service graph should therefore function as an investigation entry point, not merely as a decorative architecture diagram.
<hr>

## 4.17 Finding Navigation Workflow

Every diagnostic finding must provide a path back to its evidence.

The expected interaction is:
```text
Finding
    ↓
Relevant span group highlighted
    ↓
Developer selects span
    ↓
Raw telemetry displayed
```

For findings involving multiple spans, TraceForge should be capable of highlighting all relevant operations.

Example:
```
Finding:
Repeated database operation

[Show 34 related spans]
```

The developer should never need to manually search the trace for the spans TraceForge used to produce its own conclusion.
<hr>

## 4.18 Finding Severity and Confidence

Diagnostic findings may vary in importance and certainty.

These concepts should remain distinct.

For example:

    Severity: HIGH
    Confidence: HIGH

could represent a strongly evidenced failure affecting the request.

Whereas:

    Severity: MEDIUM
    Confidence: LOW

may represent potentially inefficient behaviour supported by weaker evidence.

Severity answers approximately:

    How important is this behaviour if the finding is correct?

Confidence answers:

    How strongly does the available telemetry support this interpretation?

TraceForge should not use severity as a substitute for diagnostic certainty.

The exact scoring systems will be defined later.
<hr>

## 4.19 Multiple Findings Within One Trace

A single trace may produce multiple findings.

Example:
```text
GET /checkout - 4.71 s

Findings:

HIGH
Likely originating failure
payment database timeout

HIGH
Major latency contributor
payment-service - 3.82 s critical-path contribution

MEDIUM
Repeated downstream operation
12 repeated inventory requests
```
Findings should not be presented as unrelated warnings if relationships between them are known.

Future versions may group related findings into a larger diagnostic narrative.

For v0.1, each finding may remain independently represented as long as its evidence is clear.
<hr>

## 4.20 Investigation Starting from a Service

Not every investigation begins with a known trace.

A developer may instead know:

    payment-service has been behaving strangely.

The workflow becomes:
```text
Open Services
    ↓
Select payment-service
    ↓
Inspect recent operations and traces
    ↓
Filter failed or slow traces
    ↓
Open trace
    ↓
Inspect findings
```
The service view should therefore provide routes into trace-level investigation.

It should not attempt to become a complete service-monitoring dashboard in v0.1.
<hr>

## 4.21 Investigation Starting from a Finding

TraceForge may provide a global findings view.

A developer may see:
```text
Recent Findings

14:42  Repeated DB operation      orders-service
14:39  Originating failure        payment-service
14:35  Major latency contributor  inventory-service
```
Selecting a finding should open the associated trace and focus the relevant evidence.

This allows the developer to begin an investigation from TraceForge's analysis rather than from a known application symptom.

This capability may be particularly useful during development sessions where the developer intentionally generates different application behaviours.
<hr>

## 4.22 Demo Application Workflow

The TraceForge repository should provide a demonstration application containing intentionally reproducible behaviours.

A developer evaluating TraceForge should be able to trigger scenarios such as:
- Normal request
- Slow downstream service
- Repeated database operation
- Repeated HTTP calls
- Propagated exception
- Concurrent calls
- Retry-like behaviour

For example:
    
    GET /demo/repeated-query

produces a controlled repeated-query trace.

The evaluation workflow becomes:
```text
Start TraceForge
        ↓
Start demo application
        ↓
Trigger known scenario
        ↓
Open generated trace
        ↓
Observe expected finding
        ↓
Inspect supporting spans
```
The demo environment therefore serves both product demonstration and engineering validation.
<hr>

## 4.23 Optional Explanation Workflow

If a future natural-language explanation layer is enabled, it should operate only after structured analysis is complete.

Example structured finding:
```text
Finding:
repeated_database_operation

Service:
orders-service

Count:
34

Combined duration:
2070 ms

Trace duration:
2810 ms
```
Optional explanation:
```text
orders-service performed the same logical database
operation 34 times during this request.

These operations accounted for approximately 74% of
the request duration.

This pattern may indicate redundant database access or
an N+1 query pattern.
```

The developer must still be able to inspect the structured finding directly.

Failure of the explanation layer should produce:

    Explanation unavailable

without affecting the diagnostic finding.
<hr>

## 4.24 Product Navigation Model

The initial information architecture should remain small.

A likely high-level navigation model is:
- Overview
- Traces
- Services
- Findings
- System

Each section should answer a specific question.

### Overview

    What is happening in the observed application right now?

### Traces

    What happened during individual requests?

### Services

    How are observed services behaving and interacting?

### Findings

    What significant behaviour has TraceForge detected?

### System

    Is TraceForge itself operating correctly?

This navigation model is conceptual and may change during UI design.

The principle is more important than the exact page names.
<hr>

## 4.25 Progressive Disclosure

TraceForge should present information in layers.

The initial view should emphasize diagnostic meaning.

For example:
```text
Potential repeated-query pattern

34 repeated operations
2.07 s combined duration
orders-service
```
The user may then expand into:

    Affected spans

and eventually into:

```text
OpenTelemetry attributes
events
resource metadata
instrumentation scope
raw identifiers
```

This avoids forcing users to interpret low-level telemetry before receiving useful information while preserving complete access for advanced investigation.
<hr>

## 4.26 Product Behaviour Principles

The workflows defined in this section imply several general behavioural principles.

### Diagnostic information should appear before raw complexity

TraceForge should surface significant findings early while keeping raw telemetry available for verification.

### Every conclusion must lead to evidence

A diagnostic message that cannot be traced back to supporting telemetry is insufficient.

### Missing information must be explicit

TraceForge must distinguish:

    No finding

from:

    Insufficient telemetry

from:

    Analysis failed
### Observation and interpretation must remain distinguishable

TraceForge may confidently state:

    34 structurally equivalent operations were observed.

while more cautiously stating:

    This may indicate an N+1 query pattern.
### The product should reduce investigation scope

The ideal output is not necessarily a complete explanation of the source-code bug.

It is a smaller, evidence-backed problem for the developer to investigate.

### Raw telemetry remains authoritative

Automated analysis is an interpretation layer.

The underlying telemetry remains available so that the developer can verify or reject TraceForge's conclusions.
<hr>

## 4.27 Definition of a Successful Investigation

A TraceForge investigation is successful when the product materially reduces the developer's search space.

For example:
```
Initial problem:

"Checkout sometimes takes four seconds."
```
TraceForge may reduce this to:
```
payment-service contributes 3.4 seconds to the
critical path.
```
Further analysis may reduce it to:

    payment-service waits 3.1 seconds for POST /charge.

The developer can then investigate the payment integration.

TraceForge does not need to determine the exact defective source-code line to provide meaningful value.

The system succeeds when it converts broad runtime symptoms into specific execution behaviour supported by observable evidence.

