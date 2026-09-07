# Functional Requirements

## 5.1 Purpose

This section defines the functional requirements that TraceForge must satisfy.

Unlike the user stories in Section 3, which describe desired behaviour from the user's perspective, the requirements in this section describe specific system capabilities.

Each requirement is assigned a stable identifier.

The initial requirement groups are:
```text
TF-INGEST-*      Telemetry ingestion
TF-TRACE-*       Trace reconstruction and retrieval
TF-SPAN-*        Span handling and inspection
TF-ANALYSIS-*    Diagnostic analysis
TF-FINDING-*     Finding generation and presentation
TF-SERVICE-*     Service discovery and dependencies
TF-SEARCH-*      Search and filtering
TF-SYSTEM-*      TraceForge system state
TF-DEMO-*        Demonstration and reproducibility
```
Requirements marked as v0.1 REQUIRED form part of the initial implementation target.

Requirements marked as DEFERRED may influence future design but must not expand the initial implementation unnecessarily.

## 5.2 Telemetry Ingestion Requirements
### TF-INGEST-001 - OTLP Trace Ingestion

Priority: **v0.1 REQUIRED**

TraceForge SHALL accept distributed trace telemetry using the OpenTelemetry Protocol.

The initial implementation SHALL support at least one standard OTLP transport supported by the OpenTelemetry ecosystem.

Support for additional transports MAY be added later.

TraceForge **SHALL NOT** require a proprietary telemetry SDK.

### TF-INGEST-002 - OpenTelemetry Collector Compatibility

Priority: **v0.1 REQUIRED**

TraceForge SHALL be compatible with telemetry forwarded by the official OpenTelemetry Collector.

The intended ingestion path SHALL support the following deployment model:
```text
Instrumented application
    ↓
OpenTelemetry Collector
    ↓
TraceForge
```

TraceForge MAY also support direct application-to-TraceForge OTLP export where technically appropriate.

### TF-INGEST-003 - Batch Processing

Priority: **v0.1 REQUIRED**

TraceForge SHALL accept telemetry containing multiple spans within a single ingestion request.

The ingestion layer SHALL process spans independently enough that failure of one malformed span does not unnecessarily invalidate unrelated valid spans unless required by the underlying protocol.

The exact partial-rejection behaviour SHALL be defined during ingestion architecture design.

### TF-INGEST-004 - Telemetry Validation

Priority: **v0.1 REQUIRED**

TraceForge SHALL validate incoming trace telemetry before persistence.

Validation SHALL include, where applicable:

- trace identifier validity;
- span identifier validity;
- timestamp validity;
- required structural fields;
- supported telemetry representation.

Invalid telemetry SHALL NOT cause undefined system behaviour.

### TF-INGEST-005 - Rejected Telemetry Visibility

Priority: **v0.1 REQUIRED**

When telemetry is rejected, TraceForge SHALL make the rejection observable.

The system SHALL record sufficient information to determine:

- when the rejection occurred;
- how many spans were affected;
- the general rejection reason.

Sensitive telemetry contents SHALL NOT be exposed unnecessarily in system diagnostics.

### TF-INGEST-006 - Duplicate Span Handling

Priority: **v0.1 REQUIRED**

TraceForge SHALL detect repeated ingestion of the same logical span where possible.

Duplicate ingestion SHALL NOT create multiple independently represented spans for the same trace and span identifier.

The exact conflict behaviour for duplicates containing different data SHALL be defined later.

### TF-INGEST-007 - Out-of-Order Span Arrival

Priority: **v0.1 REQUIRED**

TraceForge SHALL support spans arriving in an order different from their logical execution hierarchy.

A child span MAY be received before its parent.

Trace reconstruction SHALL therefore not depend on ingestion order.

### TF-INGEST-008 - Late Span Arrival

Priority: **v0.1 REQUIRED**

TraceForge SHALL support spans arriving after other parts of the same trace have already been stored.

Late-arriving spans SHALL be associated with the existing trace where identifiers permit.

