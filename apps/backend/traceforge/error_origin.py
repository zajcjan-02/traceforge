DETECTOR_ID = "error_origin"
DETECTOR_VERSION = "1"


def normalize_observations(span_rows, event_rows):
    events_by_span = {}
    for event in event_rows:
        events_by_span.setdefault(event["span_id"], []).append(event)

    observations = {}
    for span in span_rows:
        candidates = []
        error_type = span["attributes"].get("error.type")
        for event in events_by_span.get(span["span_id"], []):
            if event["name"] != "exception" or event["timestamp_unix_ns"] is None:
                continue
            attributes = event["attributes"]
            candidates.append(
                {
                    "timestamp_unix_ns": event["timestamp_unix_ns"],
                    "source": "exception_event",
                    "error_type": attributes.get("exception.type") or error_type,
                    "concrete": True,
                }
            )

        timestamp = span["end_time_unix_ns"]
        if timestamp is None:
            continue
        attributes = span["attributes"]
        if span["status"] == "ERROR":
            candidates.append(
                {
                    "timestamp_unix_ns": timestamp,
                    "source": "span_status",
                    "error_type": error_type,
                    "concrete": isinstance(error_type, str) and bool(error_type),
                }
            )
        http_status = attributes.get("http.response.status_code", attributes.get("http.status_code"))
        if isinstance(http_status, int) and http_status >= 500:
            candidates.append(
                {
                    "timestamp_unix_ns": timestamp,
                    "source": "http_5xx",
                    "error_type": error_type,
                    "concrete": isinstance(error_type, str) and bool(error_type),
                }
            )
        rpc_status = attributes.get("rpc.response.status_code")
        if attributes.get("rpc.system.name") == "grpc" and isinstance(rpc_status, str) and rpc_status.upper() != "OK":
            candidates.append(
                {
                    "timestamp_unix_ns": timestamp,
                    "source": "rpc_failure",
                    "error_type": error_type,
                    "concrete": isinstance(error_type, str) and bool(error_type),
                }
            )
        legacy_status = attributes.get("rpc.grpc.status_code")
        if isinstance(legacy_status, int) and legacy_status != 0:
            candidates.append(
                {
                    "timestamp_unix_ns": timestamp,
                    "source": "rpc_failure_legacy",
                    "error_type": error_type,
                    "concrete": isinstance(error_type, str) and bool(error_type),
                }
            )
        if candidates:
            observations[span["span_id"]] = min(
                candidates,
                key=lambda observation: (
                    observation["timestamp_unix_ns"],
                    {"exception_event": 0, "http_5xx": 1, "rpc_failure": 1, "rpc_failure_legacy": 1}.get(
                        observation["source"], 2
                    ),
                    not observation["concrete"],
                ),
            )
    return observations


def detect(trace, span_rows, event_rows):
    observations = normalize_observations(span_rows, event_rows)
    if not observations:
        return {"state": "SUCCESS_NO_FINDINGS", "findings": []}

    spans = {span["span_id"]: span for span in span_rows}
    children = {span_id: [] for span_id in spans}
    roots = []
    for span in span_rows:
        parent_id = span["parent_span_id"]
        if parent_id is None:
            roots.append(span["span_id"])
        elif parent_id in children:
            children[parent_id].append(span["span_id"])

    def descendants(span_id):
        pending = list(children[span_id])
        found = []
        while pending:
            child_id = pending.pop()
            found.append(child_id)
            pending.extend(children[child_id])
        return found

    findings = []
    for span_id, observation in sorted(observations.items(), key=lambda item: (item[1]["timestamp_unix_ns"], item[0])):
        span = spans[span_id]
        parent_id = span["parent_span_id"]
        chain = [span_id]
        intact = True
        while parent_id is not None:
            parent = spans.get(parent_id)
            if parent is None:
                intact = False
                break
            parent_observation = observations.get(parent_id)
            if parent_observation is not None:
                if parent_observation["timestamp_unix_ns"] <= observation["timestamp_unix_ns"]:
                    intact = False
                    break
                chain.append(parent_id)
            parent_id = parent["parent_span_id"]
        if not intact or len(chain) == 1:
            continue
        if any(
            observations[child_id]["timestamp_unix_ns"] <= observation["timestamp_unix_ns"]
            for child_id in descendants(span_id)
            if child_id in observations
        ):
            continue

        reaches_root = len(roots) == 1 and chain[-1] == roots[0]
        confidence = "HIGH" if observation["concrete"] and reaches_root and trace["completeness_state"] == "COMPLETE" else "MEDIUM"
        service = span["service_name"] or "unknown service"
        chain_data = [
            {
                "span_id": chain_span_id.hex(),
                "service": spans[chain_span_id]["service_name"] or "unknown service",
                "span_name": spans[chain_span_id]["name"],
                "error_timestamp_unix_ns": observations[chain_span_id]["timestamp_unix_ns"],
            }
            for chain_span_id in chain
        ]
        structured_data = {
            "origin_span_id": span_id.hex(),
            "service": service,
            "span_name": span["name"],
            "first_error_timestamp_unix_ns": observation["timestamp_unix_ns"],
            "error_source": observation["source"],
            "error_type": observation["error_type"],
            "has_concrete_exception": observation["concrete"],
            "propagation_span_ids": [chain_span_id.hex() for chain_span_id in chain],
            "ancestor_error_count": len(chain) - 1,
            "reaches_root": reaches_root,
        }
        findings.append(
            {
                "type": "LIKELY_ERROR_ORIGIN",
                "severity": "HIGH" if reaches_root else "MEDIUM",
                "confidence": confidence,
                "title": "Likely error origin",
                "summary": f"{service} / {span['name']} is the earliest observed failure in a {len(chain)}-span propagation chain.",
                "observation": f"{observation['source']} was observed in {service} before {len(chain) - 1} ancestor spans reported errors.",
                "interpretation": "This is the earliest observed failure in the associated propagation chain.",
                "structured_data": structured_data,
                "evidence": [
                    {"type": "ERROR_ORIGIN_OBSERVATION", "structured_data": structured_data},
                    {"type": "ERROR_PROPAGATION_CHAIN", "structured_data": {"chain": chain_data}},
                ],
                "span_relations": [
                    {"span": spans[chain_span_id], "relation": "ERROR_ORIGIN" if index == 0 else "ERROR_PROPAGATION"}
                    for index, chain_span_id in enumerate(chain)
                ],
            }
        )

    return {"state": "SUCCESS_WITH_FINDINGS" if findings else "SUCCESS_NO_FINDINGS", "findings": findings}
