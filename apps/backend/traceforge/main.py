import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from traceforge.database import database_ready
from traceforge.debug import router as debug_router
from traceforge.ingestion.otlp import router as otlp_router
from traceforge.lifecycle import run_lifecycle_sweep
from traceforge.retention import run_retention_sweep, validate_retention_config
from traceforge.traces import router as traces_router


@asynccontextmanager
async def lifespan(app):
    validate_retention_config()
    lifecycle_task = asyncio.create_task(run_lifecycle_sweep())
    retention_task = asyncio.create_task(run_retention_sweep())
    yield
    lifecycle_task.cancel()
    retention_task.cancel()
    with suppress(asyncio.CancelledError):
        await lifecycle_task
    with suppress(asyncio.CancelledError):
        await retention_task


app = FastAPI(lifespan=lifespan)
app.include_router(otlp_router)
app.include_router(traces_router)
app.include_router(debug_router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    if not database_ready():
        return JSONResponse(status_code=503, content={"status": "unavailable"})

    return {"status": "ok"}
