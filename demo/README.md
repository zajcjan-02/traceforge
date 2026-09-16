# TraceForge demo application

This profile-gated FastAPI application is an ordinary distributed OpenTelemetry
example. It does not import or call TraceForge internals.

Start it with the TraceForge stack:

```sh
docker compose --profile demo up --build
```

Call the gateway at `http://127.0.0.1:8010`:

```sh
curl http://127.0.0.1:8010/demo/normal
curl http://127.0.0.1:8010/demo/repeated-db
curl http://127.0.0.1:8010/demo/slow-payment
curl http://127.0.0.1:8010/demo/error
curl http://127.0.0.1:8010/demo/repeated-downstream
curl http://127.0.0.1:8010/demo/concurrent
```

The repeated-database scenario executes real SQLite queries. Its database spans
are manually created with standard OpenTelemetry DB semantic attributes because
SQLite auto-instrumentation does not reliably expose the stable query fields
needed by TraceForge's conservative detector. The repeated-downstream scenario
adds the standard `url.template` client attribute because a generic HTTP client
cannot infer a low-cardinality route template from a concrete URL.

Each `/demo/*` request writes a concise Markdown report under `demo/reports/`
when run through Docker Compose. Reports include the service, request path, and
HTTP result; generated reports are intentionally not tracked by Git.
