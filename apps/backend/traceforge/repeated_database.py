import os
import re

DETECTOR_ID = "repeated_database_operation"
DETECTOR_VERSION = "1"

UUID_PATTERN = re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", re.IGNORECASE)
STRING_PATTERN = re.compile(r"'(?:''|[^'])*'")
NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?\b")


def normalize_sql(value):
    value = " ".join(value.split())
    value = UUID_PATTERN.sub("?", value)
    value = STRING_PATTERN.sub("?", value)
    return NUMBER_PATTERN.sub("?", value)


def detect(trace, span_rows):
    database_spans = []
    for span in span_rows:
        attributes = span["attributes"]
        database_system = attributes.get("db.system.name") or attributes.get("db.system")
        if not isinstance(database_system, str) or not database_system:
            continue
        database_spans.append(span)

    if not database_spans:
        return {"state": "SKIPPED_NOT_APPLICABLE", "findings": []}

    groups = {}
    for span in database_spans:
        attributes = span["attributes"]
        summary = attributes.get("db.query.summary")
        text = attributes.get("db.query.text") or attributes.get("db.statement")
        if isinstance(summary, str) and summary:
            operation = normalize_sql(summary)
            source = "summary"
        elif isinstance(text, str) and text:
            operation = normalize_sql(text)
            source = "text"
        else:
            continue
        if (
            span["service_id"] is None
            or span["end_time_unix_ns"] is None
            or span["end_time_unix_ns"] < span["start_time_unix_ns"]
        ):
            continue
        database_system = attributes.get("db.system.name") or attributes["db.system"]
        database_name = attributes.get("db.namespace") or attributes.get("db.name") or ""
        if not isinstance(database_name, str):
            database_name = ""
        key = (span["service_id"], database_system, database_name, operation)
        groups.setdefault(key, []).append({**span, "operation": operation, "source": source})

    if not groups:
        return {"state": "SKIPPED_INSUFFICIENT_DATA", "findings": []}

    threshold = int(os.environ.get("TRACE_REPEATED_DATABASE_MIN_COUNT", "5"))
    findings = []
    for group in groups.values():
        if len(group) < threshold:
            continue
        group.sort(key=lambda span: (span["start_time_unix_ns"], span["span_id"]))
        sequential_count = 1
        previous = group[0]
        for span in group[1:]:
            if span["start_time_unix_ns"] >= previous["end_time_unix_ns"]:
                sequential_count += 1
            previous = span

        summary_used = all(span["source"] == "summary" for span in group)
        if summary_used and trace["completeness_state"] == "COMPLETE":
            confidence = "HIGH"
        elif summary_used or trace["completeness_state"] == "COMPLETE":
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        count = len(group)
        findings.append(
            {
                "severity": "MEDIUM" if sequential_count >= threshold else "LOW",
                "confidence": confidence,
                "title": "Repeated database operation",
                "summary": f"{count} structurally equivalent database operations were observed in {group[0]['service_name']}.",
                "observation": f"{count} structurally equivalent database operations were observed.",
                "interpretation": "This pattern may indicate redundant database access or an N+1 query pattern.",
                "structured_data": {
                    "count": count,
                    "sequential_count": sequential_count,
                    "combined_duration_ns": sum(span["duration_ns"] for span in group),
                    "normalized_operation": group[0]["operation"],
                    "service": group[0]["service_name"],
                    "database_system": group[0]["attributes"].get("db.system.name")
                    or group[0]["attributes"].get("db.system"),
                    "database_name": group[0]["attributes"].get("db.namespace")
                    or group[0]["attributes"].get("db.name"),
                },
                "spans": group,
            }
        )

    return {
        "state": "SUCCESS_WITH_FINDINGS" if findings else "SUCCESS_NO_FINDINGS",
        "findings": findings,
    }
