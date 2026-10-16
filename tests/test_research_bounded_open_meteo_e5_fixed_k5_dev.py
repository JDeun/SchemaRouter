"""Offline source-provenance/denominator controls, NEVER real quality claims."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PlanningError
from scripts.research_bounded_open_meteo_e5_fixed_k5_dev import (
    MAX_REGISTERED_ROUTES,
    MODEL_REVISION,
    STRICT_K,
    percentile_95,
    run_visible_dev,
)
from scripts.research_open_meteo_real_openapi_dev import (
    SOURCE_COMMIT,
    SOURCE_NAMES,
    git_blob_sha1,
)


def _fake_publisher(tmp_path: Path) -> tuple[Path, Path]:
    """Nine fake local publisher docs, never confused with real source."""
    original = tmp_path / "synthetic_not_original"
    original.mkdir()
    docs = {}
    for name in SOURCE_NAMES:
        payload = f"""openapi: 3.1.0
info:
  title: Synthetic {name} source, not publisher evidence
  version: 1.0.0
paths:
  /v1/{name}:
    get:
      summary: Read {name} published observations
      responses:
        '200':
          description: synthetic control only
          content:
            application/json:
              schema:
                type: object
                properties:
                  amount:
                    type: number
""".encode()
        (original / f"{name}.yml").write_bytes(payload)
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
    return manifest, original


def _synthetic_five(request):
    assert request.max_selections == STRICT_K
    assert len(request.options) == MAX_REGISTERED_ROUTES
    assert all(opt.id.startswith("native:") for opt in request.options)
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:STRICT_K]
    ]}


def test_original_dev_denominators_fixed_k5_and_synthetic_no_promotion(
    tmp_path: Path,
) -> None:
    manifest, source = _fake_publisher(tmp_path)
    output = run_visible_dev(
        manifest, source,
        CallableDecisionBackend(_synthetic_five),
    )
    assert output["evidence_role"].endswith("_DEV_NOT_INDEPENDENT")
    assert output["strict_k"] == 5
    assert output["original_native_route_count"] == 9
    assert output["supported_cases"] == 27
    assert output["unsupported_cases"] == 9
    assert len(output["original_visible_dev_rows"]) == 36
    assert set(output["by_language"]) == {"en", "ko", "ja"}
    for name, item in output["by_language"].items():
        assert name in {"en", "ko", "ja"}
        assert item["supported_cases"] == 9
        assert item["unsupported_cases"] == 3
        assert item["model_unsupported_nonempty_not_no_fit"] == 3
        assert item["lexical_unsupported_nonempty_not_no_fit"] == 3
    assert all(
        len(row["semantic_native_k5"]) == len(row["lexical_native_k5"]) == 5
        for row in output["original_visible_dev_rows"]
    )
    assert output["aggregate"]["max_model_input_bytes"] <= 131072
    assert output["limitations"]["query_gold_independent"] is False
    assert output["limitations"]["measured_agent_task_success"] is False
    assert output["limitations"]["commercial_release_authorized"] is False
    assert all(
        row["native_provider_tools_invoked"] is False
        for row in output["original_visible_dev_rows"]
    )


def test_changed_original_schema_must_fail_before_model_receives_data(
    tmp_path: Path,
) -> None:
    manifest, source = _fake_publisher(tmp_path)
    path = source / "marine.yml"
    path.write_bytes(path.read_bytes() + b"# malicious changed original\n")

    def forbidden(_request):
        raise AssertionError("backend must not receive altered original source")

    with pytest.raises(ValueError, match="byte drift"):
        run_visible_dev(manifest, source, CallableDecisionBackend(forbidden))


def test_partial_model_choice_is_not_repaired_with_gold_or_lexical(
    tmp_path: Path,
) -> None:
    manifest, source = _fake_publisher(tmp_path)
    with pytest.raises(ValueError, match="invalid strict-K"):
        run_visible_dev(
            manifest, source,
            CallableDecisionBackend(
                lambda request: {
                    "selections": [{"option_id": request.options[0].id}],
                },
            ),
        )


def test_forged_native_model_id_is_never_accepted(
    tmp_path: Path,
) -> None:
    manifest, source = _fake_publisher(tmp_path)
    with pytest.raises(PlanningError, match="unknown option"):
        run_visible_dev(
            manifest, source,
            CallableDecisionBackend(
                lambda _: {"selections": [{"option_id": "native:999"}]},
            ),
        )


def test_model_checkpoint_revision_is_immutable(tmp_path: Path) -> None:
    manifest, source = _fake_publisher(tmp_path)
    with pytest.raises(ValueError, match="exact fixed real E5 model revision"):
        run_visible_dev(
            manifest, source, CallableDecisionBackend(_synthetic_five),
            checkpoint_revision="main",
        )
    assert len(MODEL_REVISION) == 40


def test_p95_uses_nearest_rank_and_no_empty_observation() -> None:
    assert percentile_95([4.0, 1.0, 3.0, 2.0]) == 4.0
    with pytest.raises(ValueError, match="finite"):
        percentile_95([])
