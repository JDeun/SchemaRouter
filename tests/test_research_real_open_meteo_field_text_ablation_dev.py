"""Bounded source-text variants preserve host-authorized candidate/field shape."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.research_open_meteo_real_openapi_dev import (
    SOURCE_COMMIT,
    SOURCE_NAMES,
    git_blob_sha1,
)
from scripts.research_real_open_meteo_e5_cpu_dev import MODEL_REVISION
from scripts.research_real_open_meteo_field_text_ablation_dev import (
    VARIANTS,
    evaluate,
    render_authorized_option,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    folder = tmp_path / "provider"
    folder.mkdir()
    docs = {}
    for name in SOURCE_NAMES:
        payload = f"""openapi: 3.1.0
info:
  title: Offline unit fixture for {name}
  version: 1.0.0
paths:
  /v1/{name}:
    get:
      summary: Read {name} forecast data
      parameters:
        - name: latitude
          in: query
          description: Geographic coordinate
          schema:
            type: number
      responses:
        '200':
          description: Synthetic response
          content:
            application/json:
              schema:
                type: object
                properties:
                  value:
                    type: string
""".encode()
        (folder / f"{name}.yml").write_bytes(payload)
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
    return manifest, folder


def _fake_encoder(texts: list[str]) -> list[list[float]]:
    return [
        [1.0, 0.0] if x.startswith("query: ") else [0.8, 0.6]
        for x in texts
    ]


def test_only_authorized_fields_enrich_passage_and_no_gold_leaks() -> None:
    scoped = SimpleNamespace(
        route_id="publisher.allowed_get",
        tool_description="Weather API",
        endpoint_description="Read forecast",
        parameters=[
            SimpleNamespace(
                name="hourly", description="Hourly marine waves",
            ),
            SimpleNamespace(
                name="latitude", description="",
            ),
        ],
        output_fields=[SimpleNamespace(
            semantic_id="wave_height", name="visible_field",
        )],
    )
    base = render_authorized_option(scoped, "original")
    names = render_authorized_option(scoped, "parameter_names")
    full = render_authorized_option(scoped, "parameter_descriptions")
    assert base.description == "Weather API\nRead forecast"
    assert "hourly" in names.description
    assert "marine waves" not in names.description
    assert "Hourly marine waves" in full.description
    assert "wave_height" in full.description
    assert all(item.id == scoped.route_id for item in (base, names, full))
    with pytest.raises(ValueError, match="unregistered"):
        render_authorized_option(scoped, "oracle_gold")


def test_all_variants_are_pure_reranks_of_current_scoped_real_api(
    tmp_path: Path,
) -> None:
    manifest, folder = _fixture(tmp_path)
    results = evaluate(
        manifest, folder, _fake_encoder,
        model_revision=MODEL_REVISION,
    )
    assert results["actual_cases"] == results["expected_cases"] == 36
    assert set(results["variants"]) == set(VARIANTS)
    assert results["scope"]["may_release"] is False
    assert results["scope"]["candidate_metadata_only_after_authorization"]
    for row in results["cases"]:
        original = set(row["ranked"]["original"])
        assert len(original) == 9
        assert all(
            set(row["ranked"][variant]) == original
            for variant in VARIANTS
        )
        assert row["all_variants_authorized"]
        assert row["tool_executed"] is False
        assert row["no_fit_tested"] is False
    assert results["strata"]["all"]["supported"] == 27
    assert results["strata"]["all"]["unsupported"] == 9


@pytest.mark.parametrize("revision", ("", "main", "a" * 40))
def test_fails_closed_on_unpinned_model_revision(
    tmp_path: Path, revision: str,
) -> None:
    manifest, folder = _fixture(tmp_path)
    with pytest.raises(ValueError, match="unregistered"):
        evaluate(manifest, folder, _fake_encoder, model_revision=revision)


def test_source_blob_drift_rejected_before_encoder_call(tmp_path: Path) -> None:
    manifest, folder = _fixture(tmp_path)
    path = folder / "marine.yml"
    path.write_bytes(path.read_bytes() + b"# changed\n")
    used = []
    def tracking_encoder(texts: list[str]) -> list[list[float]]:
        used.append(texts)
        return _fake_encoder(texts)
    with pytest.raises(ValueError, match="byte drift"):
        evaluate(
            manifest, folder, tracking_encoder,
            model_revision=MODEL_REVISION,
        )
    assert not used
