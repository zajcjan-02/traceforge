import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import SpanKind


def configure(app, service_name):
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if not os.environ.get("TRACEFORGE_DEMO_TESTING"):
        exporter = OTLPSpanExporter(
            endpoint=os.environ.get(
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                "http://otel-collector:4318/v1/traces",
            )
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    @app.middleware("http")
    async def report_demo_request(request, call_next):
        if not request.url.path.startswith("/demo/"):
            return await call_next(request)
        try:
            response = await call_next(request)
        except Exception as error:
            write_report(service_name, request.method, request.url.path, 500, str(error))
            raise
        write_report(service_name, request.method, request.url.path, response.status_code)
        return response

    return provider.get_tracer(service_name)


def get(url, template, tracer):
    target = urlsplit(url)
    with tracer.start_as_current_span(f"GET {template}", kind=SpanKind.CLIENT) as span:
        span.set_attribute("http.request.method", "GET")
        span.set_attribute("url.template", template)
        span.set_attribute("server.address", target.hostname or "")
        if target.port:
            span.set_attribute("server.port", target.port)
        headers = {}
        propagate.inject(headers)
        response = requests.get(url, headers=headers, timeout=5)
        span.set_attribute("http.response.status_code", response.status_code)
        return response


def write_report(service_name, method, path, status_code, error=None):
    directory = Path(os.environ.get("DEMO_REPORTS_DIR", "reports"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    endpoint = path.strip("/").replace("/", "-")
    lines = [
        "# Demo request report",
        "",
        f"- Time: {datetime.now(timezone.utc).isoformat()}",
        f"- Service: {service_name}",
        f"- Request: {method} {path}",
        f"- Status: {status_code}",
    ]
    if error:
        lines.append(f"- Error: {error}")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{timestamp}-{endpoint}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
