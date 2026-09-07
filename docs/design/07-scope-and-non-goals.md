# 7. Scope and Non-Goals

## 7.1 Purpose

This section defines the boundaries of TraceForge v0.1.

The objective is to make explicit:

* what TraceForge is expected to do;
* what TraceForge may reasonably support later;
* what TraceForge intentionally does not attempt to solve.

This section exists to prevent architectural and implementation complexity from being introduced for capabilities that are not part of the initial product.

The existence of a potentially useful feature does not make that feature part of TraceForge v0.1.

A capability should enter scope only if it directly supports the central product objective:

> **Reduce the amount of distributed-system behaviour a developer must reconstruct manually from telemetry.**

---

## 7.2 v0.1 Product Scope

TraceForge v0.1 focuses on **distributed trace ingestion, reconstruction, visualization, and deterministic diagnostic analysis for small development and staging environments**.

The initial product SHALL support the following capability areas.

---

### 7.2.1 OpenTelemetry Trace Ingestion

TraceForge v0.1 SHALL accept distributed trace telemetry using standard OpenTelemetry-compatible mechanisms.

The product SHALL support:

```text
instrumented application
        ↓
OpenTelemetry Collector
        ↓
TraceForge
```

The product MAY also support direct OTLP export from applications where appropriate.

TraceForge SHALL NOT require a proprietary SDK.

---

### 7.2.2 Trace Reconstruction

TraceForge SHALL reconstruct distributed request execution from received spans.

This includes:

* grouping spans into traces;
* reconstructing parent-child relationships;
* tolerating out-of-order span arrival;
* representing missing parents;
* identifying candidate roots;
* preserving timing relationships;
* representing incomplete traces.

Trace reconstruction is a core capability because all downstream diagnostic analysis depends on a trustworthy execution model.

---

### 7.2.3 Trace Inspection

TraceForge SHALL allow developers to inspect individual distributed traces.

The trace inspection experience SHALL include:

* trace summary;
* execution hierarchy;
* timing relationships;
* service boundaries;
* span status;
* errors;
* individual span details;
* associated diagnostic findings.

A timeline or waterfall representation is within v0.1 scope.

---

### 7.2.4 Trace Search and Filtering

TraceForge SHALL support common investigation-oriented trace filtering.

Initial filters include:

* time range;
* service;
* operation;
* success or failure;
* duration;
* trace identifier;
* presence of findings.

A general-purpose telemetry query language is not required.

---

### 7.2.5 Service Discovery

TraceForge SHALL derive observed services from incoming telemetry.

The product SHALL provide:

* service inventory;
* first and last observation information;
* links to related traces;
* observed runtime dependencies.

Services SHALL be discovered dynamically rather than manually registered.

---

### 7.2.6 Observed Service Dependency Graph

TraceForge SHALL construct a service graph from observed distributed trace relationships.

The graph SHALL represent:

> **what services were observed communicating**

rather than:

> **what services are configured to exist**

The dependency graph SHALL serve as an investigation aid.

It SHALL NOT attempt to become a complete infrastructure topology platform.

---

## 7.3 v0.1 Diagnostic Analysis Scope

Automated diagnostic analysis is the defining feature of TraceForge.

The first version SHALL implement a deliberately small number of detectors well rather than attempting broad but unreliable diagnosis.

---

### 7.3.1 Critical Path Analysis

TraceForge SHALL analyze span timing and overlap to estimate the effective critical execution path of a request.

The analysis SHALL distinguish:

```text
wall-clock duration
```

from:

```text
accumulated span duration
```

and SHALL avoid simply summing durations of concurrent operations.

---

### 7.3.2 Major Latency Contributor Detection

TraceForge SHALL identify operations that contribute significantly to observed request latency.

The system SHALL account for child execution and overlap sufficiently to avoid treating every long parent span as the true source of latency.

---

### 7.3.3 Repeated Database Operation Detection

TraceForge SHALL detect repeated structurally equivalent database operations within a trace.

The detector SHOULD normalize operation structure so that parameter-value differences do not prevent grouping.

The system MAY report that the pattern:

```text
may indicate redundant database access
```

or:

```text
may indicate an N+1 query pattern
```

but SHALL NOT state this as a definitive source-code diagnosis without stronger evidence.

---

### 7.3.4 Error Origin Analysis

TraceForge SHALL attempt to identify the earliest relevant failure within a propagated error chain.

The output SHALL be phrased conservatively.

For example:

```text
Likely originating failure based on observed telemetry.
```

rather than:

```text
Definitive root cause.
```

---

### 7.3.5 Error Propagation Visualization

TraceForge SHALL help distinguish:

* likely originating failures;
* subsequent propagated failures;
* unaffected branches;
* recoverable or isolated failures where detectable.

---

### 7.3.6 Repeated Downstream Operation Detection