The system SHALL define a completion policy determining when a trace is considered sufficiently complete for analysis.

## 5.3 Trace Reconstruction Requirements
### TF-TRACE-001 - Trace Grouping

Priority: **v0.1 REQUIRED**

TraceForge SHALL group spans belonging to the same distributed trace using their trace identifier.

All stored spans with the same valid trace identifier SHALL be discoverable as part of the same logical trace.

### TF-TRACE-002 - Parent-Child Reconstruction

Priority: **v0.1 REQUIRED**

TraceForge SHALL reconstruct parent-child span relationships using span and parent-span identifiers.

The reconstructed hierarchy SHALL remain valid regardless of span ingestion order.

### TF-TRACE-003 - Root Span Identification

Priority: **v0.1 REQUIRED**

TraceForge SHALL identify one or more candidate root spans within a trace.

A trace containing multiple root candidates SHALL NOT cause trace reconstruction to fail.

Such traces SHALL be represented as structurally unusual or incomplete where appropriate.

### TF-TRACE-004 - Missing Parent Handling

Priority: **v0.1 REQUIRED**

TraceForge SHALL tolerate spans referencing parent spans that have not been observed.

Such spans SHALL remain inspectable.

Missing parent relationships SHALL be represented explicitly rather than silently discarded.

### TF-TRACE-005 - Trace Duration

Priority: **v0.1 REQUIRED**

TraceForge SHALL calculate observable trace duration using available span timing information.

The system SHALL distinguish between:

- total wall-clock trace duration;
- accumulated span duration;
- critical-path duration where analysis is available.

These quantities SHALL NOT be treated as equivalent.

### TF-TRACE-006 - Trace Status

Priority: **v0.1 REQUIRED**

TraceForge SHALL expose the observed status of a trace.

Trace status MAY be derived from:

- root-span status;
- error events;
- HTTP status attributes;
- child span failures;

but the exact derivation rules SHALL be formally defined later.

Trace status SHALL remain distinguishable from TraceForge's own analysis status.

### TF-TRACE-007 - Trace Completeness State

Priority: **v0.1 REQUIRED**

TraceForge SHALL maintain an explicit trace-processing state.

At minimum, the system SHALL distinguish:

    PROCESSING
    COMPLETE
    INCOMPLETE

Additional internal states MAY exist.

A trace SHALL NOT be considered complete solely because one span has ended.

### TF-TRACE-008 - Trace Analysis State

Priority: **v0.1 REQUIRED**

TraceForge SHALL represent diagnostic analysis state separately from trace completeness.

At minimum:
```
PENDING
RUNNING
COMPLETE
FAILED
PARTIAL
```
or equivalent states SHALL be representable.

This distinction SHALL allow the UI to differentiate:

    No findings detected.

from:

    Analysis did not complete.

## 5.4 Span Requirements
### TF-SPAN-001 - Raw Span Preservation

Priority: **v0.1 REQUIRED**

TraceForge SHALL preserve sufficient original span information to allow users to inspect the telemetry on which analysis is based.

Stored information SHALL include, where available:

- trace ID;
- span ID;
- parent span ID;
- span name;
- span kind;
- start timestamp;
- end timestamp;
- status;
- attributes;
- events;
- resource attributes;
- instrumentation scope.

## TF-SPAN-002 - Derived Span Duration

Priority: **v0.1 REQUIRED**

TraceForge SHALL calculate span duration from valid start and end timestamps.

Invalid temporal relationships SHALL be detectable.

For example:

    end_timestamp < start_timestamp

SHALL NOT silently produce a valid positive duration.

### TF-SPAN-003 - Service Association

Priority: **v0.1 REQUIRED**

TraceForge SHALL associate spans with an observed service where sufficient resource information exists.

The primary service identity SHOULD follow OpenTelemetry semantic conventions where possible.

Spans without identifiable service information SHALL remain ingestible and inspectable.

### TF-SPAN-004 - Span Event Preservation

