import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.trace.v1.trace_pb2 import Span

from traceforge.critical_path import calculate
from traceforge.ingestion.otlp import ingest_export_request
from traceforge.traces import get_trace

router = APIRouter()


def debug_enabled():
    return os.environ.get("TRACEFORGE_DEBUG_UI", "").lower() == "true"


def require_debug():
    if not debug_enabled():
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/debug")
def debug_page():
    require_debug()
    return HTMLResponse("""<!doctype html>
<title>TraceForge Debug</title>
<h1>TraceForge Debug</h1>
<button onclick="generate('normal')">Generate normal trace</button>
<button onclick="generate('repeated-db')">Generate repeated-database trace</button>
<button onclick="generate('critical-path')">Generate critical-path trace</button>
<p id="status"></p><pre id="trace"></pre><div id="critical-path"></div><div id="findings"></div><table id="spans"></table>
<details><summary>Raw JSON</summary><pre id="raw"></pre></details>
<script>
const status = document.querySelector('#status'), trace = document.querySelector('#trace');
const findings = document.querySelector('#findings'), spans = document.querySelector('#spans');
const criticalPath = document.querySelector('#critical-path');
const raw = document.querySelector('#raw');
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
function render(data) {
  const item = data.trace;
  trace.textContent = `Trace: ${item.trace_id}\nRevision: ${item.revision}\nCompleteness: ${item.completeness_state}\nAnalysis: ${item.analysis_state}\nSpans: ${item.span_count}\nServices: ${item.services.length}`;
  const list = data.analysis.current_run?.findings ?? [];
  findings.innerHTML = list.length ? list.map(finding => `<h2>${escape(finding.type)}</h2><p>${escape(finding.severity)} / ${escape(finding.confidence)} — ${escape(finding.summary)}</p><pre>${escape(JSON.stringify(finding.structured_data, null, 2))}</pre>`).join('') : '<p>No findings.</p>';
  spans.innerHTML = '<tr><th>Name</th><th>Service</th><th>Kind</th><th>Duration</th><th>Parent</th></tr>' + data.spans.map(span => `<tr><td>${escape(span.name)}</td><td>${escape(span.service?.name)}</td><td>${escape(span.span_kind)}</td><td>${escape(span.duration_ns)}</td><td>${escape(span.parent_span_id)}</td></tr>`).join('');
  raw.textContent = JSON.stringify(data, null, 2);
}
function renderCriticalPath(result) {
  if (result.state !== 'AVAILABLE') {
    criticalPath.innerHTML = `<h2>Critical path</h2><p>Unavailable: ${escape(result.reason)}</p>`;
    return;
  }
  criticalPath.innerHTML = `<h2>Critical path (${escape(result.duration_ns)} ns)</h2><table><tr><th>Span</th><th>Start</th><th>End</th><th>Contribution</th></tr>${result.segments.map(segment => `<tr><td>${escape(segment.span_id)}</td><td>${escape(segment.start_time_unix_ns)}</td><td>${escape(segment.end_time_unix_ns)}</td><td>${escape(segment.contribution_ns)}</td></tr>`).join('')}</table>`;
}
async function generate(scenario) {
  status.textContent = 'Generating trace...';
  const created = await fetch(`/debug/generate/${scenario}`, {method: 'POST'}).then(response => response.json());
  const deadline = Date.now() + 12000;
  async function poll() {
    const data = await fetch(`/api/v1/traces/${created.trace_id}`).then(response => response.json());
    render(data);
    const complete = data.trace.completeness_state !== 'PROCESSING';
    const analyzed = ['COMPLETE', 'PARTIAL', 'FAILED'].includes(data.analysis.state);
    if (complete && analyzed) {
      renderCriticalPath(await fetch(`/debug/critical-path/${created.trace_id}`).then(response => response.json()));
      status.textContent = 'Complete.';
      return;
    }
    if (Date.now() >= deadline) { status.textContent = 'Timed out; showing the latest known state.'; return; }
    status.textContent = 'Waiting for lifecycle and analysis...';
    setTimeout(poll, 500);
  }
  poll();
}
</script>""")


