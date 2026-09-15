import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from traceforge_demo import gateway, inventory, orders, payment, telemetry


class Response:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def json(self):
        return {"status": "ok"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_normal_endpoints_succeed(monkeypatch):
    monkeypatch.setattr(gateway, "orders", lambda scenario: Response())
    monkeypatch.setattr(orders, "call_inventory", lambda path, template: Response())
    monkeypatch.setattr(orders, "call_payment", lambda path, template: Response())

    assert TestClient(gateway.app).get("/demo/normal").status_code == 200
    assert TestClient(orders.app).get("/demo/normal").status_code == 200
    assert TestClient(inventory.app).get("/demo/normal").status_code == 200
    assert TestClient(payment.app).get("/demo/normal").status_code == 200


def test_demo_endpoint_creates_a_report(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_REPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(gateway, "orders", lambda scenario: Response())

    assert TestClient(gateway.app).get("/demo/normal").status_code == 200

    reports = list(tmp_path.glob("*-demo-normal.md"))
    assert len(reports) == 1
    assert "Service: demo-gateway" in reports[0].read_text()
    assert "Status: 200" in reports[0].read_text()


def test_repeated_database_executes_five_queries(monkeypatch):
    queries = []
    original = sqlite3.connect

    class Connection:
        def __init__(self):
            self.connection = original(":memory:")

        def execute(self, query):
            if query.startswith("SELECT"):
                queries.append(query)
            return self.connection.execute(query)

        def executemany(self, query, values):
            return self.connection.executemany(query, values)

        def close(self):
            self.connection.close()

    monkeypatch.setattr(payment.sqlite3, "connect", lambda _: Connection())
    assert TestClient(payment.app).get("/demo/repeated-db").status_code == 200
    assert len(queries) == 5


def test_propagated_error_returns_a_server_error(monkeypatch):
    monkeypatch.setattr(gateway, "orders", lambda scenario: Response(500))
    monkeypatch.setattr(orders, "call_payment", lambda path, template: Response(500))

    assert TestClient(gateway.app, raise_server_exceptions=False).get("/demo/error").status_code == 500
    assert TestClient(orders.app, raise_server_exceptions=False).get("/demo/error").status_code == 500
    assert TestClient(payment.app, raise_server_exceptions=False).get("/demo/error").status_code == 500


def test_repeated_downstream_makes_five_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(orders, "call_inventory", lambda path, template: calls.append((path, template)) or Response())

    assert TestClient(orders.app).get("/demo/repeated-downstream").status_code == 200
    assert calls == [(f"/demo/product/{index}", "/demo/product/{id}") for index in range(5)]


def test_concurrent_calls_overlap(monkeypatch):
    active = 0
    maximum = 0
    lock = threading.Lock()
    both_started = threading.Event()

    def call(path, template):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                both_started.set()
        both_started.wait(1)
        with lock:
            active -= 1
        return Response()

    monkeypatch.setattr(orders, "call_inventory", call)
    monkeypatch.setattr(orders, "call_payment", call)

    assert TestClient(orders.app).get("/demo/concurrent").status_code == 200
    assert maximum == 2


def test_client_call_propagates_trace_context(monkeypatch):
    captured_headers = {}

    class Requests:
        status_code = 200

    def fake_get(url, headers: dict, timeout):
        captured_headers.update(headers)
        return Requests()

    monkeypatch.setattr(telemetry.requests, "get", fake_get)
    tracer = telemetry.configure(FastAPI(), "demo-test")
    with tracer.start_as_current_span("request"):
        telemetry.get("http://inventory:8012/demo/normal", "/demo/normal", tracer)

    assert "traceparent" in captured_headers


def test_demo_configuration_uses_expected_service_names_and_otlp_environment():
    assert [
        gateway.tracer.resource.attributes["service.name"],
        orders.tracer.resource.attributes["service.name"],
        inventory.tracer.resource.attributes["service.name"],
        payment.tracer.resource.attributes["service.name"],
    ] == ["demo-gateway", "demo-orders", "demo-inventory", "demo-payment"]
    assert "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT" in Path(telemetry.__file__).read_text()


def test_demo_code_has_no_traceforge_internal_imports():
    source = "\n".join(path.read_text() for path in Path("traceforge_demo").glob("*.py"))

    assert "from traceforge." not in source
    assert "import traceforge." not in source
