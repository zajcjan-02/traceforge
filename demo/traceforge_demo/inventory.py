import time

from fastapi import FastAPI

from traceforge_demo.telemetry import configure

app = FastAPI(title="TraceForge demo inventory")
tracer = configure(app, "demo-inventory")


@app.get("/demo/normal")
def normal():
    return {"inventory": "available"}


@app.get("/demo/product/{product_id}")
def product(product_id: int):
    return {"product_id": product_id}


@app.get("/demo/work")
def work(delay_ms: int = 0):
    time.sleep(delay_ms / 1000)
    return {"status": "ok"}
