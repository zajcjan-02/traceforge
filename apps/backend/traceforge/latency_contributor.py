import os

DETECTOR_ID = "latency_contributor"
DETECTOR_VERSION = "1"


def detect(trace, span_rows, critical_path):
    if critical_path["state"] != "AVAILABLE":
        return {"state": "SKIPPED_INSUFFICIENT_DATA", "findings": []}

    duration = critical_path["duration_ns"]
    contributions = {}
    for segment in critical_path["segments"]:
        contributions.setdefault(segment["span_id"], []).append(segment)

    absolute_threshold = int(os.environ.get("TRACE_LATENCY_MIN_CONTRIBUTION_NS", "100000000"))
    relative_threshold = float(os.environ.get("TRACE_LATENCY_MIN_CONTRIBUTION_FRACTION", "0.25"))
    spans = {span["span_id"]: span for span in span_rows}
    findings = []
    for span_id, segments in contributions.items():
        contribution = sum(segment["contribution_ns"] for segment in segments)
        fraction = contribution / duration
        if contribution < absolute_threshold or fraction < relative_threshold:
            continue
        span = spans[span_id]
        service = span["service_name"] or "unknown service"
        segment_data = [
            {
                "start_time_unix_ns": segment["start_time_unix_ns"],
                "end_time_unix_ns": segment["end_time_unix_ns"],
                "contribution_ns": segment["contribution_ns"],
            }
            for segment in segments
        ]
        structured_data = {
            "span_id": span_id.hex(),
            "service": service,
            "span_name": span["name"],
            "contribution_ns": contribution,
            "critical_path_duration_ns": duration,
            "contribution_fraction": fraction,
            "canonical_duration_ns": span["duration_ns"],
            "critical_path_segments": segment_data,
        }
        findings.append(
            {
                "type": "MAJOR_LATENCY_CONTRIBUTOR",
                "severity": "HIGH" if fraction >= 0.5 else "MEDIUM",
                "confidence": "HIGH",
                "title": "Major latency contributor",
                "summary": f"{service} / {span['name']} contributed {contribution / 1_000_000_000:.2f} s of the {duration / 1_000_000_000:.2f} s critical path.",
                "observation": f"{service} / {span['name']} contributed {contribution / 1_000_000_000:.2f} s of the {duration / 1_000_000_000:.2f} s critical path.",
                "interpretation": "This operation was a major contributor to the request's observed latency.",
                "structured_data": structured_data,
                "evidence": [
                    {
                        "type": "CRITICAL_PATH_CONTRIBUTION",
                        "structured_data": {key: value for key, value in structured_data.items() if key != "critical_path_segments"},
                    },
                    {"type": "CRITICAL_PATH_SEGMENTS", "structured_data": {"segments": segment_data}},
                ],
                "spans": [span],
                "relation": "CRITICAL_PATH_CONTRIBUTOR",
            }
        )

    findings.sort(key=lambda finding: (-finding["structured_data"]["contribution_ns"], finding["structured_data"]["span_id"]))
    return {"state": "SUCCESS_WITH_FINDINGS" if findings else "SUCCESS_NO_FINDINGS", "findings": findings}
