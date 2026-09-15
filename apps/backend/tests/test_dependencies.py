from datetime import timedelta

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from sqlalchemy import func, select, update

from traceforge.database import engine
from traceforge.lifecycle import evaluate_expired_traces
from traceforge.main import app
from traceforge.models import service_dependency_observations, services, traces

client = TestClient(app)


def request(trace_id, definitions):
    export_request = ExportTraceServiceRequest()
    for service, span_id, parent_span_id, start, end in definitions:
        resource = export_request.resource_spans.add().resource
        if service is not None:
            resource.attributes.add(key="service.name").value.string_value = service
        span = export_request.resource_spans[-1].scope_spans.add().spans.add()
        span.trace_id = bytes.fromhex(trace_id)
        span.span_id = span_id.to_bytes(8, "big")
        if parent_span_id is not None:
            span.parent_span_id = parent_span_id.to_bytes(8, "big")
        span.name = service or "unknown"
        span.kind = Span.SPAN_KIND_SERVER
        span.start_time_unix_nano = start
        span.end_time_unix_nano = end
    return export_request


def send(export_request):
    response = client.post(
        "/v1/traces",
        content=export_request.SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200


def finalize(trace_id):
    with engine.begin() as connection:
        connection.execute(
            update(traces)
            .where(traces.c.trace_id == bytes.fromhex(trace_id))
            .values(completion_deadline=func.now() - timedelta(seconds=1))
        )
    evaluate_expired_traces()


def service_id(name):
    with engine.connect() as connection:
        return connection.execute(
            select(services.c.service_id).where(services.c.service_name == name)
        ).scalar_one()


def test_multihop_and_siblings_create_only_direct_edges():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(
        request(
            trace_id,
            [
                ("gateway", 1, None, 0, 400),
                ("orders", 2, 1, 10, 350),
                ("inventory", 3, 2, 20, 200),
                ("payment", 4, 2, 30, 300),
            ],
        )
    )
    finalize(trace_id)

    gateway = client.get(f"/api/v1/services/{service_id('gateway')}/dependencies").json()
    orders = client.get(f"/api/v1/services/{service_id('orders')}/dependencies").json()

    assert [(row["target_service"]["name"], row["first_seen_at"]) for row in gateway["outgoing"]] == [("orders", "10")]
    assert [(row["target_service"]["name"], row["first_seen_at"]) for row in orders["outgoing"]] == [
        ("inventory", "20"),
        ("payment", "30"),
    ]
    assert not gateway["incoming"]


def test_service_list_and_detail_include_stored_trace():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request(trace_id, [("gateway", 1, None, 0, 100), ("orders", 2, 1, 10, 90)]))
    finalize(trace_id)

    listed = client.get("/api/v1/services")
    assert listed.status_code == 200
    orders = next(item for item in listed.json()["items"] if item["name"] == "orders")
    assert orders["trace_count"] == 1

    detail = client.get(f"/api/v1/services/{orders['service_id']}")
    assert detail.status_code == 200
    assert detail.json()["service"]["name"] == "orders"
    assert [item["trace_id"] for item in detail.json()["recent_traces"]] == [trace_id]


def test_same_service_missing_service_and_missing_parent_create_no_edges():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(
        request(
            trace_id,
            [
                ("orders", 1, None, 0, 400),
                ("orders", 2, 1, 10, 100),
                (None, 3, 1, 20, 100),
                ("payment", 4, 9, 30, 100),
            ],
        )
    )
    finalize(trace_id)

    with engine.connect() as connection:
        assert connection.execute(select(service_dependency_observations)).mappings().all() == []


def test_repeated_edge_in_one_trace_and_duplicate_ingestion_count_once():
    trace_id = "0123456789abcdef0123456789abcdef"
    export_request = request(
        trace_id,
        [
            ("orders", 1, None, 0, 400),
            ("payment", 2, 1, 40, 100),
            ("payment", 3, 1, 20, 120),
        ],
    )
    send(export_request)
    send(export_request)
    finalize(trace_id)

    with engine.connect() as connection:
        rows = connection.execute(select(service_dependency_observations)).mappings().all()

    assert len(rows) == 1
    assert rows[0]["observed_at"] == 20


def test_multiple_traces_aggregate_and_late_revision_replaces_observations():
    trace_ids = [
        "0123456789abcdef0123456789abcdef",
        "1123456789abcdef0123456789abcdef",
        "2123456789abcdef0123456789abcdef",
    ]
    for trace_id, start in zip(trace_ids, [100, 200, 300]):
        send(request(trace_id, [("orders", 1, None, 0, 400), ("payment", 2, 1, start, 350)]))
        finalize(trace_id)

    response = client.get(f"/api/v1/services/{service_id('orders')}/dependencies").json()
    dependency = response["outgoing"][0]
    assert dependency["observation_count"] == 3
    assert dependency["first_seen_at"] == "100"
    assert dependency["last_seen_at"] == "300"

    trace_id = trace_ids[0]
    send(request(trace_id, [("inventory", 3, 1, 50, 250)]))
    finalize(trace_id)

    response = client.get(f"/api/v1/services/{service_id('orders')}/dependencies").json()
    dependencies = {row["target_service"]["name"]: row for row in response["outgoing"]}
    assert dependencies["payment"]["observation_count"] == 3
    assert dependencies["payment"]["first_seen_at"] == "100"
    assert dependencies["inventory"]["observation_count"] == 1
    assert dependencies["inventory"]["first_seen_at"] == "50"

    with engine.connect() as connection:
        rows = connection.execute(
            select(service_dependency_observations).where(
                service_dependency_observations.c.trace_id == bytes.fromhex(trace_id)
            )
        ).mappings().all()
    assert len(rows) == 2
    assert {row["trace_revision"] for row in rows} == {3}


def test_dependencies_api_returns_incoming_and_404():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request(trace_id, [("gateway", 1, None, 0, 400), ("orders", 2, 1, 10, 300)]))
    finalize(trace_id)

    response = client.get(f"/api/v1/services/{service_id('orders')}/dependencies")

    assert response.json()["incoming"][0]["source_service"]["name"] == "gateway"
    assert client.get("/api/v1/services/99999/dependencies").status_code == 404
