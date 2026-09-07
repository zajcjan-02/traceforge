# 2. Target users
## 2.1 Primary target users
TraceForge is primarily designed for **software developers working on small to medium-sized distributed applications who need to understand the runtime behaviour of requests across multiple services**.

The primary user is technically capable of instrumenting an application with OpenTelemetry and understands basic concepts such as HTTP requests, databases, services, latency, and exceptions. However, the user should not need specialist knowledge of observability platforms or distributed tracing internals in order to obtain useful diagnostic information from TraceForge.

A typical primary user may be developing an application containing:
```text
- several backend services;
- one or more databases;
- external API dependencies;
- background workers;
- caches or message brokers;
- a frontend or API gateway;
- Docker-based local or staging infrastructure.
```
The application may consist of only a few services or several dozen. At this scale, distributed-system behaviour is already sufficiently complex to make debugging difficult, while enterprise observability infrastructure may be unnecessarily expensive or operationally heavy.

TraceForge should therefore optimize for a developer who wants to move from:

    This request is slow.

to:

    These operations account for most of the latency, and this repeated behaviour is likely worth investigating.

without requiring extensive manual trace analysis.
<hr>


## 2.2 Primary User Persona
A representative primary user can be described as follows:
### Application Developer
The Application Developer builds and maintains distributed backend or full-stack applications.

They are comfortable working with:

- application source code;
- REST or similar service APIs;
- relational databases;
- Docker;
- basic infrastructure configuration;
- application logs;
- performance debugging.

They may have used conventional logging and monitoring tools but are not necessarily an observability specialist.

```text 
Client 
↓ 
API Gateway 
↓ 
Orders Service  
    ├── Authentication Service 
    ├── Product Service 
    │   └── PostgreSQL 
    └── Payment Service         
        └── External API
```

A user-facing request fails after 2.8 seconds.

The Application Developer wants to determine:

- which component caused the failure;
- which operations consumed the request lifetime;
- whether an error originated locally or downstream;
- whether unexpected repeated work occurred;
- which source code or service should be investigated first.

Without TraceForge, this process may involve searching multiple logs, inspecting a trace manually, comparing timestamps, and reasoning about relationships between operations.

With TraceForge, the desired experience is that the most diagnostically significant behaviour is identified automatically and linked back to the underlying telemetry.

<hr>

## 2.3 Secondary Target Users
TraceForge may also provide value to several related groups, although their requirements should not override those of the primary user during the initial design.

### Backend Engineers
Backend engineers working primarily on service-side systems are a natural secondary audience.

They may use TraceForge to investigate:

- slow API endpoints;
- database behaviour;
-  downstream service latency;
- retry behaviour;
- error propagation;
- inefficient service interactions

For these users, the analysis engine and detailed trace inspection are likely more important than high-level visualization.

### Small Platform or DevOps Teams

Small platform teams may use TraceForge as a lightweight diagnostic tool for development and staging environments.

Their interests may include:

- identifying unhealthy service dependencies;
- understanding cross-service latency;
- verifying instrumentation;
- observing application architecture from runtime behaviour;
- helping application developers diagnose incidents.

TraceForge is not initially intended to replace enterprise observability infrastructure used by these teams.

### Students and Developers Learning Distributed Systems

TraceForge may also serve an educational role.

A developer learning distributed systems can observe how application architecture translates into runtime execution.

For example, they can intentionally introduce:

- N+1 database queries;
- slow downstream services;
- retry storms;
- cascading errors;
- sequential operations that could execute concurrently.

TraceForge can then expose these behaviours through real telemetry.

This is a useful secondary property of the product, but TraceForge should not be designed primarily as an educational tool.

<hr>

## 2.4 Expected Technical Knowledge
TraceForge should not assume that its users are observability specialists.

A user should reasonably be expected to understand:

- what an application service is;
- HTTP requests and responses;
- basic database operations;
- application latency;
- exceptions and failures;
- basic Docker usage.

Knowledge of the following should be helpful but not required:

- OpenTelemetry internals;
- span kinds;
- trace context propagation;
- baggage;
- sampling strategies;
- collector pipelines;
- distributed tracing storage architecture.

TraceForge should expose advanced telemetry details when useful without requiring the user to understand them before obtaining useful diagnostic information.

