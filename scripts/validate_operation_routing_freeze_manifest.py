"""Validate an operation-routing candidate freeze manifest before evidence promotion."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

EXPECTED_TARGET = {
    "supported_exact_route_accuracy_min": 0.85,
    "near_domain_unsupported_rejection_min": 0.97,
    "out_of_domain_rejection": 1.0,
    "false_route_rate_max": 0.01,
    "authority_violations_max": 0,
    "execution_errors_max": 0,
    "combined_p95_ms_max": 250.0,
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_SOURCE_REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")


class FreezeManifestError(ValueError):
    """Raised when a freeze manifest violates the research contract."""


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FreezeManifestError(f"{path} must be an object")
    return value


def _nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FreezeManifestError(f"{path} must be a non-empty string")
    return value.strip()


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FreezeManifestError(f"{path} must be a positive integer")
    return value


def _sha256(value: Any, path: str) -> str:
    text = _nonempty_string(value, path)
    if _SHA256_RE.fullmatch(text) is None:
        raise FreezeManifestError(f"{path} must be a lowercase SHA-256 hex digest")
    return text


def _source_revision(value: Any, path: str) -> str:
    text = _nonempty_string(value, path)
    if _SOURCE_REVISION_RE.fullmatch(text) is None:
        raise FreezeManifestError(
            f"{path} must be a pinned 40-64 character lowercase hex revision"
        )
    return text


def _artifact_digest(value: Any, path: str) -> str:
    text = _nonempty_string(value, path)
    if _SHA256_DIGEST_RE.fullmatch(text) is None:
        raise FreezeManifestError(
            f"{path} must be a SHA-256 digest, optionally prefixed with 'sha256:'"
        )
    return text


def _model_revision(value: Any, path: str) -> str:
    return _nonempty_string(value, path)


def _metric_float(metrics: Mapping[str, Any], key: str, path: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FreezeManifestError(f"{path}.{key} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise FreezeManifestError(f"{path}.{key} must be finite")
    return result


def _validate_metrics(metrics_value: Any, path: str) -> None:
    metrics = _mapping(metrics_value, path)
    exact = _metric_float(metrics, "supported_exact_route_accuracy", path)
    near = _metric_float(metrics, "near_domain_unsupported_rejection", path)
    ood = _metric_float(metrics, "out_of_domain_rejection", path)
    false_rate = _metric_float(metrics, "false_route_rate", path)
    authority = _metric_float(metrics, "authority_violations", path)
    errors = _metric_float(metrics, "execution_errors", path)
    p95 = _metric_float(metrics, "combined_p95_ms", path)

    for name, value in (
        ("supported_exact_route_accuracy", exact),
        ("near_domain_unsupported_rejection", near),
        ("out_of_domain_rejection", ood),
        ("false_route_rate", false_rate),
    ):
        if not 0.0 <= value <= 1.0:
            raise FreezeManifestError(f"{path}.{name} must be between 0 and 1")
    if p95 < 0.0:
        raise FreezeManifestError(f"{path}.combined_p95_ms must be >= 0")
    if authority < 0.0:
        raise FreezeManifestError(f"{path}.authority_violations must be >= 0")
    if errors < 0.0:
        raise FreezeManifestError(f"{path}.execution_errors must be >= 0")

    if exact < EXPECTED_TARGET["supported_exact_route_accuracy_min"]:
        raise FreezeManifestError(f"{path} misses supported exact-route target")
    if near < EXPECTED_TARGET["near_domain_unsupported_rejection_min"]:
        raise FreezeManifestError(f"{path} misses near-domain rejection target")
    if ood != EXPECTED_TARGET["out_of_domain_rejection"]:
        raise FreezeManifestError(f"{path} misses OOD rejection target")
    if false_rate > EXPECTED_TARGET["false_route_rate_max"]:
        raise FreezeManifestError(f"{path} exceeds false-route target")
    if authority != EXPECTED_TARGET["authority_violations_max"]:
        raise FreezeManifestError(f"{path} contains authority violations")
    if errors != EXPECTED_TARGET["execution_errors_max"]:
        raise FreezeManifestError(f"{path} contains execution errors")
    if p95 > EXPECTED_TARGET["combined_p95_ms_max"]:
        raise FreezeManifestError(f"{path} exceeds combined p95 target")


def _validate_evidence_phase(value: Any, path: str) -> None:
    evidence = _mapping(value, path)
    _nonempty_string(evidence.get("corpus_seed"), f"{path}.corpus_seed")
    _sha256(evidence.get("corpus_sha256"), f"{path}.corpus_sha256")
    _positive_int(evidence.get("workflow_run_id"), f"{path}.workflow_run_id")
    _positive_int(evidence.get("artifact_id"), f"{path}.artifact_id")
    _artifact_digest(evidence.get("artifact_sha256"), f"{path}.artifact_sha256")
    _validate_metrics(evidence.get("metrics"), f"{path}.metrics")


def validate_manifest(data: Mapping[str, Any], *, phase: str) -> None:
    if data.get("schema_version") != 1:
        raise FreezeManifestError("schema_version must be 1")
    if data.get("kind") != "operation-routing-freeze-manifest":
        raise FreezeManifestError("kind must be operation-routing-freeze-manifest")
    if data.get("production_target") != EXPECTED_TARGET:
        raise FreezeManifestError("production_target differs from the frozen target")

    expected_status = "frozen-dev" if phase == "dev" else "fresh-confirmed"
    if data.get("status") != expected_status:
        raise FreezeManifestError(
            f"status must be {expected_status!r} for phase {phase!r}"
        )

    candidate = _mapping(data.get("candidate"), "candidate")
    _nonempty_string(candidate.get("candidate_id"), "candidate.candidate_id")
    _source_revision(candidate.get("source_revision"), "candidate.source_revision")
    _nonempty_string(candidate.get("architecture_id"), "candidate.architecture_id")

    authority = _mapping(candidate.get("authority"), "candidate.authority")
    _nonempty_string(authority.get("route_authority"), "candidate.authority.route_authority")
    _nonempty_string(authority.get("verifier_role"), "candidate.authority.verifier_role")
    required_authority = {
        "finite_registered_ids_only": True,
        "rank2_fallback": False,
        "pseudo_route": False,
        "provider_can_create_execution_authority": False,
    }
    for key, expected in required_authority.items():
        if authority.get(key) is not expected:
            raise FreezeManifestError(
                f"candidate.authority.{key} must be {expected!r}"
            )

    models = candidate.get("models")
    if not isinstance(models, list) or not models:
        raise FreezeManifestError("candidate.models must contain at least one pinned model")
    for index, model_value in enumerate(models):
        model = _mapping(model_value, f"candidate.models[{index}]")
        _nonempty_string(model.get("role"), f"candidate.models[{index}].role")
        _nonempty_string(model.get("name"), f"candidate.models[{index}].name")
        _model_revision(
            model.get("revision"),
            f"candidate.models[{index}].revision",
        )

    runtime = _mapping(candidate.get("runtime"), "candidate.runtime")
    _nonempty_string(runtime.get("python"), "candidate.runtime.python")
    _mapping(runtime.get("dependency_versions"), "candidate.runtime.dependency_versions")
    _nonempty_string(runtime.get("hardware_label"), "candidate.runtime.hardware_label")

    representation = _mapping(
        candidate.get("representation"),
        "candidate.representation",
    )
    for key in (
        "query_representation_sha256",
        "capability_representation_sha256",
        "prompt_or_instruction_sha256",
    ):
        _sha256(representation.get(key), f"candidate.representation.{key}")
    _nonempty_string(
        representation.get("option_ordering_rule"),
        "candidate.representation.option_ordering_rule",
    )

    decision_rule = _mapping(candidate.get("decision_rule"), "candidate.decision_rule")
    _nonempty_string(decision_rule.get("rule_id"), "candidate.decision_rule.rule_id")
    threshold = decision_rule.get("threshold")
    if threshold is not None:
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise FreezeManifestError("candidate.decision_rule.threshold must be numeric or null")
        if not math.isfinite(float(threshold)):
            raise FreezeManifestError("candidate.decision_rule.threshold must be finite")
    _mapping(decision_rule.get("parameters"), "candidate.decision_rule.parameters")

    evidence = _mapping(data.get("evidence"), "evidence")
    _validate_evidence_phase(evidence.get("development"), "evidence.development")

    fresh = evidence.get("fresh_confirmation")
    if phase == "fresh":
        fresh_mapping = _mapping(fresh, "evidence.fresh_confirmation")
        _nonempty_string(
            fresh_mapping.get("surface_id"),
            "evidence.fresh_confirmation.surface_id",
        )
        _nonempty_string(
            fresh_mapping.get("zero_overlap_audit_artifact"),
            "evidence.fresh_confirmation.zero_overlap_audit_artifact",
        )
        _validate_evidence_phase(
            fresh_mapping,
            "evidence.fresh_confirmation",
        )

    governance = _mapping(data.get("governance"), "governance")
    if governance.get("failed_confirmation_tuning_forbidden") != [270, 287]:
        raise FreezeManifestError(
            "governance.failed_confirmation_tuning_forbidden must be [270, 287]"
        )
    if governance.get("semantic_retuning_after_freeze_allowed") is not False:
        raise FreezeManifestError(
            "governance.semantic_retuning_after_freeze_allowed must be false"
        )
    if (
        governance.get(
            "runtime_only_optimization_after_quality_pass_requires_same_semantics"
        )
        is not True
    ):
        raise FreezeManifestError(
            "runtime-only optimization must require unchanged semantics"
        )
    if governance.get("calibration_or_blind_inspected") is not False:
        raise FreezeManifestError(
            "calibration_or_blind_inspected must be false before #198"
        )
    if governance.get("calibration_issue") != 198:
        raise FreezeManifestError("governance.calibration_issue must be 198")
    if governance.get("paper_evidence_issue") != 199:
        raise FreezeManifestError("governance.paper_evidence_issue must be 199")
    if governance.get("canonical_tracker_issue") != 200:
        raise FreezeManifestError("governance.canonical_tracker_issue must be 200")

    _nonempty_string(data.get("created_at_utc"), "created_at_utc")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--phase", choices=("dev", "fresh"), required=True)
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise FreezeManifestError("manifest root must be an object")

    validate_manifest(data, phase=args.phase)
    print(
        json.dumps(
            {
                "valid": True,
                "phase": args.phase,
                "candidate_id": data["candidate"]["candidate_id"],
                "source_revision": data["candidate"]["source_revision"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
