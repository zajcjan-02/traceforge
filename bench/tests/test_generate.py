from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from traceforge_bench.generate import Workload, batches, manifest, trace_id


def workload():
    return Workload("test-run", 3, 4, 2, 2, 1, None, "normal", 1_000_000)


def test_generator_has_deterministic_trace_counts_and_timing():
    current = workload()
    encoded = list(batches(current))
    assert sum(len(indexes) for indexes, _ in encoded) == 3
    assert manifest(current)["expected_spans"] == 12

    request = ExportTraceServiceRequest()
    request.ParseFromString(encoded[0][1])
    spans = [span for resource in request.resource_spans for scope in resource.scope_spans for span in scope.spans]
    assert len(spans) == 8
    roots = [span for span in spans if not span.parent_span_id]
    assert len(roots) == 2
    assert roots[1].start_time_unix_nano > roots[0].start_time_unix_nano
    assert all(span.end_time_unix_nano >= span.start_time_unix_nano for span in spans)
    assert trace_id(current, 0) != trace_id(current, 1)


def test_generator_assigns_services_and_optional_database_operations():
    current = Workload("test-db", 1, 9, 3, 1, 1, None, "mixed-findings", 1_000_000)
    _, payload = next(batches(current))
    request = ExportTraceServiceRequest()
    request.ParseFromString(payload)
    services = {attribute.value.string_value for resource in request.resource_spans for attribute in resource.resource.attributes}
    spans = [span for resource in request.resource_spans for scope in resource.scope_spans for span in scope.spans]
    assert services == {"benchmark-service-0", "benchmark-service-1", "benchmark-service-2"}
    assert sum(any(attribute.key == "db.query.text" for attribute in span.attributes) for span in spans) == 5
