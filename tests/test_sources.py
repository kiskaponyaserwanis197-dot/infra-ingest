import subprocess

import requests

from infra_ingest.sources import _request_with_retries, download_audio_from_url, is_url, title_from_url


def test_is_url_only_accepts_http_urls():
    assert is_url("https://example.com/a")
    assert is_url("http://example.com")
    assert not is_url("/tmp/file.txt")
    assert not is_url("ftp://example.com/file")


def test_is_url_strips_whitespace_and_requires_host():
    assert is_url("  https://example.com/report  ")
    assert not is_url("https:///missing-host")
    assert not is_url("example.com/report")


def test_title_from_url_builds_readable_slug():
    assert title_from_url("https://www.example.com/reports/alpha factor?id=1") == "example.com-reports-alpha-factor"


def test_title_from_url_keeps_chinese_slug_and_falls_back_to_host():
    assert title_from_url("https://www.example.com/") == "example.com"
    assert title_from_url("https://www.example.com/研报/新能源?id=1") == "example.com-研报-新能源"


def test_download_audio_from_url_raises_clear_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr("infra_ingest.sources._find_yt_dlp", lambda: "yt-dlp")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=1)

    monkeypatch.setattr("infra_ingest.sources.subprocess.run", fake_run)

    try:
        download_audio_from_url("https://example.com/video", tmp_path, timeout=1)
    except RuntimeError as exc:
        assert "yt-dlp 下载超时" in str(exc)
    else:
        raise AssertionError("expected timeout error")


def test_request_with_retries_recovers_from_timeout(monkeypatch):
    calls = []

    class FakeResponse:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    def fake_request(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise requests.Timeout("slow")
        return FakeResponse()

    monkeypatch.setattr("infra_ingest.sources.requests.request", fake_request)
    monkeypatch.setattr("infra_ingest.sources.time.sleep", lambda _seconds: None)

    response = _request_with_retries("GET", "https://example.com", retries=2, timeout=1)

    assert response.text == "ok"
    assert len(calls) == 2


def test_request_with_retries_does_not_retry_client_errors(monkeypatch):
    class FakeResponse:
        status_code = 404
        text = "missing"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("infra_ingest.sources.requests.request", lambda *args, **kwargs: FakeResponse())

    try:
        _request_with_retries("GET", "https://example.com/missing", retries=3, timeout=1)
    except RuntimeError as exc:
        assert "HTTP 404 客户端错误" in str(exc)
    else:
        raise AssertionError("expected client error")
