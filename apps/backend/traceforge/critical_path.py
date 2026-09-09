import heapq


def unavailable(reason):
    return {"state": "UNAVAILABLE", "reason": reason, "duration_ns": None, "segments": []}


def calculate(trace, spans):
    records = {}
    children = {}

    for span in spans:
        span_id = span.get("span_id")
        start = span.get("start_time_unix_ns")
        end = span.get("end_time_unix_ns")
        if span_id in records:
            return unavailable("DUPLICATE_SPAN_ID")
        if not isinstance(start, int) or not isinstance(end, int) or start >= end:
            return unavailable("INVALID_TIMING")
        records[span_id] = {"start": start, "end": end, "parent": span.get("parent_span_id") or None}
        children[span_id] = []

    if not records:
        return unavailable("NO_SPANS")

    roots = []
    for span_id, span in records.items():
        if span["parent"] is None:
            roots.append(span_id)
        elif span["parent"] not in records:
            return unavailable("MISSING_PARENT")
        else:
            children[span["parent"]].append(span_id)

    if len(roots) != 1:
        return unavailable("MULTIPLE_OR_MISSING_ROOTS")

    root_id = roots[0]
    visited = set()
    pending = [root_id]
    while pending:
        span_id = pending.pop()
        if span_id in visited:
            return unavailable("CYCLE")
        visited.add(span_id)
        pending.extend(children[span_id])
    if len(visited) != len(records):
        return unavailable("CYCLE")
    if trace.get("completeness_state") != "COMPLETE":
        return unavailable("TRACE_NOT_COMPLETE")

    segments = []

    def add_segment(span_id, start, end):
        if start == end:
            return
        if segments and segments[-1]["span_id"] == span_id and segments[-1]["end_time_unix_ns"] == start:
            segments[-1]["end_time_unix_ns"] = end
            segments[-1]["contribution_ns"] += end - start
            return
        segments.append(
            {
                "span_id": span_id,
                "start_time_unix_ns": start,
                "end_time_unix_ns": end,
                "contribution_ns": end - start,
            }
        )

    def walk(span_id, window_start, window_end):
        events = {}
        for child_id in children[span_id]:
            child = records[child_id]
            start = max(window_start, child["start"])
            end = min(window_end, child["end"])
            if start >= end:
                raise ValueError("CHILD_OUTSIDE_PARENT")
            events.setdefault(start, []).append(child_id)
            events.setdefault(end, [])

        active = []
        ownership = []
        points = sorted({window_start, window_end, *events})
        for index, point in enumerate(points[:-1]):
            for child_id in events.get(point, []):
                child = records[child_id]
                if child["start"] <= point < child["end"]:
                    heapq.heappush(active, (-min(window_end, child["end"]), child_id))
            next_point = points[index + 1]
            while active and -active[0][0] <= point:
                heapq.heappop(active)
            owner = active[0][1] if active else span_id
            if ownership and ownership[-1][0] == owner and ownership[-1][2] == point:
                ownership[-1] = (owner, ownership[-1][1], next_point)
            else:
                ownership.append((owner, point, next_point))

        for owner, start, end in ownership:
            if owner == span_id:
                add_segment(span_id, start, end)
            else:
                walk(owner, start, end)

    root = records[root_id]
    try:
        walk(root_id, root["start"], root["end"])
    except ValueError:
        return unavailable("CHILD_OUTSIDE_PARENT")

    duration = sum(segment["contribution_ns"] for segment in segments)
    if (
        duration != root["end"] - root["start"]
        or any(
            segment["start_time_unix_ns"] < root["start"]
            or segment["end_time_unix_ns"] > root["end"]
            or segment["start_time_unix_ns"] >= segment["end_time_unix_ns"]
            or segment["contribution_ns"]
            != segment["end_time_unix_ns"] - segment["start_time_unix_ns"]
            for segment in segments
        )
        or any(
            left["end_time_unix_ns"] > right["start_time_unix_ns"]
            or (
                left["span_id"] == right["span_id"]
                and left["end_time_unix_ns"] == right["start_time_unix_ns"]
            )
            for left, right in zip(segments, segments[1:])
        )
    ):
        return unavailable("INVARIANT_VIOLATION")

    return {"state": "AVAILABLE", "reason": None, "duration_ns": duration, "segments": segments}
