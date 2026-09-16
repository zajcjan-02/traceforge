import runpy
import urllib.error
from pathlib import Path


RUNNER = runpy.run_path(Path(__file__).parents[1] / "run_benchmarks.py")


class Response:
    status = 200

    def read(self):
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_export_batch_posts_otlp_protobuf(monkeypatch):
    captured = {}

    def urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["content_type"] = request.get_header("Content-type")
        captured["payload"] = request.data
        return Response()

    monkeypatch.setattr(RUNNER["urllib"].request, "urlopen", urlopen)
    result = RUNNER["export_batch"]("http://collector/v1/traces", b"protobuf", 2, 20)

    assert result["accepted"] is True
    assert result["span_count"] == 20
    assert captured == {
        "url": "http://collector/v1/traces",
        "content_type": "application/x-protobuf",
        "payload": b"protobuf",
    }


def test_export_batch_records_export_failures(monkeypatch):
    def urlopen(*_, **__):
        raise urllib.error.URLError("collector unavailable")

    monkeypatch.setattr(RUNNER["urllib"].request, "urlopen", urlopen)
    result = RUNNER["export_batch"]("http://collector/v1/traces", b"protobuf", 1, 10)

    assert result["accepted"] is False
    assert "collector unavailable" in result["error"]