Priority: **v0.1 REQUIRED**

TraceForge SHALL preserve span events required for diagnostics.

This includes exception-related events where present.

### TF-SPAN-005 - Span Attribute Access

Priority: **v0.1 REQUIRED**

Users SHALL be able to inspect stored span attributes.

TraceForge MAY present frequently useful semantic attributes separately from the full attribute set.

## 5.5 Trace Retrieval Requirements
### TF-TRACE-009 - Recent Trace Listing

Priority: **v0.1 REQUIRED**

TraceForge SHALL provide a list of recently observed traces.

The trace list SHALL expose enough summary information to support investigation without opening every trace.

Summary information SHOULD include:

- start time;
- primary operation;
- initiating or root service;
- duration;
- status;
- span count;
- participating service count;
- number of findings.

### TF-TRACE-010 - Trace Detail Retrieval

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow retrieval of a complete stored trace by trace identifier.

The returned representation SHALL contain enough information to reconstruct:

- span hierarchy;
- timing relationships;
- participating services;
- status;
- diagnostic findings.

### TF-TRACE-011 - Waterfall-Compatible Timing Data

Priority: **v0.1 REQUIRED**

TraceForge SHALL expose timing data sufficient for the client to render trace execution on a shared timeline.

This SHALL include absolute or trace-relative timing information necessary to represent:

- sequential execution;
overlapping execution;
- nested spans.


## 5.6 Search and Filtering Requirements
### TF-SEARCH-001 - Filter by Time Range

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow traces to be filtered by observation or execution time.

### TF-SEARCH-002 - Filter by Service

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow traces involving a specified service to be retrieved.

### TF-SEARCH-003 - Filter by Operation

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow traces to be filtered by operation or route where such information is available.

### TF-SEARCH-004 - Filter by Status

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow traces to be filtered by observed success or failure state.

### TF-SEARCH-005 - Filter by Duration

Priority: **v0.1 REQUIRED**

TraceForge SHALL support retrieving traces above or below a specified duration threshold.

### TF-SEARCH-006 - Filter by Finding Presence

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow users to retrieve traces according to whether diagnostic findings exist.

Filtering by individual finding type MAY be included in v0.1 if implementation complexity is low.

### TF-SEARCH-007 - Trace ID Lookup

Priority: **v0.1 REQUIRED**

TraceForge SHALL allow direct lookup of a trace by trace identifier.

### TF-SEARCH-008 - Advanced Query Language

Priority: **DEFERRED**

TraceForge is NOT required to implement a general-purpose observability query language in v0.1.

Future requirements MAY introduce one if common investigation workflows cannot be expressed adequately using structured filters.

## 5.7 Analysis Engine Requirements

### TF-ANALYSIS-001 - Automatic Trace Analysis

Priority: **v0.1 REQUIRED**

TraceForge SHALL automatically evaluate eligible traces using configured diagnostic detectors.

The user SHALL NOT be required to manually trigger basic analysis for every trace.

### TF-ANALYSIS-002 - Detector Isolation

Priority: **v0.1 REQUIRED**

A failure in one diagnostic detector SHOULD NOT prevent unrelated detectors from producing findings where technically feasible.

The analysis engine SHALL preserve enough execution state to distinguish:

    Detector produced no finding.

from:

    Detector failed to execute.

### TF-ANALYSIS-003 - Deterministic Core Analysis

Priority: **v0.1 REQUIRED**

Core diagnostic findings SHALL be generated using deterministic or reproducible analysis logic.

A language model SHALL NOT be required to produce the initial diagnostic result.

### TF-ANALYSIS-004 - Critical Path Analysis

Priority: **v0.1 REQUIRED**

TraceForge SHALL analyze temporal span relationships to estimate the effective critical path through a trace.

The algorithm SHALL account for overlapping spans.

The system SHALL NOT derive critical-path latency by simply summing all span durations.

### TF-ANALYSIS-005 - Major Latency Contributor Detection

