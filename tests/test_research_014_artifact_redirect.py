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


def test_frozen_heldout_preflight_patches_transport_without_changing_source() -> None:
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/research-0.14-heldout-generalization.yml"
    ).read_text(encoding="utf-8")

    assert 'ref: "${{ inputs.source_sha }}"' in workflow
    preflight = workflow.split(
        "- name: Verify exact upstream artifacts and optional-condition gates", 1
    )[1].split("- name: Generate fresh held-out corpus", 1)[0]
    assert "urllib.request.install_opener(" in preflight
    assert "urllib.request.build_opener(_SafeArtifactRedirect())" in preflight
    assert "target.scheme.lower() != \"https\"" in preflight
    assert "redirected.remove_header(header)" in preflight
    assert "GitHubAPI, combine_digests" in preflight
    assert preflight.index("urllib.request.install_opener(") < preflight.index(
        "from scripts.research_014_conveyor import GitHubAPI"
    )
