"""Validate frozen cross-project evaluation manifests before scoring."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")


class ExternalValidationFreezeError(ValueError):
    """Raised when an external-validation freeze manifest is incomplete."""


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalValidationFreezeError(f"{path} must be an object")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExternalValidationFreezeError(f"{path} must be a non-empty string")
    return value.strip()


def _commit(value: Any, path: str) -> str:
    text = _text(value, path)
    if _COMMIT_RE.fullmatch(text) is None:
        raise ExternalValidationFreezeError(f"{path} must be a pinned commit SHA")
    return text


def _sha256(value: Any, path: str) -> str:
    text = _text(value, path)
    if _SHA256_RE.fullmatch(text) is None:
        raise ExternalValidationFreezeError(f"{path} must be a lowercase SHA-256")
    return text


def _nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ExternalValidationFreezeError(f"{path} must be a non-negative integer")
    return value


def _positive_int(value: Any, path: str) -> int:
    result = _nonnegative_int(value, path)
    if result == 0:
        raise ExternalValidationFreezeError(f"{path} must be positive")
    return result


def validate_manifest(data: Mapping[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise ExternalValidationFreezeError("schema_version must be 1")
    if data.get("kind") != "external-validation-freeze-manifest":
        raise ExternalValidationFreezeError(
            "kind must be external-validation-freeze-manifest"
        )
    if data.get("status") != "frozen":
        raise ExternalValidationFreezeError("status must be 'frozen' before scoring")
    _text(data.get("comparison_id"), "comparison_id")

    schema_router = _mapping(data.get("schema_router"), "schema_router")
    if schema_router.get("repository") != "JDeun/SchemaRouter":
        raise ExternalValidationFreezeError(
            "schema_router.repository must be JDeun/SchemaRouter"
        )
    _commit(schema_router.get("commit"), "schema_router.commit")

    upstream = _mapping(data.get("upstream"), "upstream")
    _text(upstream.get("repository"), "upstream.repository")
    _commit(upstream.get("commit"), "upstream.commit")
    _text(upstream.get("license"), "upstream.license")
    artifacts = upstream.get("source_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ExternalValidationFreezeError(
            "upstream.source_artifacts must contain at least one pinned artifact"
        )

    catalog = _mapping(data.get("catalog"), "catalog")
    _text(catalog.get("path"), "catalog.path")
    _sha256(catalog.get("sha256"), "catalog.sha256")
    _text(catalog.get("license"), "catalog.license")
    _positive_int(catalog.get("tool_count"), "catalog.tool_count")
    _text(catalog.get("field_contract_source"), "catalog.field_contract_source")
    _sha256(catalog.get("field_contract_sha256"), "catalog.field_contract_sha256")

    cases = _mapping(data.get("cases"), "cases")
    _text(cases.get("path"), "cases.path")
    _sha256(cases.get("sha256"), "cases.sha256")
    supported = _positive_int(cases.get("supported_count"), "cases.supported_count")
    unsupported = _positive_int(
        cases.get("unsupported_count"), "cases.unsupported_count"
    )
    ambiguous = _positive_int(cases.get("ambiguous_count"), "cases.ambiguous_count")
    if supported + unsupported + ambiguous < 3:
        raise ExternalValidationFreezeError("case set is unexpectedly empty")
    if cases.get("labels_frozen") is not True:
        raise ExternalValidationFreezeError("cases.labels_frozen must be true")

    budget = _mapping(data.get("budget"), "budget")
    _positive_int(budget.get("top_k"), "budget.top_k")
    _text(budget.get("schema_budget_definition"), "budget.schema_budget_definition")
    schema_budget = budget.get("schema_budget_bytes")
    if schema_budget is not None:
        _positive_int(schema_budget, "budget.schema_budget_bytes")

    latency = _mapping(data.get("latency"), "latency")
    if latency.get("clock") != "perf_counter":
        raise ExternalValidationFreezeError("latency.clock must be perf_counter")
    _text(latency.get("cold_definition"), "latency.cold_definition")
    _text(latency.get("hot_definition"), "latency.hot_definition")
    _nonnegative_int(latency.get("warmup_runs"), "latency.warmup_runs")
    _positive_int(latency.get("measured_runs"), "latency.measured_runs")

    metrics = _mapping(data.get("metrics"), "metrics")
    for key in (
        "candidate_recall",
        "activation_recall",
        "tool_recall",
        "field_recall",
        "unsupported_rejection",
        "ambiguous_abstention",
        "exposed_schema_bytes",
        "latency_ms",
    ):
        if not isinstance(metrics.get(key), bool):
            raise ExternalValidationFreezeError(f"metrics.{key} must be boolean")
    if metrics.get("tool_recall") is not True:
        raise ExternalValidationFreezeError("tool recall must be measured")
    if metrics.get("field_recall") is not True:
        raise ExternalValidationFreezeError("field recall must be measured separately")
    if metrics.get("unsupported_rejection") is not True:
        raise ExternalValidationFreezeError("unsupported rejection must be measured")

    boundary = _mapping(data.get("boundary"), "boundary")
    _text(boundary.get("schema_router_role"), "boundary.schema_router_role")
    if boundary.get("upstream_execution_authority_preserved") is not True:
        raise ExternalValidationFreezeError(
            "upstream execution authority must remain preserved"
        )
    if boundary.get("external_tool_execution") is not False:
        raise ExternalValidationFreezeError(
            "offline decision package must not execute external tools"
        )
    if boundary.get("paid_model_dependency") is not False:
        raise ExternalValidationFreezeError(
            "offline decision package must not require a paid model"
        )

    governance = _mapping(data.get("governance"), "governance")
    if governance.get("frozen_before_scoring") is not True:
        raise ExternalValidationFreezeError(
            "governance.frozen_before_scoring must be true"
        )
    if governance.get("negative_results_publishable_unchanged") is not True:
        raise ExternalValidationFreezeError(
            "negative results must remain publishable unchanged"
        )
    if governance.get("post_freeze_semantic_tuning_allowed") is not False:
        raise ExternalValidationFreezeError(
            "semantic tuning after freeze must be disabled"
        )
    _text(data.get("created_at_utc"), "created_at_utc")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ExternalValidationFreezeError("manifest root must be an object")
    validate_manifest(data)
    print(
        json.dumps(
            {
                "valid": True,
                "comparison_id": data["comparison_id"],
                "schema_router_commit": data["schema_router"]["commit"],
                "upstream_repository": data["upstream"]["repository"],
                "upstream_commit": data["upstream"]["commit"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