Priority: **v0.1 REQUIRED**

TraceForge SHALL identify spans or operations that contribute significantly to the effective latency of a trace.

Parent spans SHALL NOT automatically be classified as primary contributors merely because their duration includes child execution.

### TF-ANALYSIS-006 - Repeated Database Operation Detection

Priority: **v0.1 REQUIRED**

TraceForge SHALL identify repeated structurally equivalent database operations occurring within the same trace.

Detection SHALL operate on a normalized representation where possible.

Parameter-value differences SHOULD NOT prevent structurally equivalent operations from being grouped.

### TF-ANALYSIS-007 - Repeated Downstream Request Detection

Priority: **v0.1 TARGET**

TraceForge SHOULD identify repeated structurally equivalent downstream service requests within a trace.

This requirement MAY be postponed from the earliest implementation milestone if necessary, provided the analysis architecture supports adding it without redesign.

### TF-ANALYSIS-008 - Error Origin Analysis

Priority: **v0.1 REQUIRED**

TraceForge SHALL attempt to identify the earliest relevant error associated with a propagated failure chain.

The result SHALL be expressed as a probable or observed error origin rather than an unconditional source-code root cause.

### TF-ANALYSIS-009 - Error Propagation Reconstruction

Priority: **v0.1 REQUIRED**

TraceForge SHALL identify relationships between errors occurring across parent and child spans where telemetry permits.

The system SHOULD distinguish likely originating failures from subsequent propagated failures.

### TF-ANALYSIS-010 - Incomplete Trace Awareness

Priority: **v0.1 REQUIRED**

Each diagnostic detector SHALL define the trace information it requires.

A detector SHALL NOT silently produce a definitive conclusion when required telemetry is known to be missing.

The analysis system SHALL support partial analysis of incomplete traces where specific detectors remain valid.

### TF-ANALYSIS-011 - Historical Baseline Analysis

Priority: **DEFERRED**

TraceForge is NOT required in the initial implementation to detect abnormalities using long-term statistical baselines.

Initial analysis SHOULD prioritize deterministic single-trace behaviour.

## 5.8 Finding Requirements
### TF-FINDING-001 - Structured Finding Representation

Priority: **v0.1 REQUIRED**

Every diagnostic finding SHALL use a common structured representation.

The finding model SHALL be capable of representing at least:

- identifier
- finding type
- severity
- confidence
- trace reference
- related span references
- summary
- evidence
- analysis timestamp
- detector identity/version

The exact schema SHALL be defined later.

### TF-FINDING-002 - Evidence Association

Priority: **v0.1 REQUIRED**

Every diagnostic finding SHALL contain or reference the telemetry evidence used to produce it.

A finding SHALL NOT exist solely as an untraceable textual conclusion.

### TF-FINDING-003 - Related Span Navigation

Priority: **v0.1 REQUIRED**

A user SHALL be able to navigate from a finding to the span or spans associated with its evidence.

### TF-FINDING-004 - Observation vs Interpretation

Priority: **v0.1 REQUIRED**

TraceForge SHALL distinguish directly observable facts from diagnostic interpretation where necessary.

For example:
```
Observed:
34 structurally equivalent database spans occurred.
```
and:
```
Interpretation:
This may represent an N+1 query pattern.
```

SHALL NOT be represented as equivalent levels of certainty.

### TF-FINDING-005 - Finding Severity

Priority: **v0.1 REQUIRED**

Findings SHALL support a severity classification.

The exact severity model SHALL be defined during analysis-engine design.

Severity SHALL represent the potential importance or impact of the observed behaviour.

### TF-FINDING-006 - Finding Confidence

Priority: **v0.1 REQUIRED**

Findings SHALL support a confidence classification or score where interpretation is involved.

Confidence SHALL represent the strength of evidence supporting the diagnostic interpretation.

Confidence and severity SHALL remain separate concepts.

### TF-FINDING-007 - No-Finding State

Priority: **v0.1 REQUIRED**

