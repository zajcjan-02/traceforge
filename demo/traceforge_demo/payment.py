import sqlite3
import time

from fastapi import FastAPI
from opentelemetry.trace import SpanKind, Status, StatusCode

from traceforge_demo.telemetry import configure

app = FastAPI(title="TraceForge demo payment")
tracer = configure(app, "demo-payment")


def database():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE product (id INTEGER PRIMARY KEY, name TEXT)")
    connection.executemany("INSERT INTO product VALUES (?, ?)", [(index, f"product-{index}") for index in range(5)])
    return connection


@app.get("/demo/normal")
def normal():
    return {"payment": "accepted"}


@app.get("/demo/repeated-db")
def repeated_database():
    connection = database()
    for product_id in range(5):
        query = f"SELECT name FROM product WHERE id = {product_id}"
        with tracer.start_as_current_span("SELECT product", kind=SpanKind.CLIENT) as span:
            span.set_attribute("db.system.name", "sqlite")
            span.set_attribute("db.namespace", "demo")
            span.set_attribute("db.query.text", query)
            connection.execute(query).fetchone()
    connection.close()
    return {"status": "ok"}


@app.get("/demo/slow-payment")
def slow_payment():
    time.sleep(0.5)
    return {"status": "ok"}


@app.get("/demo/work")
def work(delay_ms: int = 0):
    time.sleep(delay_ms / 1000)
    return {"status": "ok"}


@app.get("/demo/error")
def propagated_error():
    with tracer.start_as_current_span("database operation", kind=SpanKind.CLIENT) as span:
        try:
            raise RuntimeError("demo payment database failure")
        except RuntimeError as error:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise
