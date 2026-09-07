# 1. Problem statement
## 1.1 Background

Modern applications are increasingly composed of multiple independently executing components: web frontends, APIs, background workers, databases, caches, message brokers, and external services. Even relatively small applications can therefore exhibit the failure characteristics of distributed systems.
When a request becomes slow or fails, the visible symptom is often far removed from the underlying cause. A user may receive an HTTP 500 response from an API gateway even though the original failure occurred several service calls earlier. A request may take several seconds to complete even though no individual operation initially appears obviously defective. A service may perform the same database query dozens of times, retry a downstream dependency unnecessarily, or spend most of the request lifetime waiting on another component.

Distributed tracing and observability systems provide the telemetry required to investigate these problems. They can record individual operations as spans, connect spans into traces, associate them with services, and expose timings, errors, attributes, and events.

However, collecting telemetry does not by itself explain system behavior.

The developer is still commonly responsible for manually inspecting the trace, following parent-child relationships, comparing durations, identifying suspicious patterns, correlating errors, and deciding which parts of the execution are relevant.

The result is that observability tools often provide the evidence, while the developer must still perform the **diagnosis**.

## 1.2 The problem
TraceForge addresses the gap between observing a distributed request and understanding why that request behaved the way it did.

Given a trace containing tens or hundreds of spans, a developer should not have to manually answer questions such as:
-	Which operation was primarily responsible for this request's latency?
-	Which sequence of operations formed the effective critical path?
-	Where did an error originate, rather than merely propagate?
-	Did a service perform an unusual number of repeated database queries?
-	Were multiple downstream requests likely retries of the same operation?
-	Which service or dependency contributed most heavily to the observed behaviour?
-	Is the behaviour unusual relative to comparable requests?
-	Is the apparent bottleneck real, or is the span merely waiting for another operation?

Existing telemetry already contains much of the information required to answer these questions. The problem is that this information is represented as low-level execution data rather than as higher-level diagnostic conclusions.
TraceForge exists to perform that **interpretation**.

## 1.3 Product thesis
The central thesis of TraceForge is: 
```text
Distributed telemetry should be analysed, not merely displayed 
```
TraceForge will ingest distributed traces and transform them into a model of request execution that can be inspected both visually and algorithmically.

Instead of treating a trace only as a tree of spans, TraceForge will attempt to identify meaningful execution behaviour within it.

For example, rather than only displaying:
```text
GET /orders 2.81 s 

└── orders-service 2.64 s 
    ├── SELECT product 61 ms 
    ├── SELECT product 58 ms 
    ├── SELECT product 63 ms 
    ├── ... 
    └── SELECT product 59 ms
```

TraceForge should additionally be capable of producing a diagnostic finding such as:
```text
34 structurally similar database operations were executed during this request. 

Combined duration: 2.07 s 
Contribution to trace duration: 73.7% 
Affected service: orders-service
```

The trace remains available for inspection. TraceForge does not hide the underlying telemetry or replace the developer's judgement. Instead, it adds an analysis layer that extracts behaviour from the telemetry and presents the evidence supporting each conclusion.

## 1.4 Why TraceForge Should Exist
TraceForge is not intended to exist because distributed tracing itself is missing. Distributed tracing is already a mature concept, and telemetry collection should use established standards rather than inventing a proprietary alternative.

TraceForge exists because there is a meaningful difference between four stages of observability:
```text
Collection 
    ↓ 
Storage 
    ↓ 
Visualization 
    ↓ 
Interpretation
```
The first three make telemetry accessible.

The fourth makes telemetry useful for diagnosis.

TraceForge will focus primarily on that fourth stage.

Its purpose is therefore not to answer only:

    What happened during this request?

but also: 

    What is significant about what happened?

and, where sufficient evidence exists:

    What most likely caused the observed behaviour?

This distinction defines the project.

A trace waterfall viewer is useful, but it is not sufficient justification for TraceForge to exist. Service graphs, search interfaces, latency charts, and filtering are supporting capabilities. They exist so that developers can inspect and verify the system's interpretation of telemetry.

The primary product capability is **evidence-based automated analysis of distributed request execution**.

## 1.5 Deterministic Diagnosis
TraceForge should prefer deterministic analysis wherever possible.

A diagnostic conclusion must be derived from observable telemetry and accompanied by the evidence that caused it to be generated.

For example:
```text
Finding:
Repeated downstream operation

Evidence:
- 17 client spans
- same originating service
- same normalized destination
- same normalized route
- execution occurred within one trace
- 15 calls occurred sequentially
```

This design allows a developer to understand not only what TraceForge concluded, but also why it reached that conclusion.

This is deliberately different from sending raw telemetry directly to a language model and asking it to diagnose the application.

Language models may later be used to explain, summarize, or contextualize findings, but they must not be required for TraceForge's core diagnostic functionality.

The intended relationship is:
```
Telemetry
    ↓
Deterministic analysis
    ↓
Structured findings
    ↓
Optional natural-language explanation
```
not:
```text
Telemetry
    ↓
Large Language Model
    ↓
Unverifiable diagnosis
```
The underlying analysis must remain usable, reproducible, and testable without an AI component.

## 1.6 Intended Developer Experience
TraceForge should reduce the amount of manual reasoning required to move from a symptom to a plausible area of investigation.

The desired workflow is:
```text
Developer observes unexpected behaviour
        ↓
Opens TraceForge
        ↓
Locates affected trace
        ↓
TraceForge reconstructs request execution
        ↓
Analysis engine evaluates it
        ↓
Developer receives findings + evidence
        ↓
Developer inspects relevant spans
        ↓
Developer investigates code
```
TraceForge does not claim to determine the definitive root cause of every software failure. Runtime telemetry cannot provide enough information to make such a guarantee.

Instead, TraceForge attempts to answer a narrower and more defensible question:

    Given the telemetry available for this request, what execution behaviour is sufficiently unusual or significant that the developer should investigate it?

This principle should govern the design of the analysis engine.

When TraceForge lacks sufficient evidence to support a conclusion, it should report uncertainty or produce no finding rather than fabricate one.

## 1.7 Initial Problem Boundary
The initial version of TraceForge will focus on request-level analysis of small distributed applications.

The primary environment is expected to contain approximately several to several dozen services running locally, in development, or in small staging environments.

The initial problem domain includes:
```text 
- distributed HTTP request tracing;
- service-to-service calls;
- database spans;
- latency analysis;
- error propagation;
- repeated-operation detection;
- service dependency reconstruction;
- trace-level diagnostic findings.
```
The initial problem domain **does not include** attempting to become a complete replacement for a commercial observability platform.

TraceForge does not initially need to provide:

- enterprise-scale telemetry retention;
- infrastructure monitoring;
- business analytics;
- security information and event management;
- full log analytics;
- full metrics monitoring;
- alert management;
- incident-response workflow management;
- multi-tenant SaaS functionality.


These capabilities may interact with TraceForge in the future, but they are not part of the reason the project exists.

## 1.8 Core Product Principle
The defining principle of TraceForge is:

    Do not merely show developers more telemetry. Reduce the amount of telemetry they have to understand manually.
Every major product feature should ultimately support this objective.

If TraceForge only reproduces functionality already provided by conventional trace viewers, the project has failed to establish a meaningful reason to exist.

If TraceForge can take a complex distributed trace and reliably direct a developer toward the small subset of execution behaviour that deserves investigation, then it has achieved its central purpose.

