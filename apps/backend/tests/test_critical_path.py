from traceforge.critical_path import calculate


def span(span_id, start, end, parent=None):
    return {
        "span_id": span_id,
        "parent_span_id": parent,
        "start_time_unix_ns": start,
        "end_time_unix_ns": end,
    }


def trace(state="COMPLETE"):
    return {"completeness_state": state}


def compact(result):
    return [
        (segment["span_id"], segment["start_time_unix_ns"], segment["end_time_unix_ns"])
        for segment in result["segments"]
    ]


def test_nested_span_preserves_parent_exclusive_time():
    result = calculate(trace(), [span("A", 0, 1000), span("B", 100, 900, "A")])

    assert result["duration_ns"] == 1000
    assert compact(result) == [("A", 0, 100), ("B", 100, 900), ("A", 900, 1000)]


def test_sequential_children_do_not_double_count():
    result = calculate(
        trace(), [span("P", 0, 1000), span("A", 100, 300, "P"), span("B", 400, 900, "P")]
    )

    assert compact(result) == [
        ("P", 0, 100), ("A", 100, 300), ("P", 300, 400), ("B", 400, 900), ("P", 900, 1000)
    ]


def test_concurrent_children_use_latest_effective_end_rule():
    result = calculate(
        trace(), [span("R", 0, 1000), span("A", 100, 700, "R"), span("B", 200, 900, "R")]
    )

    assert compact(result) == [("R", 0, 100), ("A", 100, 200), ("B", 200, 900), ("R", 900, 1000)]


def test_partial_overlap_and_deep_nesting_are_partitioned():
    result = calculate(
        trace(),
        [
            span("A", 0, 1000), span("B", 100, 500, "A"), span("C", 400, 800, "A"),
            span("D", 450, 700, "C"),
        ],
    )

    assert compact(result) == [
        ("A", 0, 100), ("B", 100, 400), ("C", 400, 450), ("D", 450, 700), ("C", 700, 800), ("A", 800, 1000)
    ]


def test_result_invariants_and_determinism():
    spans = [span("R", 0, 100), span("A", 10, 80, "R"), span("B", 20, 90, "R")]
    first = calculate(trace(), spans)
    second = calculate(trace(), spans)

    assert first == second
    assert first["duration_ns"] == 100
    assert sum(segment["contribution_ns"] for segment in first["segments"]) == 100
    for left, right in zip(first["segments"], first["segments"][1:]):
        assert left["end_time_unix_ns"] <= right["start_time_unix_ns"]
        assert not (
            left["span_id"] == right["span_id"]
            and left["end_time_unix_ns"] == right["start_time_unix_ns"]
        )
    for segment in first["segments"]:
        assert segment["contribution_ns"] == segment["end_time_unix_ns"] - segment["start_time_unix_ns"]
        assert 0 <= segment["start_time_unix_ns"] < segment["end_time_unix_ns"] <= 100


def test_invalid_or_incomplete_traces_are_unavailable():
    assert calculate(trace(), [span("A", 0, 10, "missing")])["reason"] == "MISSING_PARENT"
    assert calculate(trace(), [span("A", 0, 10), span("B", 0, 10)])["reason"] == "MULTIPLE_OR_MISSING_ROOTS"
    assert calculate(trace(), [span("A", 10, 10)])["reason"] == "INVALID_TIMING"
    assert calculate(trace("INCOMPLETE"), [span("A", 0, 10)])["reason"] == "TRACE_NOT_COMPLETE"
    assert calculate(trace(), [span("A", 0, 10), span("B", 20, 30, "A")])["reason"] == "CHILD_OUTSIDE_PARENT"
