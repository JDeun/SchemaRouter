"""Bounded GitHub Actions GET retry regression for research-0.14 recovery."""

from __future__ import annotations

import io
import urllib.error

import pytest

from scripts import research_014_conveyor as conveyor


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"ok": true}'


class _Opener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def open(self, request):
        self.calls.append(request.get_method())
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return _Response()


def _error(code):
    return urllib.error.HTTPError(
        "https://api.github.com/repos/JDeun/SchemaRouter/actions/runs/1/jobs",
        code,
        "test",
        {},
        io.BytesIO(b'{"message":"fixture"}'),
    )


def _api(monkeypatch, outcomes):
    api = conveyor.GitHubAPI("JDeun/SchemaRouter", "test-secret")
    opener = _Opener(outcomes)
    delays = []
    monkeypatch.setattr(api, "_opener", opener)
    monkeypatch.setattr(conveyor.time, "sleep", delays.append)
    return api, opener, delays


def test_transient_502_get_retries_and_preserves_json(monkeypatch):
    transient = _error(502)
    api, opener, delays = _api(monkeypatch, [transient, True])
    assert api.get("/actions/runs/1/jobs?per_page=100&page=2") == {"ok": True}
    assert opener.calls == ["GET", "GET"]
    assert delays == [1]
    assert transient.closed


def test_transient_get_errors_have_bounded_exponential_backoff(monkeypatch):
    failures = [_error(502), _error(503), _error(504), _error(500)]
    api, opener, delays = _api(monkeypatch, failures)
    with pytest.raises(RuntimeError, match="GET .* failed: 500"):
        api.get("/actions/runs/1/jobs")
    assert opener.calls == ["GET"] * 4
    assert delays == [1, 2, 4]
    assert all(error.closed for error in failures)


def test_nontransient_get_404_fails_without_retry(monkeypatch):
    unexpected = _error(404)
    api, opener, delays = _api(monkeypatch, [unexpected])
    with pytest.raises(RuntimeError, match="failed: 404"):
        api.get("/contents/not-found")
    assert opener.calls == ["GET"]
    assert delays == []
    assert unexpected.closed


def test_post_never_retries_to_avoid_duplicate_dispatch(monkeypatch):
    unexpected = _error(502)
    api, opener, delays = _api(monkeypatch, [unexpected])
    with pytest.raises(RuntimeError, match="POST .* failed: 502"):
        api.post("/actions/workflows/example.yml/dispatches", {"ref": "main"})
    assert opener.calls == ["POST"]
    assert delays == []
    assert unexpected.closed
