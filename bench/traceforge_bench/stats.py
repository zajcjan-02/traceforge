import math


def summary(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "p50": None, "p95": None, "max": None}

    def percentile(percent):
        return values[math.ceil(len(values) * percent) - 1]

    return {
        "count": len(values),
        "p50": percentile(0.50),
        "p95": percentile(0.95),
        "max": values[-1],
    }
