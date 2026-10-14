"""Validate v0.18 external-evidence inventory without initiating a benchmark.

This is a local publication/readiness guard, not a scorer, independent reviewer,
source authenticator, or license to claim external performance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "v018-external-evidence-status.json"
)
LOCAL_VERDICTS = {"PASS", "VALID_NEGATIVE", "INFRA_INVALID", "NOT_COMPARABLE"}
EXTERNAL_VERDICTS = {
    "PASS", "VALID_NEGATIVE", "INFRA_INVALID", "BLOCKED_EXTERNAL", "NOT_COMPARABLE"
}
EVIDENCE_CLASSES = {
    "SOURCE_VERIFIED_DEV_ONLY",
    "NATIVE_SCHEMA_DEV_ONLY",
    "NATIVE_DEV_ONLY",
    "COMPONENT_OR_LOOPBACK_PREFLIGHT_ONLY",
    "UNSCORED_INPUT_PREFLIGHT_ONLY",
    "UNSCORED_PREFLIGHT_ONLY",
    "SYNTHETIC_CONTRACT_ONLY",
    "MOCKED_TRANSPORT_ONLY",
}


def validate(report: dict[str, Any]) -> None:
    if type(report) is not dict or type(report.get("schema_version")) is not int:
        raise ValueError("invalid evidence manifest envelope")
    if report["schema_version"] != 1 or report.get("release_target") != "0.18.0":
        raise ValueError("unexpected schema or release target")
    if report.get("historical_frozen_runs_unchanged") is not True:
        raise ValueError("cannot rewrite frozen benchmark history")
    if not isinstance(report.get("as_of"), str) or not report["as_of"]:
        raise ValueError("missing observation date")
    rows = report.get("suite")
    if not isinstance(rows, list) or len(rows) < 7:
        raise ValueError("expected complete external evidence inventory")
    ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("benchmark row must be an object")
        ident = row.get("id")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("duplicate or missing suite ID")
        ids.add(ident)
        if type(row.get("issue")) is not int or row["issue"] < 1:
            raise ValueError(f"{ident}: missing issue provenance")
        for field in ("source", "blocker", "permitted_claim"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{ident}: missing {field}")
        if row.get("evidence_class") not in EVIDENCE_CLASSES:
            raise ValueError(f"{ident}: unrecognized evidence class")
        if row.get("local_verdict") not in LOCAL_VERDICTS:
            raise ValueError(f"{ident}: malformed DEV/preflight verdict")
        decision = row.get("independent_verdict")
        if decision not in EXTERNAL_VERDICTS:
            raise ValueError(f"{ident}: unrecognized external verdict")
        run_id = row.get("run_id")
        run_url = row.get("run_url")
        if run_id is None:
            if run_url is not None:
                raise ValueError(f"{ident}: URL with no verified run")
        else:
            if type(run_id) is not int or run_id < 1:
                raise ValueError(f"{ident}: invalid run ID")
            expected_url = (
                "https://github.com/JDeun/SchemaRouter/actions/runs/" + str(run_id)
            )
            if run_url != expected_url:
                raise ValueError(f"{ident}: run URL does not match run ID")
        if row["local_verdict"] in {"PASS", "VALID_NEGATIVE"} and run_id is None:
            raise ValueError(f"{ident}: local DEV result needs a verified run")
        artifact_id = row.get("artifact_id")
        artifact_sha = row.get("artifact_sha256")
        if (artifact_id is None) != (artifact_sha is None):
            raise ValueError(f"{ident}: artifact ID and digest must both be set")
        if artifact_id is not None:
            if type(artifact_id) is not int or artifact_id < 1 or run_id is None:
                raise ValueError(f"{ident}: invalid artifact provenance")
            if (
                not isinstance(artifact_sha, str)
                or len(artifact_sha) != 64
                or any(c not in "0123456789abcdef" for c in artifact_sha)
            ):
                raise ValueError(f"{ident}: invalid artifact SHA-256")
        if decision in {"PASS", "VALID_NEGATIVE"}:
            # Explicitly do not accept a DEV/preflight SHA or run as independent.
            for field in (
                "independent_run_id", "independent_artifact_sha256",
                "independent_case_sha256", "independent_gold_review",
            ):
                value = row.get(field)
                if value is None or type(value) is bool or not value:
                    raise ValueError(
                        f"{ident}: external verdict requires {field}"
                    )
            if type(row["independent_run_id"]) is not int:
                raise ValueError(f"{ident}: independent run must be an integer")
            for field in ("independent_artifact_sha256", "independent_case_sha256"):
                digest = row[field]
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)
                ):
                    raise ValueError(f"{ident}: invalid independent digest")
            if row["independent_gold_review"] is not True:
                raise ValueError(f"{ident}: no independent signed gold review")
        if decision == "BLOCKED_EXTERNAL" and not row["blocker"].strip():
            raise ValueError(f"{ident}: blocked claim has no dependency")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    try:
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit("invalid external evidence manifest") from exc
    validate(payload)
    print(
        f"External readiness rows verified: {len(payload['suite'])}; "
        "DEV/preflight evidence is not independent confirmation."
    )


if __name__ == "__main__":
    main()