TraceForge SHALL explicitly represent successful analysis that produces no findings.

This SHALL remain distinguishable from:

- pending analysis;
- failed analysis;
- incomplete analysis.

### TF-FINDING-008 - Finding Detector Version

Priority: **v0.1 TARGET**

TraceForge SHOULD record which detector and detector version produced a finding.

This supports:

- reproducibility;
- debugging;
- later re-analysis;
- understanding behavioural changes between TraceForge versions.


## 5.9 Service Discovery Requirements
### TF-SERVICE-001 - Automatic Service Discovery

Priority: **v0.1 REQUIRED**

TraceForge SHALL derive observed services from received telemetry.

Users SHALL NOT be required to manually register services before telemetry can be viewed.

### TF-SERVICE-002 - Service Inventory

Priority: **v0.1 REQUIRED**

TraceForge SHALL expose a list of observed services.

Each service SHOULD expose basic information such as:

- service name;
- first observed timestamp;
- last observed timestamp;
- observed operation count;
- recent trace count.

### TF-SERVICE-003 - Observed Dependency Graph

Priority: **v0.1 REQUIRED**

TraceForge SHALL derive service-to-service dependencies from observed trace relationships.

The graph SHALL represent runtime-observed interactions rather than configured architecture.

### TF-SERVICE-004 - Dependency Evidence

Priority: **v0.1 REQUIRED**

A service dependency SHALL be traceable to telemetry demonstrating the relationship.

The user SHOULD be able to navigate from a dependency to traces in which that dependency occurred.

### TF-SERVICE-005 - Service Relationship Statistics

Priority: **v0.1 TARGET**

TraceForge SHOULD expose lightweight aggregate information about observed service relationships.

Potential information includes:

- observed request count;
- error count;
- observed latency;
- operations.

This SHALL NOT expand into a general metrics platform in v0.1.

## 5.10 System State Requirements
### TF-SYSTEM-001 - Ingestion Health

Priority: **v0.1 REQUIRED**

TraceForge SHALL expose whether the ingestion subsystem is operational.

## TF-SYSTEM-002 - Last Telemetry Reception

Priority: **v0.1 REQUIRED**

TraceForge SHALL expose when telemetry was most recently received.

Where possible, this SHOULD also be available per observed service.

## TF-SYSTEM-003 - Analysis Health

Priority: **v0.1 REQUIRED**

TraceForge SHALL expose whether diagnostic analysis is operating successfully.

The system SHOULD expose recent analysis failures in a developer-readable form.

### TF-SYSTEM-004 - Storage Health

Priority: **v0.1 REQUIRED**

TraceForge SHALL detect and expose loss of access to its required persistence layer.

### TF-SYSTEM-005 - Empty State

Priority: **v0.1 REQUIRED**

When no telemetry has been received, TraceForge SHALL present an explicit first-run or empty state.

An empty dataset SHALL NOT be visually indistinguishable from system failure.

## 5.11 Demo Environment Requirements
### TF-DEMO-001 - Reproducible Demo Application

Priority: **v0.1 REQUIRED**

The TraceForge project SHALL include or provide a reproducible demonstration application capable of generating distributed traces.

### TF-DEMO-002 - Normal Request Scenario

Priority: **v0.1 REQUIRED**

The demo environment SHALL provide at least one healthy request workflow that should produce no significant diagnostic findings.

### TF-DEMO-003 - Repeated Database Scenario

Priority: **v0.1 REQUIRED**

The demo environment SHALL provide a deterministic scenario producing repeated structurally similar database spans.

This scenario SHALL be suitable for validating repeated-database-operation detection.

### TF-DEMO-004 - Slow Dependency Scenario

Priority: **v0.1 REQUIRED**

The demo environment SHALL provide a deterministic scenario in which a downstream operation contributes substantially to trace latency.

This scenario SHALL validate critical-path and major-latency-contributor analysis.

### TF-DEMO-005 - Propagated Error Scenario

