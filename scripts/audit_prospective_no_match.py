"""Unscored prospective diagnostic of an externally fixed opt-in no-match gate.

Never derives thresholds from labels, executes tools, modifies retrieval defaults,
or certifies independent test provenance. Existing visible DEV IDs/queries are
explicitly excluded when supplied as required CLI inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from schemarouter import (
    CapabilityRetrieval,
    RetrievalAbstentionPolicy,
    apply_retrieval_abstention,
)


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def exact(obj: Any, keys: set[str], label: str) -> dict:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ValueError(f"{label}: unknown or missing fields")
    return obj


def sha(value: Any, label: str) -> None:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError(f"{label}: lowercase sha256 required")


def usable_ms(value: Any) -> float:
    if (
        isinstance(value, bool) or not isinstance(value, (float, int))
        or not math.isfinite(value) or value < 0
    ):
        raise ValueError("observed latency must be finite and nonnegative")
    return float(value)


def audit(plan: Any, cases: Any, observations: Any, known_dev: list[Any]) -> dict:
    p = exact(plan, {
        "schema_version", "status", "approved", "source_sha",
        "scorer_sha", "registry_sha256", "case_sha256", "policy", "top_k",
    }, "plan")
    if (
        type(p["schema_version"]) is not int or p["schema_version"] != 1
        or p["status"] != "unscored_prospective_draft"
        or p["approved"] is not False
    ):
        raise ValueError("this instrument accepts only unapproved draft plans")
    for key, digits in (("source_sha", 40), ("scorer_sha", 40),
                        ("registry_sha256", 64)):
        value = p[key]
        if (
            not isinstance(value, str) or len(value) != digits
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError(f"malformed {key}")
    if type(p["top_k"]) is not int or p["top_k"] < 2:
        raise ValueError("top_k >= 2 required for explicit margin evidence")
    policy = RetrievalAbstentionPolicy.model_validate(p["policy"])
    sha(p["case_sha256"], "case SHA")

    c = exact(cases, {"schema_version", "role", "cases"}, "case cohort")
    if c["schema_version"] != 1 or c["role"] != "prospective_unreviewed":
        raise ValueError("prospective, unreviewed source only")
    if canonical_sha(c) != p["case_sha256"]:
        raise ValueError("case cohort digest mismatch")
    entries = c["cases"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("nonempty prospective case cohort required")
    banned_ids: set[str] = set()
    banned_queries: set[str] = set()
    if len(known_dev) != 2:
        raise ValueError("exactly two frozen historical DEV case files required")
    for fixture in known_dev:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("cases"), list):
            raise ValueError("malformed historical DEV case file")
        for old in fixture["cases"]:
            banned_ids.add(old["id"])
            banned_queries.add(hashlib.sha256(
                old["query"].strip().casefold().encode("utf-8")
            ).hexdigest())
    labels: dict[str, dict] = {}
    query_hashes: set[str] = set()
    for row in entries:
        item = exact(row, {
            "id", "label", "query_sha256", "expected_routes", "forbidden_routes",
        }, "prospective case")
        ident = item["id"]
        if not isinstance(ident, str) or not ident or ident in labels:
            raise ValueError("duplicate/invalid prospective case ID")
        sha(item["query_sha256"], "query SHA")
        if ident in banned_ids or item["query_sha256"] in banned_queries:
            raise ValueError("reused known visible DEV case or query")
        if item["query_sha256"] in query_hashes:
            raise ValueError("duplicate prospective query")
        query_hashes.add(item["query_sha256"])
        label = item["label"]
        if label not in ("supported", "unsupported", "ambiguous", "forbidden"):
            raise ValueError("unknown open-set case label")
        targets = item["expected_routes"]
        forbidden = item["forbidden_routes"]
        if (
            not isinstance(targets, list) or not isinstance(forbidden, list)
            or any(not isinstance(x, str) or not x for x in targets + forbidden)
            or len(set(targets)) != len(targets)
            or len(set(forbidden)) != len(forbidden)
            or set(targets) & set(forbidden)
            or (label in ("supported", "ambiguous") and not targets)
            or (label in ("unsupported", "forbidden") and targets)
            or (label == "forbidden" and not forbidden)
        ):
            raise ValueError("invalid case route labels")
        labels[ident] = item

    obs = exact(observations, {
        "schema_version", "plan_sha256", "case_sha256", "rows",
    }, "observations")
    if (
        obs["schema_version"] != 1 or obs["plan_sha256"] != canonical_sha(p)
        or obs["case_sha256"] != p["case_sha256"]
    ):
        raise ValueError("observations not pinned to fixed plan and cohort")
    if not isinstance(obs["rows"], list) or len(obs["rows"]) != len(labels):
        raise ValueError("missing or extra prospective observations")

    metrics = {key: 0 for key in (
        "supported", "supported_raw_hit", "supported_selected_hit",
        "supported_false_refusal", "unsupported", "unsupported_raw_nonempty",
        "unsupported_selected_nonempty", "ambiguous", "ambiguous_selected_hit",
        "forbidden", "forbidden_selected_exposure", "abstained",
    )}
    seen: set[str] = set()
    before_bytes: list[int] = []
    after_bytes: list[int] = []
    supplied_latencies: list[float] = []
    records = []
    for row in obs["rows"]:
        r = exact(row, {"id", "retrieval", "retrieval_ms"}, "observed row")
        ident = r["id"]
        if not isinstance(ident, str) or ident not in labels or ident in seen:
            raise ValueError("unknown or duplicate observed case")
        seen.add(ident)
        latency = usable_ms(r["retrieval_ms"])
        raw = CapabilityRetrieval.model_validate(r["retrieval"])
        if raw.requested_k != p["top_k"]:
            raise ValueError("non-frozen requested Top-K")
        query_digest = hashlib.sha256(
            raw.query.strip().casefold().encode("utf-8")
        ).hexdigest()
        if query_digest != labels[ident]["query_sha256"]:
            raise ValueError("observed query not identical to prospective case")
        decision = apply_retrieval_abstention(raw, policy=policy)
        old = {x.route_id for x in raw.candidates}
        new = {x.route_id for x in decision.candidates}
        assert new <= old
        label = labels[ident]["label"]
        targets = set(labels[ident]["expected_routes"])
        denied = set(labels[ident]["forbidden_routes"])
        metrics[label] += 1
        metrics["abstained"] += int(decision.abstained)
        if label == "supported":
            was_hit = bool(old & targets)
            metrics["supported_raw_hit"] += int(was_hit)
            metrics["supported_selected_hit"] += int(bool(new & targets))
            metrics["supported_false_refusal"] += int(was_hit and decision.abstained)
        elif label == "unsupported":
            metrics["unsupported_raw_nonempty"] += int(bool(old))
            metrics["unsupported_selected_nonempty"] += int(bool(new))
        elif label == "ambiguous":
            metrics["ambiguous_selected_hit"] += int(bool(new & targets))
        else:
            metrics["forbidden_selected_exposure"] += int(bool(new & denied))
        before = len(json.dumps(
            [x.model_dump(mode="json") for x in raw.candidates],
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8"))
        after = len(json.dumps(
            [x.model_dump(mode="json") for x in decision.candidates],
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8"))
        before_bytes.append(before)
        after_bytes.append(after)
        supplied_latencies.append(latency)
        records.append({
            "id": ident, "label": label, "disposition": decision.disposition,
            "reason": decision.reason, "raw_count": len(old),
            "selected_count": len(new),
        })
    if seen != set(labels):
        raise ValueError("incomplete prospective result set")
    ordered = sorted(supplied_latencies)
    return {
        "status": "UNSCORED_NOT_INDEPENDENTLY_VERIFIED",
        "approved": False,
        "plan_sha256": canonical_sha(p),
        "case_sha256": p["case_sha256"],
        "count": len(records),
        "counts": metrics,
        "mean_candidate_metadata_bytes_before": statistics.mean(before_bytes),
        "mean_candidate_metadata_bytes_after": statistics.mean(after_bytes),
        "supplied_retrieval_latency_ms_p50": statistics.median(ordered),
        "supplied_retrieval_latency_ms_p95": ordered[
            math.ceil(0.95 * len(ordered)) - 1
        ],
        "per_case": records,
        "limitations": [
            "No independently authenticated source, authorship or labels.",
            "Input timings are not authenticated; no abstention latency measured.",
            "Metadata bytes are JSON candidate objects, not REST/MCP wire bytes.",
            "Ranking abstention is not an execution permission/denial policy.",
            "Policy is externally supplied, never tuned by this checker.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--observations", type=Path, required=True)
    p.add_argument("--known-dev", type=Path, action="append", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    def read(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
    result = audit(
        read(args.plan), read(args.cases), read(args.observations),
        [read(path) for path in args.known_dev],
    )
    if args.out.exists():
        p.error("never overwrite a prospective diagnostic")
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"UNSCORED: audited {result['count']} candidate records; "
          "no actual independent confirmation")


if __name__ == "__main__":
    main()
