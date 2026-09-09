from traceforge.error_origin import detect, normalize_observations


def span(span_id, parent=None, end=100, status="ERROR", attributes=None, service="orders"):
    return {
        "span_id": span_id.to_bytes(8, "big"),
        "parent_span_id": parent.to_bytes(8, "big") if parent else None,
        "end_time_unix_ns": end,
        "status": status,
        "attributes": attributes or {},
        "service_name": service,
        "name": f"span-{span_id}",
    }


def event(span_id, timestamp, name="exception", attributes=None):
    return {
        "span_id": span_id.to_bytes(8, "big"),
        "timestamp_unix_ns": timestamp,
        "name": name,
        "attributes": attributes or {"exception.type": "Timeout"},
    }


def trace(state="COMPLETE"):
    return {"completeness_state": state}


def test_downstream_exception_with_later_ancestors_is_origin():
    spans = [span(1, end=400), span(2, 1, 300), span(3, 2, 200, service="database")]
    result = detect(trace(), spans, [event(3, 150)])
    finding = result["findings"][0]

    assert finding["structured_data"]["origin_span_id"] == "0000000000000003"
    assert finding["structured_data"]["propagation_span_ids"] == [
        "0000000000000003", "0000000000000002", "0000000000000001"
    ]
    assert finding["confidence"] == "HIGH"


def test_upstream_or_equal_error_is_not_blame_shifted_downstream():
    spans = [span(1, end=50), span(2, 1, 200)]

    assert detect(trace(), spans, [event(2, 100)])["findings"] == []
    equal_timing = [span(1, end=100), span(2, 1, 200)]
    assert detect(trace(), equal_timing, [event(2, 100), event(1, 100)])["findings"] == []


def test_independent_branches_do_not_form_a_chain():
    spans = [span(1, status="UNSET"), span(2, 1, 200), span(3, 1, 300)]

    assert detect(trace(), spans, [event(2, 150), event(3, 250)])["findings"] == []


def test_known_http_rpc_and_error_type_are_normalized():
    observations = normalize_observations(
        [
            span(1, attributes={"http.response.status_code": 503, "error.type": "HttpFailure"}),
            span(2, attributes={"rpc.system.name": "grpc", "rpc.response.status_code": "UNAVAILABLE", "error.type": "RpcFailure"}),
            span(3, attributes={"rpc.grpc.status_code": 14}),
        ],
        [],
    )

    assert observations[span(1)["span_id"]]["error_type"] == "HttpFailure"
    assert observations[span(2)["span_id"]]["source"] == "rpc_failure"
    assert observations[span(3)["span_id"]]["source"] == "rpc_failure_legacy"


def test_incomplete_trace_needs_an_intact_ordered_chain():
    spans = [span(1, end=300), span(2, 1, 200)]
    result = detect(trace("INCOMPLETE"), spans, [event(2, 100)])

    assert result["findings"][0]["confidence"] == "MEDIUM"
    assert detect(trace("INCOMPLETE"), [span(2, 9, 200)], [event(2, 100)])["findings"] == []