Repeated downstream HTTP or RPC operation detection is within the intended v0.1 architecture.

It is a **target capability**, but MAY be implemented after the mandatory detectors if necessary.

The architecture SHALL not prevent this detector from being added cleanly.

---

## 7.4 Finding Scope

TraceForge v0.1 SHALL provide a common finding model.

A finding SHALL be capable of representing:

```text
type
severity
confidence
summary
evidence
trace reference
related span references
detector identity
analysis timestamp
```

Every diagnostic finding SHALL be evidence-backed.

TraceForge SHALL preserve the distinction between:

```text
observation
```

and:

```text
interpretation
```

For example:

```text
Observation:
34 structurally equivalent database spans occurred.
```

```text
Interpretation:
This may indicate an N+1 query pattern.
```

These statements SHALL NOT be treated as having identical certainty.

---

## 7.5 v0.1 Deployment Scope

The primary deployment target for TraceForge v0.1 is:

```text
local development
shared development
small staging environments
```

The primary deployment mechanism SHALL be:

```text
Docker Compose
```

The initial system SHOULD be practical to run on an ordinary development workstation.

TraceForge v0.1 is not intended to require:

* Kubernetes;
* distributed databases;
* clustered workers;
* message streaming infrastructure;
* external control planes.

These technologies may be evaluated later if justified by real requirements.

---

## 7.6 v0.1 Scale Boundary

TraceForge v0.1 is intended for applications with approximately:

```text
3–20 application services
```

and workloads appropriate for development and small staging environments.

The system SHOULD tolerate moderate growth beyond these numbers.

However, architecture SHALL NOT be optimized primarily for:

```text
hundreds of services
millions of spans per second
multi-region ingestion
petabyte-scale telemetry retention
```

unless future product requirements explicitly change this scope.

---

## 7.7 Demo Application Scope

The project SHALL include a reproducible demo environment.

The demo SHALL be capable of producing controlled traces representing at least:

```text
normal request
slow downstream dependency
repeated database access
propagated failure
concurrent downstream operations
```

Additional scenarios MAY include:

```text
repeated HTTP calls
retry-like behaviour
missing parent spans
late span arrival
```

The demo application serves four roles:

* product demonstration;
* integration testing;
* detector validation;
* developer onboarding.

It SHALL therefore be treated as part of the TraceForge project rather than disposable sample code.

---

## 7.8 Explicit Non-Goals for v0.1

The following capabilities are intentionally outside the initial scope.

Their exclusion is deliberate and should prevent them from influencing the architecture unnecessarily.

---

### 7.8.1 Full Log Management Platform

TraceForge v0.1 SHALL NOT attempt to provide:

* arbitrary log ingestion;
* full-text log indexing;
* log retention management;
* advanced log query language;
* centralized log dashboards.

Logs MAY later be correlated with traces if this improves diagnosis.

TraceForge SHALL NOT attempt to become a replacement for dedicated log platforms in v0.1.

---

### 7.8.2 General Metrics Platform

TraceForge v0.1 SHALL NOT provide a complete metrics monitoring system.

Out of scope capabilities include:

* arbitrary Prometheus-style metric ingestion;
* long-term metric dashboards;
* infrastructure monitoring;
* capacity planning dashboards;
* general time-series analytics.

TraceForge MAY expose its own internal operational metrics.

Future versions MAY consume selected metrics when they provide useful diagnostic context.

---

### 7.8.3 Infrastructure Monitoring

TraceForge is not initially responsible for monitoring:

```text
CPU
memory
disk
network
container resource usage
host availability
```

These signals may become useful diagnostic inputs in future versions.

They are not required for the core trace-analysis product.

---

### 7.8.4 Production Alerting

TraceForge v0.1 SHALL NOT implement a general alerting platform.

Out-of-scope functionality includes:

* alert rule configuration;
* email notifications;
* Slack notifications;
* PagerDuty integration;
* escalation policies;
* on-call scheduling.

The initial workflow is investigation-driven rather than alert-driven.

---

### 7.8.5 Incident Management

TraceForge SHALL NOT initially manage:

* incidents;
* incident ownership;
* incident timelines;
* remediation tasks;
* postmortems;
* ticketing workflow.

TraceForge may eventually integrate with systems that provide these capabilities.

---

### 7.8.6 Multi-Tenancy

TraceForge v0.1 SHALL NOT support complex organizational multi-tenancy.

The product SHALL NOT initially require:

* organizations;
* workspaces;
* teams;
* tenant-specific storage;
* tenant isolation policies;
* organization administrators.

The deployment model assumes a trusted local or development environment.

---

### 7.8.7 Enterprise Authentication and Authorization

The initial version SHALL NOT require:

```text
SSO
SAML
OIDC enterprise identity integration
complex RBAC
fine-grained permission policies
```

