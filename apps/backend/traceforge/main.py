from fastapi import FastAPI
from fastapi.responses import JSONResponse

from traceforge.database import database_ready
from traceforge.ingestion.otlp import router as otlp_router
from traceforge.traces import router as traces_router

app = FastAPI()
app.include_router(otlp_router)
app.include_router(traces_router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    if not database_ready():
        return JSONResponse(status_code=503, content={"status": "unavailable"})

    return {"status": "ok"}
