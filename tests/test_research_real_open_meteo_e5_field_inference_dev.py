"""No oracle leakage, no unauthorized metadata, no mutation in field inference."""
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
from scripts.research_real_open_meteo_e5_field_inference_dev import (
    MAX_FIELDS,
    PASSAGE_STYLES,
    authorized_enum_fields,
    evaluate,
    field_options,
)


def _candidate(
    route: str,
    *,
    values: list[str],
    read_only: bool = True,
    output: bool = False,
):
    return SimpleNamespace(
        route_id=route,
        read_only=read_only,
        parameters=[
            SimpleNamespace(
                name="hourly",
                location="query",
                json_schema={
                    "type": "array",
                    "items": {"type": "string", "enum": values},
                },
            ),
            SimpleNamespace(
                name="injected",
                location="body",
                json_schema={"enum": ["hidden_action"]},
            ),
        ],
    )


def _provider_fixture(tmp_path: Path) -> tuple[Path, Path]:
    directory = tmp_path / "official"
    directory.mkdir()
    docs = {}
    for source in SOURCE_NAMES:
        payload = f"""openapi: 3.1.0
info:
  title: Offline {source} source fixture
  version: 1.0.0
paths:
  /v1/{source}:
    get:
      summary: Read {source} forecast
      parameters:
        - name: hourly
          in: query
          schema:
            type: array
            items:
              type: string
              enum: [temperature_2m, wave_height]
      responses:
        '200':
          description: fixture response
          content:
            application/json:
              schema:
                type: object
                properties:
                  value:
                    type: string
""".encode()
        (directory / f"{source}.yml").write_bytes(payload)
        docs[source] = {
            "path": f"openapi/{source}.yml",
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
    return manifest, directory


def _fake_encoder(texts: list[str]) -> list[list[float]]:
    """Only verify API plumbing; not evidence of semantic field recall."""
    return [
        [1.0, 0.0] if text.startswith("query: ") else [0.6, 0.8]
        for text in texts
    ]


def test_only_read_only_query_enums_from_authorized_candidates() -> None:
    fields, sources, stats = authorized_enum_fields([
        _candidate("allowed.one", values=["wave_height", "temperature_2m"]),
        _candidate("allowed.two", values=["wave_height"]),
        _candidate("hidden.write", values=["delete_all"], read_only=False),
    ])
    assert fields == [
        ("hourly", "temperature_2m"), ("hourly", "wave_height"),
    ]
    assert sources["hourly:wave_height"] == ["allowed.one", "allowed.two"]
    assert stats["seen_route_count"] == 3
    assert "hourly:delete_all" not in sources
    assert not any("hidden_action" in str(item) for item in fields)
    for style in PASSAGE_STYLES:
        opts = field_options(fields, style)
        assert len(opts) == 2
        assert {item.id for item in opts} == {
            "field:hourly:temperature_2m", "field:hourly:wave_height",
        }


def test_duplicate_route_and_large_enum_fail_closed() -> None:
    item = _candidate("allowed.one", values=["wave_height"])
    with pytest.raises(ValueError, match="duplicated"):
        authorized_enum_fields([item, item])
    excess = _candidate(
        "one.read", values=[f"var_{i}" for i in range(1025)],
    )
    with pytest.raises(ValueError, match="no authorized"):
        authorized_enum_fields([excess])
    assert MAX_FIELDS >= 1000


def test_all_three_languages_infer_without_using_oracle(
    tmp_path: Path,
) -> None:
    manifest, folder = _provider_fixture(tmp_path)
    report = evaluate(
        manifest, folder, _fake_encoder,
        model_revision=MODEL_REVISION,
    )
    assert len(report["cases"]) == 36
    assert report["by_language"]["all"]["supported"] == 27
    assert report["by_language"]["all"]["gold_defined"] == 24
    assert report["by_language"]["all"]["unsupported_unscored"] == 9
    assert report["scope"]["field_inference_uses_human_gold"] is False
    assert report["scope"]["may_change_default_or_release"] is False
    assert all(
        row["all_predicted_from_authorized_source"]
        for row in report["cases"]
    )
    assert all(
        row["human_gold_fields_for_scoring_only"] is None
        for row in report["cases"] if row["kind"] == "unsupported"
    )


@pytest.mark.parametrize("bad", ("main", "unknown", "", "a" * 40))
def test_unpinned_checkpoint_must_fail(
    tmp_path: Path, bad: str,
) -> None:
    manifest, folder = _provider_fixture(tmp_path)
    with pytest.raises(ValueError, match="immutable"):
        evaluate(
            manifest, folder, _fake_encoder,
            model_revision=bad,
        )


def test_corrupted_original_publisher_blob_stops_encoder_first(
    tmp_path: Path,
) -> None:
    manifest, folder = _provider_fixture(tmp_path)
    original = folder / "flood.yml"
    original.write_bytes(original.read_bytes() + b"# modified\n")
    calls = []
    def tracked(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return _fake_encoder(texts)
    with pytest.raises(ValueError, match="byte drift"):
        evaluate(
            manifest, folder, tracked,
            model_revision=MODEL_REVISION,
        )
    assert not calls


def test_unknown_passage_style_is_not_a_gold_oracle() -> None:
    with pytest.raises(ValueError, match="unregistered"):
        field_options([("hourly", "wave_height")], "gold_source")