Priority: **v0.1 REQUIRED**

The demo environment SHALL provide a deterministic scenario in which an error originates in a downstream operation and propagates through upstream services.

This scenario SHALL validate error-origin and error-propagation analysis.

### TF-DEMO-006 - Concurrent Operation Scenario

Priority: **v0.1 REQUIRED**

The demo environment SHALL provide a scenario containing overlapping downstream operations.

This SHALL validate that accumulated span duration is not incorrectly interpreted as request wall-clock duration.

### TF-DEMO-007 - Repeated HTTP Scenario

Priority: **v0.1 TARGET**

The demo environment SHOULD provide a scenario containing repeated structurally similar downstream requests.

### TF-DEMO-008 - Incomplete Trace Scenario

Priority: **v0.1 TARGET**

The development/test environment SHOULD provide a mechanism for validating behaviour when traces contain missing parents or incomplete span sets.

This MAY be produced through synthetic telemetry rather than ordinary application execution.
## 5.12 Optional Explanation Requirements
### TF-EXPLAIN-001 — Natural Language Explanation

Priority: **DEFERRED**

TraceForge MAY provide natural-language explanations of diagnostic findings.

### TF-EXPLAIN-002 — Structured Input Requirement

Priority: **DEFERRED**

Any natural-language explanation component SHALL consume structured diagnostic findings and their evidence rather than raw telemetry as its sole diagnostic input.

### TF-EXPLAIN-003 — Explanation Independence

Priority: **DEFERRED**

Failure or absence of the explanation component SHALL NOT prevent core diagnostic findings from being generated or displayed.

## 5.13 Explicitly Excluded Functional Requirements

The following capabilities are intentionally excluded from the initial implementation.

TraceForge v0.1 SHALL NOT require:

- full-text log ingestion and search
- general infrastructure monitoring
- business analytics
- production alert management
- incident ticketing
- multi-tenant organization management
- billing
- enterprise RBAC
- SSO
- Kubernetes-native operation
- proprietary telemetry instrumentation
- long-term statistical anomaly detection
- LLM-based primary diagnosis

These exclusions SHALL remain valid unless changed explicitly through a later design decision.

## 5.14 Requirement Traceability

Functional requirements SHOULD be traceable to:
```text
Product problem
    ↓
User story
    ↓
Functional requirement
    ↓
Architecture component
    ↓
Implementation
    ↓
Test
```
For example:
```
US-REPEAT-001
Detect repeated database operations
            ↓
TF-ANALYSIS-006
Repeated database operation detection
            ↓
RepeatedOperationDetector
            ↓
integration/demo/repeated-query
            ↓
automated validation
```

The exact implementation name shown above is illustrative and does not prescribe the final architecture.

This traceability model exists to ensure that major implemented capabilities correspond to actual product requirements.

## 5.15 Requirement Change Policy

The functional requirements in this document are expected to evolve as the design becomes more precise.

However, changes SHOULD be intentional.

If implementation reveals that a requirement is:

- technically invalid;
- unnecessarily restrictive;
- insufficiently precise;
- incompatible with another requirement;

the requirement SHOULD be updated in this document rather than silently ignored in code.

A requirement should not become permanent merely because an early implementation happened to behave a certain way.

## 5.16 v0.1 Functional Definition

TraceForge v0.1 is functionally complete when it can:
```
receive real OpenTelemetry traces
        ↓
validate and persist spans
        ↓
reconstruct distributed traces
        ↓
display trace hierarchy and timing
        ↓
discover observed services
        ↓
construct an observed dependency graph
        ↓
analyze traces deterministically
        ↓
identify critical latency behaviour
        ↓
detect repeated database operations
        ↓
identify likely propagated error origins
        ↓
produce structured evidence-backed findings
        ↓
allow the developer to inspect the supporting telemetry
```
This definition intentionally excludes broader observability capabilities.

The initial product succeeds by performing a small number of diagnostic tasks reliably rather than a large number of observability tasks superficially.