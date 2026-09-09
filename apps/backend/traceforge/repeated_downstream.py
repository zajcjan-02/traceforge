import os

DETECTOR_ID = "repeated_downstream_operation"
DETECTOR_VERSION = "1"


def detect(trace, span_rows):
    candidates = False
    groups = {}
    for span in span_rows:
        if span["span_kind"] != "CLIENT":
            continue
        attributes = span["attributes"]
        method = attributes.get("http.request.method")
        rpc_system = attributes.get("rpc.system.name")
        if not isinstance(method, str) and not isinstance(rpc_system, str):
            continue
        candidates = True
        address = attributes.get("server.address")
        if (
            span["service_id"] is None
            or not isinstance(address, str)
            or not address
            or span["end_time_unix_ns"] is None
            or span["end_time_unix_ns"] < span["start_time_unix_ns"]
        ):
            continue
        port = attributes.get("server.port")
        target = f"{address}:{port}" if isinstance(port, int) else address
        if isinstance(method, str) and method:
            template = attributes.get("url.template")
            if not isinstance(template, str) or not template:
                continue
            protocol = "HTTP"
            operation = f"{method.upper()} {template}"
        elif isinstance(rpc_system, str) and rpc_system:
            method = attributes.get("rpc.method")
            if not isinstance(method, str) or not method:
                continue
            protocol = f"RPC:{rpc_system}"
            operation = method
        else:
            continue
        key = (span["service_id"], target, protocol, operation)
        groups.setdefault(key, []).append({**span, "target": target, "protocol": protocol, "operation": operation})

    if not candidates:
        return {"state": "SKIPPED_NOT_APPLICABLE", "findings": []}
    if not groups:
        return {"state": "SKIPPED_INSUFFICIENT_DATA", "findings": []}

    threshold = int(os.environ.get("TRACE_REPEATED_DOWNSTREAM_MIN_COUNT", "5"))
    findings = []
    for key in sorted(groups):
        group = groups[key]
        if len(group) < threshold:
            continue
        group.sort(key=lambda span: (span["start_time_unix_ns"], span["span_id"]))
        sequential_count = 1
        previous = group[0]
        for span in group[1:]:
            if span["start_time_unix_ns"] >= previous["end_time_unix_ns"]:
                sequential_count += 1
            previous = span

        count = len(group)
        combined_duration = sum(span["duration_ns"] for span in group)
        service = group[0]["service_name"] or "unknown service"
        structured_data = {
            "count": count,
            "sequential_count": sequential_count,
            "combined_duration_ns": combined_duration,
            "normalized_operation": group[0]["operation"],
            "source_service": service,
            "target_peer": group[0]["target"],
            "protocol": group[0]["protocol"],
        }
        findings.append(
            {
                "type": "REPEATED_DOWNSTREAM_OPERATION",
                "severity": "MEDIUM" if sequential_count * 2 > count else "LOW",
                "confidence": "HIGH" if trace["completeness_state"] == "COMPLETE" else "MEDIUM",
                "title": "Repeated downstream operation",
                "summary": f"{count} structurally equivalent downstream {group[0]['protocol']} calls were observed from {service} to {group[0]['target']}.",
                "observation": f"{count} structurally equivalent downstream calls were observed.",
                "interpretation": "This pattern may indicate redundant downstream requests or per-item remote access.",
                "structured_data": structured_data,
                "evidence": [
                    {"type": "DOWNSTREAM_OPERATION_COUNT", "structured_data": {"count": count}},
                    {
                        "type": "DOWNSTREAM_OPERATION_TIMING",
                        "structured_data": {
                            "sequential_count": sequential_count,
                            "combined_duration_ns": combined_duration,
                        },
                    },
                    {"type": "DOWNSTREAM_OPERATION_CONTEXT", "structured_data": structured_data},
                ],
                "spans": group,
                "relation": "REPEATED_DOWNSTREAM_OPERATION",
            }
        )

    return {
        "state": "SUCCESS_WITH_FINDINGS" if findings else "SUCCESS_NO_FINDINGS",
        "findings": findings,
    }