def normal_request(trace_id):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add().resource
    resource.attributes.add(key="service.name").value.string_value = "debug-orders"
    scope = request.resource_spans[0].scope_spans.add()
    root = scope.spans.add()
    root.trace_id = trace_id
    root.span_id = (1).to_bytes(8, "big")
    root.name = "debug request"
    root.kind = Span.SPAN_KIND_SERVER
    root.start_time_unix_nano = 0
    root.end_time_unix_nano = 100
    child = scope.spans.add()
    child.trace_id = trace_id
    child.span_id = (2).to_bytes(8, "big")
    child.parent_span_id = root.span_id
    child.name = "debug work"
    child.kind = Span.SPAN_KIND_INTERNAL
    child.start_time_unix_nano = 10
    child.end_time_unix_nano = 90
    return request


def repeated_database_request(trace_id):
    request = normal_request(trace_id)
    scope = request.resource_spans[0].scope_spans[0]
    for index in range(5):
        span = scope.spans.add()
        span.trace_id = trace_id
        span.span_id = (index + 3).to_bytes(8, "big")
        span.parent_span_id = (1).to_bytes(8, "big")
        span.name = "SELECT product"
        span.kind = Span.SPAN_KIND_CLIENT
        span.start_time_unix_nano = index * 10
        span.end_time_unix_nano = index * 10 + 5
        span.attributes.add(key="db.system.name").value.string_value = "postgresql"
        span.attributes.add(key="db.query.text").value.string_value = (
            f"SELECT name FROM product WHERE id = {index}"
        )
    return request


def critical_path_request(trace_id):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add().resource
    resource.attributes.add(key="service.name").value.string_value = "debug-critical-path"
    scope = request.resource_spans[0].scope_spans.add()
    for span_id, name, parent_span_id, start, end in [
        (1, "request", None, 0, 1000),
        (2, "branch A", 1, 100, 700),
        (3, "branch B", 1, 200, 900),
    ]:
        span = scope.spans.add()
        span.trace_id = trace_id
        span.span_id = span_id.to_bytes(8, "big")
        if parent_span_id is not None:
            span.parent_span_id = parent_span_id.to_bytes(8, "big")
        span.name = name
        span.kind = Span.SPAN_KIND_INTERNAL
        span.start_time_unix_nano = start
        span.end_time_unix_nano = end
    return request


@router.post("/debug/generate/normal")
def generate_normal_trace():
    require_debug()
    trace_id = uuid4().bytes
    ingest_export_request(normal_request(trace_id))
    return {"trace_id": trace_id.hex()}


@router.post("/debug/generate/repeated-db")
def generate_repeated_database_trace():
    require_debug()
    trace_id = uuid4().bytes
    ingest_export_request(repeated_database_request(trace_id))
    return {"trace_id": trace_id.hex()}


@router.post("/debug/generate/critical-path")
def generate_critical_path_trace():
    require_debug()
    trace_id = uuid4().bytes
    ingest_export_request(critical_path_request(trace_id))
    return {"trace_id": trace_id.hex()}


@router.get("/debug/critical-path/{trace_id}")
def critical_path(trace_id: str):
    require_debug()
    detail = get_trace(trace_id)
    if not isinstance(detail, dict):
        return detail
    result = calculate(
        detail["trace"],
        [
            {
                "span_id": bytes.fromhex(span["span_id"]),
                "parent_span_id": (
                    bytes.fromhex(span["parent_span_id"]) if span["parent_span_id"] else None
                ),
                "start_time_unix_ns": span["start_time_unix_ns"],
                "end_time_unix_ns": span["end_time_unix_ns"],
            }
            for span in detail["spans"]
        ],
    )
    for segment in result["segments"]:
        segment["span_id"] = segment["span_id"].hex()
    return result
