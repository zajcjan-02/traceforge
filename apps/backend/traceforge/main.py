from fastapi import FastAPI

from traceforge.ingestion.otlp import router as otlp_router

app = FastAPI()
app.include_router(otlp_router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    return {"status": "ok"}
