from traceforge.critical_path import calculate
from traceforge.latency_contributor import detect


def span(span_id, start, end, parent=None, service="orders", name="operation"):
    return {
        "span_id": span_id.to_bytes(8, "big"),
        "parent_span_id": parent.to_bytes(8, "big") if parent else None,
        "service_name": service,
        "name": name,
        "start_time_unix_ns": start,
        "end_time_unix_ns": end,
        "duration_ns": end - start,
    }


def trace():
    return {"completeness_state": "COMPLETE"}


def result(spans):
    return detect(trace(), spans, calculate(trace(), spans))


def test_slow_child_uses_critical_path_contribution():
    spans = [span(1, 0, 3_000_000_000, name="checkout"), span(2, 500_000_000, 2_800_000_000, 1, "payment", "charge")]
    finding = result(spans)["findings"][0]

    assert finding["structured_data"]["span_id"] == "0000000000000002"
    assert finding["structured_data"]["contribution_ns"] == 2_300_000_000
    assert finding["structured_data"]["contribution_fraction"] == 2_300_000_000 / 3_000_000_000
    assert finding["severity"] == "HIGH"
    assert finding["confidence"] == "HIGH"


def test_parent_uses_only_exclusive_segments(monkeypatch):
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_FRACTION", "0.05")
    spans = [span(1, 0, 3_000_000_000), span(2, 100_000_000, 2_900_000_000, 1)]
    findings = result(spans)["findings"]
    root = next(finding for finding in findings if finding["structured_data"]["span_id"] == "0000000000000001")

    assert root["structured_data"]["canonical_duration_ns"] == 3_000_000_000
    assert root["structured_data"]["contribution_ns"] == 200_000_000


def test_parent_exclusive_and_concurrent_work_are_not_double_counted():
    spans = [
        span(1, 0, 3_000_000_000),
        span(2, 200_000_000, 2_200_000_000, 1, name="A"),
        span(3, 500_000_000, 2_800_000_000, 1, name="B"),
    ]
    findings = result(spans)["findings"]

    assert [finding["structured_data"]["span_id"] for finding in findings] == ["0000000000000003"]
    assert findings[0]["structured_data"]["contribution_ns"] == 2_300_000_000


def test_thresholds_are_inclusive_and_segments_are_aggregated(monkeypatch):
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_NS", "200")
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_FRACTION", "0.2")
    spans = [span(1, 0, 1000), span(2, 100, 900, 1)]
    findings = result(spans)["findings"]

    root = next(finding for finding in findings if finding["structured_data"]["span_id"] == "0000000000000001")
    assert root["structured_data"]["contribution_ns"] == 200
    assert len(root["structured_data"]["critical_path_segments"]) == 2


def test_below_relative_threshold_is_not_a_finding(monkeypatch):
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_NS", "100")
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_FRACTION", "0.25")
    spans = [span(1, 0, 1000), span(2, 100, 200, 1)]
    findings = result(spans)["findings"]

    assert [finding["structured_data"]["span_id"] for finding in findings] == ["0000000000000001"]


def test_multiple_significant_contributors_have_stable_order(monkeypatch):
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_NS", "100")
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_FRACTION", "0.25")
    spans = [span(1, 0, 3_000), span(2, 1_000, 2_000, 1)]

    assert [finding["structured_data"]["span_id"] for finding in result(spans)["findings"]] == [
        "0000000000000001",
        "0000000000000002",
    ]


def test_below_threshold_and_unavailable_path_have_no_findings(monkeypatch):
    monkeypatch.setenv("TRACE_LATENCY_MIN_CONTRIBUTION_NS", "1000")
    spans = [span(1, 0, 999)]

    assert result(spans)["state"] == "SUCCESS_NO_FINDINGS"
    assert detect(trace(), spans, {"state": "UNAVAILABLE"}) == {
        "state": "SKIPPED_INSUFFICIENT_DATA",
        "findings": [],
    }