The system should therefore progressively expose complexity.

A developer should first be able to see:

    orders-service is responsible for most observed latency.

and then, if desired, inspect:

    Span ID
    Parent Span ID
    Span Kind
    Attributes
    Events
    Resource Attributes
    Instrumentation Scope
    Status

The diagnostic result should be understandable before the implementation details of OpenTelemetry are.

<hr>

## 2.5 Target Environment
The initial TraceForge user is expected to operate primarily in one of three environments:

1. local development;
2. shared development environments;
3. small staging environments.

Docker Compose should represent the primary deployment environment for the first version.

A representative environment may contain approximately:

    3–20 application services
    1–5 supporting infrastructure components
    hundreds to thousands of requests during a development session

These numbers represent a design target rather than strict limits.

TraceForge should not contain architectural decisions that make moderate growth impossible, but the initial implementation should not be optimized for enterprise telemetry volumes at the cost of unnecessary complexity.

<hr>


## 2.6 User Motivations

The primary motivation for using TraceForge is **reducing debugging effort**.

Users are not expected to deploy TraceForge because they want another place to look at traces.

They should deploy it because they want help answering questions about application behaviour.

Major motivations include:

### Faster identification of relevant behaviour

A complex trace may contain dozens or hundreds of spans.

The user wants TraceForge to identify which subset deserves attention.

### Reduction of manual correlation

The user should not have to manually reconstruct service relationships, calculate latency contributions, or follow propagated errors wherever this information can be derived reliably.

### Evidence-backed diagnosis

The user wants diagnostic conclusions that can be verified against the underlying trace.

TraceForge should therefore show both:

    Conclusion

and:

    Evidence supporting the conclusion

<hr>

## 2.7 Users TraceForge Is Not Initially Designed For

Explicitly defining non-target users is necessary to prevent requirements from being introduced for scenarios outside the intended product scope.

### Large Enterprise Observability Teams

TraceForge v0.1 is not designed for organizations operating:
- hundreds or thousands of services;
- millions of spans per second;
- geographically distributed telemetry clusters;
- multi-year telemetry retention;
- strict multi-tenant isolation.

Supporting these requirements would significantly change the storage, ingestion, deployment, security, and operational architecture.

### Security Operations Teams

TraceForge is not initially a SIEM, threat-detection system, or security monitoring platform.

Security-related telemetry may pass through the system, but cybersecurity analysis is outside the initial product scope.

### Business Analytics Users

TraceForge is intended to analyze technical application execution.

It is not designed primarily for:
- product analytics;
- conversion tracking;
- customer behaviour;
- business intelligence.

### Non-Technical End Users

TraceForge is a developer tool.

Its interface does not need to hide technical concepts such as services, database queries, spans, HTTP routes, or exception types.

Usability remains important, but technical precision should not be sacrificed in an attempt to make the product understandable to users with no software-development background.

## 2.8 Design Implications

The target user definition creates several direct product constraints.

### TraceForge must be easy to deploy

The initial user should not need Kubernetes or a complex distributed installation.

### TraceForge must work well at relatively small scale

Useful analysis should not depend on enormous historical datasets.

Many findings should be possible from a single trace or a relatively small collection of comparable traces.

### TraceForge must explain its findings

The target user is a developer capable of validating technical evidence.

TraceForge should therefore expose the telemetry responsible for each conclusion.

### TraceForge must preserve access to raw detail

Automated diagnosis should accelerate investigation, not prevent deeper investigation.

The developer must always be able to inspect the spans behind a finding.

### TraceForge must avoid unnecessary enterprise complexity

Features such as multi-tenancy, billing, organizational permission hierarchies, geographically replicated storage, and enterprise identity integration should not influence the v0.1 architecture unless they are required to avoid a significant future dead end.

<hr>

## 2.9 Primary User Definition

For the purposes of all subsequent design decisions, the default TraceForge user will be:

```text
A software developer debugging a small distributed application in a local, development, or staging environment who wants automated, evidence-backed analysis of distributed request behaviour without operating a full enterprise observability platform.
```

When competing requirements arise, the option that better serves this user should normally take priority unless an explicit architectural reason justifies otherwise.