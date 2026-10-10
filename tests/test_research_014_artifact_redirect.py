"""Regression coverage for GitHub Actions artifact redirect authorization."""

from __future__ import annotations

import urllib.request

import pytest

from scripts.research_014_conveyor import _CrossOriginSafeRedirect


def _request() -> urllib.request.Request:
    return urllib.request.Request(
        "https://api.github.com/repos/JDeun/SchemaRouter/actions/artifacts/123/zip",
        headers={
            "Authorization": "Bearer secret",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "schemarouter-test",
        },
    )


def test_artifact_redirect_does_not_forward_github_authorization() -> None:
    redirected = _CrossOriginSafeRedirect().redirect_request(
        _request(),
        None,
        302,
        "Found",
        {},
        "https://results.blob.core.windows.net/artifacts/archive.zip?sig=fixture",
    )
    assert redirected is not None
    assert redirected.full_url.endswith("sig=fixture")
    headers = {key.lower(): value for key, value in redirected.header_items()}
    assert "authorization" not in headers
    assert "x-github-api-version" not in headers
    assert headers["user-agent"] == "schemarouter-test"


def test_same_origin_redirect_preserves_github_authorization() -> None:
    redirected = _CrossOriginSafeRedirect().redirect_request(
        _request(),
        None,
        302,
        "Found",
        {},
        "https://api.github.com/repos/JDeun/SchemaRouter/actions/artifacts/123",
    )
    assert redirected is not None
    headers = {key.lower(): value for key, value in redirected.header_items()}
    assert headers["authorization"] == "Bearer secret"
    assert headers["x-github-api-version"] == "2022-11-28"


def test_redirect_refuses_tls_downgrade_even_on_same_host() -> None:
    with pytest.raises(RuntimeError, match="non-HTTPS"):
        _CrossOriginSafeRedirect().redirect_request(
            _request(),
            None,
            302,
            "Found",
            {},
            "http://api.github.com/repos/JDeun/SchemaRouter/actions/artifacts/123",
        )
