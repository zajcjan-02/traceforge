import contextvars
import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI

from traceforge_demo.telemetry import configure, get

app = FastAPI(title="TraceForge demo orders")
tracer = configure(app, "demo-orders")
inventory_url = os.environ.get("INVENTORY_URL", "http://demo-inventory:8012")
payment_url = os.environ.get("PAYMENT_URL", "http://demo-payment:8013")


def call_inventory(path, template):
    return get(f"{inventory_url}{path}", template, tracer)


def call_payment(path, template):
    return get(f"{payment_url}{path}", template, tracer)


@app.get("/demo/normal")
def normal():
    call_inventory("/demo/normal", "/demo/normal").raise_for_status()
    call_payment("/demo/normal", "/demo/normal").raise_for_status()
    return {"status": "ok"}


@app.get("/demo/repeated-db")
def repeated_database():
    call_payment("/demo/repeated-db", "/demo/repeated-db").raise_for_status()
    return {"status": "ok"}


@app.get("/demo/slow-payment")
def slow_payment():
    call_payment("/demo/slow-payment", "/demo/slow-payment").raise_for_status()
    return {"status": "ok"}


@app.get("/demo/error")
def propagated_error():
    response = call_payment("/demo/error", "/demo/error")
    response.raise_for_status()
    return response.json()


@app.get("/demo/repeated-downstream")
def repeated_downstream():
    for product_id in range(5):
        call_inventory(f"/demo/product/{product_id}", "/demo/product/{id}").raise_for_status()
    return {"status": "ok"}


@app.get("/demo/concurrent")
def concurrent():
    calls = [
        (call_inventory, "/demo/work?delay_ms=200", "/demo/work"),
        (call_payment, "/demo/work?delay_ms=200", "/demo/work"),
    ]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(contextvars.copy_context().run, call, path, template)
            for call, path, template in calls
        ]
        for future in futures:
            future.result().raise_for_status()
    return {"status": "ok"}