Basic access protection MAY be introduced if needed.

However, enterprise identity management SHALL NOT influence the core v0.1 architecture.

---

### 7.8.8 SaaS Hosting and Billing

TraceForge v0.1 is not intended to operate as a commercial hosted SaaS platform.

The project SHALL NOT include:

* subscription management;
* customer billing;
* usage metering for billing;
* account plans;
* payment processing;
* commercial customer onboarding.

The initial product is self-hosted.

---

### 7.8.9 Kubernetes-Native Operation

Kubernetes support is explicitly outside the initial implementation.

TraceForge SHALL NOT require:

* Helm charts;
* Kubernetes operators;
* CRDs;
* service-mesh integration;
* cluster discovery;
* Kubernetes RBAC;
* horizontal pod autoscaling.

These MAY become future capabilities.

The initial architecture SHOULD not deliberately prevent future container orchestration support, but SHALL NOT optimize around it.

---

### 7.8.10 Distributed TraceForge Deployment

TraceForge v0.1 SHALL NOT require independently scalable distributed deployment of internal components.

The architecture MAY contain logical components such as:

```text
ingestion
analysis
API
frontend
```

but these responsibilities do not automatically need separate network services.

Physical separation SHALL require justification.

---

### 7.8.11 Enterprise Telemetry Scale

TraceForge SHALL NOT claim or attempt to guarantee enterprise telemetry performance in v0.1.

Examples of out-of-scope goals include:

```text
millions of spans per second
multi-region ingestion
geo-replicated storage
automatic sharding
petabyte-scale retention
```

The architecture should remain sensible, but enterprise scalability is not an initial acceptance criterion.

---

### 7.8.12 Long-Term Telemetry Warehousing

TraceForge v0.1 SHALL NOT optimize for indefinite telemetry retention.

The system MAY retain traces for the duration appropriate to development and testing.

Retention controls should remain architecturally possible.

Long-term analytical warehousing is outside the initial product definition.

---

### 7.8.13 Full Statistical Anomaly Detection

TraceForge v0.1 SHALL NOT require machine-learning or historical statistical anomaly detection.

Examples include:

```text
seasonality modelling
dynamic latency baselines
automatic clustering of behavioural anomalies
unsupervised failure detection
```

Initial diagnostic analysis SHALL prioritize deterministic single-trace behaviour.

Historical comparison MAY be introduced later.

---

### 7.8.14 AI-Dependent Diagnosis

TraceForge SHALL NOT depend on a language model to produce core findings.

The following architecture is outside the product philosophy:

```text
raw telemetry
    ↓
LLM
    ↓
diagnosis
```

The supported future direction is:

```text
raw telemetry
    ↓
deterministic analysis
    ↓
structured findings
    ↓
optional explanation model
```

The product must remain diagnostically useful without AI access.

---

### 7.8.15 Automatic Source-Code Root Cause Identification

TraceForge SHALL NOT claim that runtime telemetry alone can reliably identify the exact defective source-code line.

For example, TraceForge may identify:

```text
orders-service performs 34 repeated product queries.
```

It SHOULD NOT claim:

```text
Line 87 of OrderRepository.java is the root cause.
```

unless future integrations provide sufficient evidence to support such a conclusion.

The product goal is to reduce the developer's investigation space, not to replace source-code debugging entirely.

---

### 7.8.16 Code Profiling

TraceForge is not initially a CPU or memory profiler.

It SHALL NOT attempt to replace tools that provide:

* stack sampling;
* flame graphs from runtime profiling;
* heap analysis;
* allocation profiling;
* lock-contention profiling.

TraceForge analyzes distributed request telemetry.

---

### 7.8.17 Application Performance Optimization

TraceForge SHALL identify suspicious runtime behaviour.

It SHALL NOT automatically modify application code or configuration to optimize performance.

For example, it may report:

```text
17 structurally similar calls executed sequentially.
```

It SHALL NOT automatically rewrite application logic to execute them concurrently.

---

### 7.8.18 Security Monitoring

TraceForge is not a SIEM or intrusion-detection platform.

It SHALL NOT initially attempt to identify:

* malicious traffic;
* account compromise;
* data exfiltration;
* attack patterns;
* suspicious authentication behaviour.

Security remains important for TraceForge itself, but security analytics are not part of the initial product.

---

### 7.8.19 Business Analytics

TraceForge SHALL NOT provide product analytics such as:

```text
conversion rates
customer funnels
feature engagement
revenue analytics
user behaviour analytics
```

TraceForge analyzes technical application execution.

---

## 7.9 Features That Are Supporting Capabilities, Not Product Goals

Several capabilities are necessary but should not become the center of the project.

These include:

```text
trace waterfall
service graph
trace filters
service pages
system health screen
```

These features support investigation.

They are not individually sufficient reasons for TraceForge to exist.

The product should not evolve into:

