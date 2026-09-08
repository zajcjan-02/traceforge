import logging

from fastapi import APIRouter, HTTPException, Request, Response
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/v1/traces")
async def ingest_traces(request: Request):
    if request.headers.get("content-type") != "application/x-protobuf":
        raise HTTPException(status_code=415, detail="Expected application/x-protobuf")

    export_request = ExportTraceServiceRequest()
    try:
        export_request.ParseFromString(await request.body())
    except DecodeError:
        raise HTTPException(status_code=400, detail="Malformed protobuf") from None

    resource_spans = len(export_request.resource_spans)
    scope_spans = sum(len(resource.scope_spans) for resource in export_request.resource_spans)
    spans = sum(
        len(scope.spans)
        for resource in export_request.resource_spans
        for scope in resource.scope_spans
    )
    logger.info(
        "Received OTLP traces: resource_spans=%d scope_spans=%d spans=%d",
        resource_spans,
        scope_spans,
        spans,
    )

    return Response(
        content=ExportTraceServiceResponse().SerializeToString(),
        media_type="application/x-protobuf",
    )
