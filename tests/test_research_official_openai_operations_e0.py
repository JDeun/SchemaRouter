"""Original publisher HTTP method preservation and source journal, E0 only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemarouter.native_graph_index import NativeSchemaGraphIndex
from scripts import research_official_openai_get_e0 as source


@pytest.fixture(scope="module")
def original() -> dict:
    base = source.FIXTURE_DIR / f"openai-openapi-{source.PUBLISHER_COMMIT[:8]}"
    return source.parse_pinned_openai_source(
        Path(str(base) + "-openapi.yaml.gz").read_bytes(),
        Path(str(base) + "-LICENSE.txt").read_bytes(),
    )


def test_exact_upstream_yaml_date_like_literals_remain_json_strings(original: dict) -> None:
    # safe_load's implicit timestamp coercion previously broke authentic
    # POST response schemas containing literal 2024-10-01/2026-10-08.
    dumped = json.dumps(original, sort_keys=True, allow_nan=False)
    assert '"2024-10-01"' in dumped
    assert '"2026-10-08"' in dumped


@pytest.mark.parametrize(
    ("path", "method"),
    (("/responses", "post"), ("/models/{model}", "delete")),
)
def test_original_non_get_projection_preserves_full_operation_and_security(
    original: dict, path: str, method: str,
) -> None:
    # Regression: prior GET-only scoping cannot drop body/auth on a write.
    selected = source.scope_original_http_operation_source(original, path, method)
    assert set(selected["paths"]) == {path}
    assert selected["paths"][path][method] == original["paths"][path][method]
    assert selected["security"] == original["security"]
    assert selected["components"]["securitySchemes"] == original["components"][
        "securitySchemes"
    ]


@pytest.mark.parametrize(
    ("path", "method"),
    (("/responses?beta=true", "post"), ("/responses/{response_id}?beta=true", "delete"),
     ("/models", "delete"), ("/models", "GET"), ("/models", "options")),
)
def test_original_operation_projection_rejects_invalid_source_or_method(
    original: dict, path: str, method: str,
) -> None:
    with pytest.raises(ValueError, match="unsupported|invalid"):
        source.scope_original_http_operation_source(original, path, method)


@pytest.fixture(scope="module")
def whole_source_receipt() -> dict:
    from scripts.research_official_openai_operations_e0 import (
        audit_official_openai_operations_churn_e0,
    )

    return audit_official_openai_operations_churn_e0()


def test_all_supported_real_http_methods_are_registered_without_grants(
    whole_source_receipt: dict,
) -> None:
    receipt = whole_source_receipt
    assert receipt["original_source_operation_count"] == 371
    assert receipt["unsupported_literal_query_operation_count"] == 7
    assert receipt["unsupported_non_json_body_operation_count"] == 9
    assert receipt["native_method_counts"] == {"GET": 161, "POST": 142, "DELETE": 52}
    assert receipt["native_original_operations"] == 355
    assert receipt["mixed_provider_route_counts"] == [358, 357, 358]
    assert receipt["required_path_inputs_preserved"] is True
    assert receipt["original_authentication_preserved"] is True
    assert receipt["required_json_bodies_preserved"] is True
    assert receipt["write_methods_never_read_only"] is True
    assert receipt["source_methods_and_operation_ids_preserved"] is True
    assert receipt["untrusted_semantic_postings"] == 0
    assert receipt["unauthorized_dependency_edges"] == 0
    assert receipt["provider_runtime_calls"] == 0
    assert receipt["execution_authority"] is False
    assert receipt["publisher_gold_verified"] is False
    assert receipt["independent_e2_qualified"] is False


def test_original_multipart_only_operations_are_explicitly_unrepresentable(
    original: dict, whole_source_receipt: dict,
) -> None:
    # Source-derived independent inventory, not computed from the compiled
    # native registry. The adapter only understands JSON request bodies.
    unsupported = {
        (path, method)
        for path, path_item in original["paths"].items() if "?" not in path
        for method, operation in path_item.items() if method in {"get", "post", "delete"}
        if (body := operation.get("requestBody", {})).get("content")
        and "application/json" not in body["content"]
    }
    assert unsupported == {
        ("/audio/transcriptions", "post"), ("/audio/translations", "post"),
        ("/audio/voice_consents", "post"), ("/files", "post"),
        ("/images/variations", "post"), ("/realtime/calls", "post"),
        ("/uploads/{upload_id}/parts", "post"),
        ("/content_provenance_checks", "post"), ("/videos/characters", "post"),
    }
    assert whole_source_receipt["unsupported_non_json_body_operation_count"] == len(unsupported)


def test_real_http_method_churn_matches_full_source_oracle_and_rejects_stale(
    whole_source_receipt: dict,
) -> None:
    receipt = whole_source_receipt
    assert receipt["distinct_registry_versions"] == 3
    assert receipt["distinct_index_snapshots"] == 3
    assert receipt["stale_index_rejections"] == 2
    assert receipt["journal_rebuild_matches"] is True
    assert receipt["original_source_manifest_matches"] is True


def test_real_write_method_churn_rejects_forged_noop_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.research_official_openai_operations_e0 import (
        audit_official_openai_operations_churn_e0,
    )

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(lambda cls, previous, registry: previous),
    )
    with pytest.raises(ValueError, match="journal|stale|snapshot"):
        audit_official_openai_operations_churn_e0()