> A collection of increasingly sophisticated observability dashboards.

The diagnostic engine remains the defining capability.

---

## 7.10 Future-Scope Candidates

The following capabilities are plausible future directions but are intentionally undecided.

Their presence here does not constitute a commitment to implement them.

Possible future areas include:

#### Trace-to-log correlation

Relevant application logs may be attached to trace context to improve diagnosis.

#### Trace-to-metric correlation

Infrastructure or application metrics may provide contextual evidence for slow or failed traces.

#### Historical behavioural baselines

TraceForge may compare a trace against previous executions of the same logical operation.

#### Statistical anomaly detection

Unusual span counts, latency, dependency relationships, or execution structure may eventually be detected automatically.

#### Retry analysis

TraceForge may implement more sophisticated classification of repeated downstream operations as retries.

#### Messaging and asynchronous workflows

Future versions may better reconstruct request flows involving:

* queues;
* event buses;
* message brokers;
* asynchronous workers.

#### Kubernetes integration

TraceForge may eventually discover runtime context from container orchestration environments.

#### Source-code correlation

Telemetry may eventually be linked to:

* repository;
* deployment version;
* commit;
* source location;

where instrumentation provides sufficient information.

#### Natural-language explanation

Structured deterministic findings may optionally be summarized through a language model.

#### Detector plugins

The analysis engine may eventually support externally defined or configurable detectors.

#### Production deployment

Future releases may introduce authentication, retention policies, alerting, scaling, and deployment capabilities required for production environments.

Each of these features must be justified against the product thesis before entering active scope.

---

## 7.11 Scope Admission Criteria

A new capability SHOULD enter active TraceForge scope only if at least one of the following is true:

#### It directly improves diagnosis

Example:

```text
Adding retry detection helps explain repeated downstream execution.
```

#### It is required to support a core diagnostic capability

Example:

```text
A normalization layer is required for reliable repeated-query detection.
```

#### It significantly improves investigation usability

Example:

```text
Highlighting spans referenced by a finding reduces manual searching.
```

#### It removes a meaningful operational barrier

Example:

```text
A simple retention policy prevents a development deployment from filling its disk.
```

A feature SHOULD NOT enter scope merely because:

```text
other observability products have it
```

or:

```text
the technology would be interesting to implement.
```

Interesting engineering is valuable, but it must remain connected to the product.

---

## 7.12 Scope Escalation Rule

If a proposed feature introduces one or more major new architectural concerns, it SHOULD require an explicit design decision before implementation.

Examples include features requiring:

* a new database;
* a message broker;
* a new externally deployed service;
* authentication;
* distributed coordination;
* background scheduling;
* major schema redesign;
* a new telemetry signal;
* a machine-learning model.

The relevant question is:

> **Does the expected product value justify the additional permanent system complexity?**

If the answer is unclear, the feature should remain out of scope.

---

## 7.13 v0.1 Definition Boundary

A concise representation of the initial product boundary is:

```text
                        TRACEFORGE v0.1

        ┌───────────────────────────────────────┐
        │         OpenTelemetry Traces          │
        └───────────────────┬───────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │      Ingestion + Reconstruction       │
        └───────────────────┬───────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │          Trace Inspection             │
        └───────────────────┬───────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │       Deterministic Analysis          │
        │                                       │
        │ • critical path                       │
        │ • latency contributors                │
        │ • repeated DB operations              │
        │ • error origin / propagation          │
        └───────────────────┬───────────────────┘
                            ↓
        ┌───────────────────────────────────────┐
        │      Evidence-Backed Findings         │
        └───────────────────────────────────────┘
```

Everything surrounding this core should be evaluated according to whether it materially supports that flow.

---

## 7.14 v0.1 Completion Rule

TraceForge v0.1 SHALL be considered complete based on the quality of its defined capabilities rather than the breadth of its feature set.

The project does not need:

```text
logs
metrics
Kubernetes
AI
alerting
enterprise authentication
distributed storage
```

before it can be considered a successful first release.

It does need to perform the following reliably:

```text
receive a real distributed trace
        ↓
reconstruct it correctly
        ↓
allow the developer to inspect it
        ↓
analyze meaningful execution behaviour
        ↓
produce trustworthy structured findings
        ↓
show the evidence supporting those findings
```

A smaller product that performs this workflow correctly is preferable to a larger observability platform whose diagnostic functionality remains superficial.

---

## 7.15 Core Scope Principle

When deciding whether something belongs in TraceForge, the default question should be:

> **Does this help explain distributed request behaviour, or does it merely add more telemetry infrastructure?**

If a proposed feature primarily increases the quantity of data TraceForge can collect or display without improving interpretation, it should normally remain outside the core product scope.

TraceForge should become more valuable by becoming better at **reasoning over telemetry**, not merely by accumulating more of it.
