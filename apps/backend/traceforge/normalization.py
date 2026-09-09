import base64

from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status


def normalize_request(export_request):
    spans = []
    for resource_spans in export_request.resource_spans:
        resource_attributes = normalize_attributes(resource_spans.resource.attributes)
        service_name = resource_attributes.get("service.name")
        service_namespace = resource_attributes.get("service.namespace", "")

        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                end_time = span.end_time_unix_nano or None
                spans.append(
                    {
                        "trace_id": bytes(span.trace_id),
                        "span_id": bytes(span.span_id),
                        "parent_span_id": bytes(span.parent_span_id) or None,
                        "service_name": service_name if isinstance(service_name, str) else None,
                        "service_namespace": (
                            service_namespace if isinstance(service_namespace, str) else ""
                        ),
                        "name": span.name,
                        "span_kind": Span.SpanKind.Name(span.kind).removeprefix("SPAN_KIND_"),
                        "start_time_unix_ns": span.start_time_unix_nano,
                        "end_time_unix_ns": end_time,
                        "duration_ns": (
                            end_time - span.start_time_unix_nano if end_time is not None else None
                        ),
                        "status": Status.StatusCode.Name(span.status.code).removeprefix(
                            "STATUS_CODE_"
                        ),
                        "attributes": normalize_attributes(span.attributes),
                        "resource_attributes": resource_attributes,
                        "events": [
                            {
                                "event_index": index,
                                "name": event.name,
                                "timestamp_unix_ns": event.time_unix_nano or None,
                                "attributes": normalize_attributes(event.attributes),
                            }
                            for index, event in enumerate(span.events)
                        ],
                    }
                )

    return spans


def normalize_attributes(attributes):
    return {attribute.key: normalize_value(attribute.value) for attribute in attributes}


def normalize_value(value):
    kind = value.WhichOneof("value")
    if kind == "string_value":
        return value.string_value
    if kind == "bool_value":
        return value.bool_value
    if kind == "int_value":
        return value.int_value
    if kind == "double_value":
        return value.double_value
    if kind == "bytes_value":
        return {"bytes": base64.b64encode(value.bytes_value).decode()}
    if kind == "array_value":
        return [normalize_value(item) for item in value.array_value.values]
    if kind == "kvlist_value":
        return normalize_attributes(value.kvlist_value.values)
    return None
