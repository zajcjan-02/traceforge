from traceforge_bench.stats import summary


def test_summary_uses_nearest_rank_percentiles():
    assert summary([1, 2, 3, 4, 5]) == {"count": 5, "p50": 3, "p95": 5, "max": 5}


def test_summary_handles_empty_values():
    assert summary([]) == {"count": 0, "p50": None, "p95": None, "max": None}
