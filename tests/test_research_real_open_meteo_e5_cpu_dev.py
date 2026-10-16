"""Offline trust-boundary tests for E5 semantic reranking of published schemas.

The fixture is a local stand-in for source-verification test purposes only.
The Actions real-model job loads publisher-authored Open-Meteo documents.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemarouter import PlanRequest, PrincipalContext
from scripts.research_open_meteo_real_openapi_dev import (
    SOURCE_COMMIT,
    SOURCE_NAMES,
    git_blob_sha1,
)
from scripts.research_real_open_meteo_e5_cpu_dev import (
    MODEL_REVISION,
    candidate_options,
    catalog,
    evaluate_with_encoder,
    validate_semantic_ranks,
)


def _local_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "official"
    source.mkdir()
    docs = {}
    for name in SOURCE_NAMES:
        payload = f"""openapi: 3.1.0
info:
  title: Offline fixture {name}
  version: 1.0.0
paths:
  /v1/{name}:
    get:
      summary: Get {name} measurements and forecast
      responses:
        '200':
          description: fixture-only response
          content:
            application/json:
              schema:
                type: object
                properties:
                  value:
                    type: string
""".encode()
        (source / f"{name}.yml").write_bytes(payload)
        docs[name] = {
            "path": f"openapi/{name}.yml",
            "git_blob_sha1": git_blob_sha1(payload),
        }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "provider_repository": "open-meteo/open-meteo",
        "source_commit": SOURCE_COMMIT,
        "real_provider_authored_spec": True,
        "independently_authored_query_labels": False,
        "may_release": False,
        "docs": docs,
    }), encoding="utf-8")
    return manifest, source


def _dummy_encoder(texts: list[str]) -> list[list[float]]:
    # This fake encoder is ONLY for control flow and never serves as evidence
    # that multilingual textual similarity works.
    return [
        [1.0, 0.0] if text.startswith("query:") else [0.8, 0.6]
        for text in texts
    ]


def test_no_real_model_or_api_invocation_still_runs_36_cases(tmp_path: Path) -> None:
    manifest, sources = _local_fixture(tmp_path)
    output = evaluate_with_encoder(
        manifest, sources, _dummy_encoder,
        model_source_revision=MODEL_REVISION,
    )
    assert len(output["rows"]) == 36
    assert output["supported"] == 27 and output["unsupported"] == 9
    assert all(row["semantic_returned_full_authorized_catalog"]
               for row in output["rows"])
    assert all(row["actual_tool_called"] is False for row in output["rows"])
    assert output["limitations"]["may_release"] is False
    assert output["limitations"]["product_default_retrieve_uses_e5"] is False
    assert output["limitations"]["independently_reviewed_queries"] is False


def test_model_is_only_given_authorized_route_subset(tmp_path: Path) -> None:
    manifest, sources = _local_fixture(tmp_path)
    router, viewer, routes, _ = catalog(manifest, sources)
    allowed = set().union(*(set(group) for group in routes.values()))
    options, ids, scores = candidate_options(
        router, viewer, query="파도 예보를 알려주세요",
        expected_route_ids=allowed,
    )
    assert len(options) == len(ids) == len(scores) == 9
    assert {option.id for option in options} == allowed
    assert all(option.id.startswith("open_meteo_") for option in options)
    with pytest.raises(ValueError, match="authorized"):
        validate_semantic_ranks(ids + ["invented.unsafe"], allowed)
    with pytest.raises(ValueError, match="authorized"):
        validate_semantic_ranks(ids[:-1] + ["invented.unsafe"], allowed)

    denied = PrincipalContext(
        subject="untrusted-denied-role", roles=("none",),
    )
    actual = router.retrieve_authorized(
        PlanRequest(query="Get weather"), principal=denied, k=9,
    )
    assert actual.candidates == []


@pytest.mark.parametrize("invalid", ("main", "", "a" * 40))
def test_model_source_revision_must_be_pinned(
    invalid: str, tmp_path: Path,
) -> None:
    manifest, sources = _local_fixture(tmp_path)
    with pytest.raises(ValueError, match="checkpoint"):
        evaluate_with_encoder(
            manifest, sources, _dummy_encoder,
            model_source_revision=invalid,
        )


def test_altered_real_provider_schema_fails_before_any_model_call(
    tmp_path: Path,
) -> None:
    manifest, sources = _local_fixture(tmp_path)
    (sources / "marine.yml").write_bytes(
        (sources / "marine.yml").read_bytes() + b"# tampered\n"
    )
    calls = []
    def fail_if_called(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return _dummy_encoder(texts)
    with pytest.raises(ValueError, match="byte drift"):
        evaluate_with_encoder(
            manifest, sources, fail_if_called,
            model_source_revision=MODEL_REVISION,
        )
    assert not calls
