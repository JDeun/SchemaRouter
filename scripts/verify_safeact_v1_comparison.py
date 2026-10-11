"""Audit official SafeAct V1 comparison outputs after agent trajectories finish.

This is evaluator-side integrity checking, never a runtime evidence source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

CONDITIONS = (
    "SAFEACT-UNGATED",
    "SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE",
    "SAFEACT-SCHEMAROUTER-EVIDENCE-GATE",
)
REQUIRED = frozenset({
    "public_scenario", "raw_output", "trace",
    "normalized_record", "evaluation_record",
})


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def verify_artifacts(root: Path, marker: dict) -> None:
    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != REQUIRED:
        raise ValueError("incomplete official artifact list")
    for label, item in artifacts.items():
        if not isinstance(item, dict):
            raise ValueError(f"malformed artifact: {label}")
        name, checksum = item.get("path"), item.get("sha256")
        if not isinstance(name, str) or not isinstance(checksum, str):
            raise ValueError(f"missing artifact identity: {label}")
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or "." in rel.parts:
            raise ValueError(f"unsafe artifact path: {label}")
        target = root / rel
        if any(node.is_symlink() for node in (target, *target.parents)
               if node != root.parent and node != root.parent.parent):
            raise ValueError(f"symlink artifact: {label}")
        if not target.is_file() or not target.resolve().is_relative_to(root):
            raise ValueError(f"artifact missing/outside root: {label}")
        if hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
            raise ValueError(f"tampered official artifact: {label}")


def verify_comparison(
    outputs: Mapping[str, Path], *, expected_cases: int = 131,
) -> dict:
    if set(outputs) != set(CONDITIONS) or expected_cases < 1:
        raise ValueError("three preregistered conditions required")
    reference_cases: dict | None = None
    reference_dataset: tuple | None = None
    runtime_model: str | None = None
    success_rates: dict[str, float] = {}
    for condition in CONDITIONS:
        root = outputs[condition].resolve()
        summary = _json(root / "summary.json")
        if (summary.get("mode") != "external_agent"
                or summary.get("selected_protocols") != ["v1"]
                or not summary.get("agent_cmd")
                or summary.get("failures") != []
                or summary.get("reused_cases") != []
                or summary.get("deferred_cases") != []
                or summary.get("new_cases_run") != expected_cases):
            raise ValueError(f"incomplete or simulated run: {condition}")
        metrics = summary.get("metrics")
        if not isinstance(metrics, dict) or any(
            type(metrics.get(key)) is not int or metrics[key] != expected_cases
            for key in ("selected_cases", "scored_cases", "evaluated_cases")
        ):
            raise ValueError(f"unpaired official V1 coverage: {condition}")
        if metrics.get("harness_excluded_cases") != 0:
            raise ValueError(f"harness exclusions: {condition}")
        rate = metrics.get("strict_success_rate")
        if isinstance(rate, bool) or not isinstance(rate, (float, int)):
            raise ValueError(f"missing official metric: {condition}")
        if not 0 <= rate <= 1:
            raise ValueError(f"out-of-range official metric: {condition}")
        dataset = tuple(summary.get(key) for key in (
            "dataset_id", "dataset_version", "evaluation_contract",
        ))
        if not all(isinstance(v, str) and v for v in dataset):
            raise ValueError(f"missing evaluator identity: {condition}")
        if reference_dataset is not None and dataset != reference_dataset:
            raise ValueError("dataset/evaluator drift across conditions")
        reference_dataset = dataset
        files = sorted((root / "completions" / "v1").glob("*.json"))
        if len(files) != expected_cases:
            raise ValueError(f"V1 completion count mismatch: {condition}")
        cases: dict[str, tuple[str, str]] = {}
        for file in files:
            marker = _json(file)
            case = marker.get("case_id")
            if (marker.get("protocol") != "v1"
                    or marker.get("schema_version") != 1
                    or not isinstance(case, str)
                    or not case.startswith("SAB-V1-")
                    or file.stem != case or case in cases):
                raise ValueError(f"invalid official completion: {condition}")
            identity = marker.get("observed_runtime_identity")
            if (not isinstance(identity, dict)
                    or identity.get("fresh_session") is not True
                    or identity.get("session_persistence") != "ephemeral"
                    or not isinstance(identity.get("runtime_model"), str)
                    or not identity["runtime_model"]):
                raise ValueError(f"unattested agent session: {case}")
            if runtime_model is None:
                runtime_model = identity["runtime_model"]
            elif runtime_model != identity["runtime_model"]:
                raise ValueError(f"runtime model changed: {case}")
            inputs = marker.get("inputs")
            if not isinstance(inputs, dict):
                raise ValueError(f"missing frozen input identity: {case}")
            declared = inputs.get("runtime_identity")
            if (isinstance(declared, dict)
                    and declared.get("requested_model") not in (
                        None, runtime_model,
                    )):
                raise ValueError(f"model attestation mismatch: {case}")
            verify_artifacts(root, marker)
            artifacts = marker["artifacts"]
            scenario_hash = artifacts["public_scenario"]["sha256"]
            if marker.get("public_scenario_sha256") != scenario_hash:
                raise ValueError(f"public scenario fingerprint mismatch: {case}")
            trace = _json(root / artifacts["trace"]["path"])
            for key in ("runtime_model", "fresh_session", "session_persistence"):
                if trace.get(key) != identity.get(key):
                    raise ValueError(f"runtime trace attestation mismatch: {case}")
            cases[case] = (
                str(marker.get("public_scenario_sha256", "")),
                str(inputs.get("hidden_case_spec_sha256", "")),
            )
            if not all(cases[case]):
                raise ValueError(f"missing case fingerprint: {case}")
        if reference_cases is not None and cases != reference_cases:
            raise ValueError("different case set/source across conditions")
        reference_cases = cases
        success_rates[condition] = float(rate)
    return {
        "verification": "official-evaluator-postrun-only",
        "paired_cases": expected_cases,
        "attested_model": runtime_model,
        "official_strict_success_rate": success_rates,
        "not_measured_here": [
            "unsupported_execution_rate", "premature_action_attempt_rate",
            "false_refusal_rate",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for condition in CONDITIONS:
        parser.add_argument("--" + condition.lower(), required=True, type=Path)
    args = parser.parse_args()
    roots = {
        c: getattr(args, c.lower().replace("-", "_")) for c in CONDITIONS
    }
    print(json.dumps(verify_comparison(roots), indent=2))


if __name__ == "__main__":
    main()
