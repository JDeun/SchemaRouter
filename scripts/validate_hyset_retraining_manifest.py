"""Offline, no-model HYSET independently retrained comparison preflight (#795).

Read-only structural checks. Passing them does not establish independent
review, permit held-out scoring, or reproduce the unavailable paper best.pt.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

PINNED_HYSET_SHA = "93808cb8d633b6b685f0f9353923b27c2ad7ad81"
ENCODER_REPOSITORY = "reasonwang/ToolGen-Qwen2.5-1.5B-Tool-Retriever"
RESULT_LABEL = "independently retrained HYSET"
SPLITS = (
    "data/test_query_ids/G1_category_test_query_ids.json",
    "data/test_query_ids/G1_instruction_test_query_ids.json",
    "data/test_query_ids/G1_tool_test_query_ids.json",
    "data/test_query_ids/G2_category_test_query_ids.json",
    "data/test_query_ids/G2_instruction_test_query_ids.json",
    "data/test_query_ids/G3_instruction_test_query_ids.json",
)


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{label}: missing or unexpected fields")
    return value


def _sha(value: Any, length: int, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label}: require lowercase {length}-character digest")


def _literal_false(value: Any, label: str) -> None:
    if value is not False:
        raise ValueError(f"{label}: must be literal false")


def _literal_true(value: Any, label: str) -> None:
    if value is not True:
        raise ValueError(f"{label}: must be literal true")


def _training_configuration(training: dict[str, Any]) -> None:
    configuration = _object(
        training["primary_configuration"],
        {"encoder_type", "d_z", "eta", "mode", "command"},
        "training.primary_configuration",
    )
    model = configuration["encoder_type"]
    expected_dimensions = {"bert": 768, "qwen": 1536}
    if (
        type(model) is not str
        or model not in expected_dimensions
        or type(configuration["d_z"]) is not int
        or configuration["d_z"] != expected_dimensions[model]
    ):
        raise ValueError("encoder type/d_z must match documented HYSET configurations")
    eta = configuration["eta"]
    if type(eta) not in (int, float):
        raise ValueError("eta must be numeric, finite and preregistered")
    try:
        eta_finite = math.isfinite(eta)
    except OverflowError:
        eta_finite = False
    if not eta_finite:
        raise ValueError("eta must be numeric, finite and preregistered")
    if (
        type(configuration["command"]) is not str
        or not configuration["command"].strip()
        or "train_hyset.sh" not in configuration["command"]
    ):
        raise ValueError("pinned public train_hyset.sh invocation is required")
    if eta == 0:
        if configuration["mode"] != "annotation_only_eta0":
            raise ValueError("eta=0 requires explicit annotation-only ablation label")
        if training["reward_cache_digest"] is not None:
            raise ValueError("eta=0 must not claim an execution reward cache")
    elif eta == 0.3:
        if configuration["mode"] != "execution_reward_eta03":
            raise ValueError("eta=0.3 must explicitly identify execution-reward training")
        _sha(training["reward_cache_digest"], 64, "reward cache")
    else:
        raise ValueError("eta must be the preregistered 0.3 or annotation-only 0")


def validate_manifest(manifest: Any, *, stage: str = "development") -> dict[str, Any]:
    """Validate provenance only; NEVER declare scoring or reproduction approved."""
    if stage not in {"development", "training", "evaluation"}:
        raise ValueError("unknown HYSET preflight stage")

    m = _object(manifest, {
        "schema_version", "kind", "status", "issue", "comparison_id",
        "upstream", "encoder", "data", "training", "governance",
    }, "manifest")
    if (
        type(m["schema_version"]) is not int or m["schema_version"] != 1
        or m["kind"] != "hyset-public-retraining-development-manifest"
        or type(m["issue"]) is not int or m["issue"] != 795
        or m["comparison_id"] != "schemarouter-hyset-public-retraining-v1"
    ):
        raise ValueError("incorrect HYSET comparison protocol identity")

    upstream = _object(m["upstream"], {
        "repository", "commit", "paper_checkpoint_available", "result_label",
    }, "upstream")
    if upstream["repository"] != "stormwther18/HYSET":
        raise ValueError("unexpected upstream HYSET repository")
    _sha(upstream["commit"], 40, "HYSET commit")
    if upstream["commit"] != PINNED_HYSET_SHA:
        raise ValueError("HYSET upstream commit deviates from pinned public protocol")
    _literal_false(upstream["paper_checkpoint_available"], "paper checkpoint availability")
    if upstream["result_label"] != RESULT_LABEL:
        raise ValueError("results must be labeled independently retrained HYSET")

    encoder = _object(m["encoder"], {"repository", "revision"}, "encoder")
    if encoder["repository"] != ENCODER_REPOSITORY:
        raise ValueError("unexpected public ToolGen encoder repository")

    data = _object(m["data"], {
        "toolbench_source_revision", "toolbench_digest",
        "heldout_split_ids", "heldout_split_paths",
    }, "data")
    if data["heldout_split_ids"] != (
        "six data/test_query_ids/*_test_query_ids.json files at pinned HYSET commit"
    ):
        raise ValueError("heldout split identity description drift")
    if data["heldout_split_paths"] != list(SPLITS):
        raise ValueError("must preserve all six exact HYSET upstream heldout split paths")

    training = _object(m["training"], {
        "seed", "primary_configuration", "reward_cache_digest",
        "annotation_only_eta0_allowed_if_reward_cache_not_publicly_reproducible",
        "checkpoint_sha256",
    }, "training")
    if type(training["seed"]) is not int or training["seed"] != 42:
        raise ValueError("the declared baseline seed must remain 42")
    _literal_true(
        training["annotation_only_eta0_allowed_if_reward_cache_not_publicly_reproducible"],
        "annotation-only escape boundary",
    )
    governance = _object(m["governance"], {
        "paper_checkpoint_reproduction_claim_allowed", "heldout_tuning_allowed",
        "failed_training_and_oom_are_reportable_results", "frozen_before_scoring",
    }, "governance")
    _literal_false(
        governance["paper_checkpoint_reproduction_claim_allowed"], "paper checkpoint claim",
    )
    _literal_false(governance["heldout_tuning_allowed"], "heldout tuning")
    _literal_true(governance["failed_training_and_oom_are_reportable_results"], "negative results")
    if type(governance["frozen_before_scoring"]) is not bool:
        raise ValueError("freeze status must be an explicit boolean")

    if stage == "development":
        if m["status"] != "development_unfrozen":
            raise ValueError("development stage cannot be mislabeled frozen")
        _literal_false(governance["frozen_before_scoring"], "development freeze")
        if any(value is not None for value in (
            encoder["revision"], data["toolbench_source_revision"],
            data["toolbench_digest"], training["primary_configuration"],
            training["reward_cache_digest"], training["checkpoint_sha256"],
        )):
            raise ValueError("development stage must not masquerade as pinned training")
    else:
        if m["status"] != "frozen_pre_scoring":
            raise ValueError("training/evaluation requires an explicitly frozen manifest")
        _literal_true(governance["frozen_before_scoring"], "training freeze")
        _sha(encoder["revision"], 40, "public encoder exact revision")
        _sha(data["toolbench_source_revision"], 40, "ToolBench source revision")
        _sha(data["toolbench_digest"], 64, "ToolBench raw data")
        _training_configuration(training)
        if stage == "evaluation":
            _sha(training["checkpoint_sha256"], 64, "retrained checkpoint")
        elif training["checkpoint_sha256"] is not None:
            raise ValueError("training preflight must not claim an existing checkpoint")

    return {
        "stage": stage,
        "status": "DEVELOPMENT_UNSCORED" if stage == "development"
        else "STRUCTURAL_INPUTS_ONLY_NOT_EXTERNALLY_REVIEWED",
        "paper_checkpoint_reproduction_claim_allowed": False,
        "scoring_authorized": False,
        "independent_reviewer_approved": False,
        "native_hyset_execution_performed": False,
        "upstream_commit": upstream["commit"],
        "split_count": len(SPLITS),
        "limitations": [
            "No source-byte/dataset content authentication or third-party review.",
            "Validation cannot prove the ToolBench training/test split is disjoint.",
            "Passing input preflight does not authorize real scored evaluation.",
            "No claim of reproducing the paper's unavailable best.pt checkpoint.",
        ],
    }


def load_manifest(path: Path) -> Any:
    """Read untrusted JSON without silent duplicate-key or NaN acceptance."""
    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for name, value in pairs:
            if name in output:
                raise ValueError(f"duplicate HYSET manifest key: {name}")
            output[name] = value
        return output

    def reject_nonfinite_constant(value: str) -> None:
        raise ValueError(f"invalid nonfinite HYSET manifest constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_pairs,
        parse_constant=reject_nonfinite_constant,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=Path("benchmarks/external-validation-hyset-retrain-dev-v1/manifest.json"),
    )
    parser.add_argument(
        "--stage", choices=("development", "training", "evaluation"),
        default="development",
    )
    args = parser.parse_args()
    payload = load_manifest(args.manifest)
    print(json.dumps(validate_manifest(payload, stage=args.stage), indent=2))


if __name__ == "__main__":
    main()
