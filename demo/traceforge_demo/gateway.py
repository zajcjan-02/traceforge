import os

from fastapi import FastAPI

from traceforge_demo.telemetry import configure, get

app = FastAPI(title="TraceForge demo gateway")
tracer = configure(app, "demo-gateway")
orders_url = os.environ.get("ORDERS_URL", "http://demo-orders:8011")


def orders(scenario):
    return get(f"{orders_url}/demo/{scenario}", f"/demo/{scenario}", tracer)


@app.get("/demo/normal")
def normal():
    return orders("normal").json()


@app.get("/demo/repeated-db")
def repeated_database():
    return orders("repeated-db").json()


@app.get("/demo/slow-payment")
def slow_payment():
    return orders("slow-payment").json()


@app.get("/demo/error")
def propagated_error():
    response = orders("error")
    response.raise_for_status()
    return response.json()


@app.get("/demo/repeated-downstream")
def repeated_downstream():
    return orders("repeated-downstream").json()


@app.get("/demo/concurrent")
def concurrent():
    return orders("concurrent").json()
