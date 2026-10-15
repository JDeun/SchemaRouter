"""Generate bounded, evidence-linked research configurations; never execute models.

This is the proposal stage of #1412, NOT an autonomous code writer, evaluator,
independent validation, or permission to merge the held v0.18 release.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "benchmarks/adaptive-routing-search-v1-policy.json"
SEED = ROOT / "benchmarks/adaptive-routing-search-v1-dev-seed.json"
MARKER = "<!-- schemarouter-adaptive-proposal-v1:"
END = " -->"
BOT = "github-actions[bot]"
SHA = re.compile(r"^[0-9a-f]{64}$")
DIMENSIONS = ("retriever", "encoder", "candidate_k", "operation_filter", "no_fit")
ALLOWED = {
    "retriever": ("dense", "hybrid_lexical_dense"),
    "encoder": ("multilingual_minilm", "multilingual_e5"),
    "candidate_k": (3, 5, 10),
    "operation_filter": ("host_only", "advisory_contrastive"),
    "no_fit": ("explicit_negative_veto", "calibrated_selective"),
}
FAILURES = ("supported_route_miss", "unsupported_false_accept",
            "wrong_operation", "supported_false_refusal")
TARGET = {
    "supported_tool_recall_min": 0.97,
    "unsupported_rejection_min": 0.99,
    "wrong_operation_rate_max": 0.01,
    "unauthorized_dispatch_max": 0,
    "selection_p95_ms_max": 250,
}


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def load_policy(path: Path = POLICY) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or set(doc) != {
        "schema_version", "id", "purpose", "experiment_issue",
        "search_space", "targets", "langs", "catalog_sizes",
        "max_new_proposals_per_wave", "max_pending_proposals",
        "qualification", "execution",
    }:
        raise ValueError("unrecognized adaptive research policy")
    if (type(doc["schema_version"]) is not int or doc["schema_version"] != 1
        or doc["id"] != "adaptive-routing-search-v1"
        or doc["purpose"] != "research_proposal_only"
        or doc["experiment_issue"] != 1412
        or doc["targets"] != TARGET
        or doc["langs"] != ["en", "ko", "ja"]
        or doc["catalog_sizes"] != [100, 250, 500]
        or doc["max_new_proposals_per_wave"] != 1
        or doc["max_pending_proposals"] != 2
        or doc["qualification"] != "independent_disjoint_required"
        or doc["execution"] != "no_model_or_tools_or_release"
        or not isinstance(doc["search_space"], dict)
        or set(doc["search_space"]) != set(DIMENSIONS)):
        raise ValueError("policy attempts authority/measurement escalation")
    for key in DIMENSIONS:
        if (type(doc["search_space"][key]) is not list
            or tuple(doc["search_space"][key]) != ALLOWED[key]):
            raise ValueError(f"unreviewed experiment grammar: {key}")
    return doc


def load_evidence(path: Path = SEED) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or set(doc) != {
        "schema_version", "split", "source", "corpus_sha256",
        "run_ids", "failure_counts", "source_class",
        "independent_qualification",
    }:
        raise ValueError("malformed research evidence")
    if (type(doc["schema_version"]) is not int or doc["schema_version"] != 1
        or doc["split"] != "development"
        or doc["source_class"] != "previously_observed_DEV_only"
        or doc["independent_qualification"] is not False
        or not isinstance(doc["source"], str)
        or not doc["source"].startswith("https://github.com/JDeun/SchemaRouter/")
        or not isinstance(doc["corpus_sha256"], str)
        or SHA.fullmatch(doc["corpus_sha256"]) is None
        or not isinstance(doc["run_ids"], list)
        or not doc["run_ids"]
        or len(doc["run_ids"]) != len(set(map(str, doc["run_ids"])))
        or any(type(i) is not int or i <= 0 for i in doc["run_ids"])
        or not isinstance(doc["failure_counts"], dict)
        or set(doc["failure_counts"]) != set(FAILURES)
        or any(type(doc["failure_counts"][k]) is not int
               or not 0 <= doc["failure_counts"][k] <= 1000000
               for k in FAILURES)):
        raise ValueError("unverifiable/unsafe DEV evidence")
    return doc


def proposals_from_comments(comments: Any) -> set[str]:
    """Only bot-issued, canonical proposal receipts count as queued work."""
    if not isinstance(comments, list):
        raise ValueError("expected GitHub paginated issue comments")
    found: set[str] = set()
    for page in comments:
        rows = page if isinstance(page, list) else [page]
        for comment in rows:
            if not isinstance(comment, dict):
                raise ValueError("invalid issue comment")
            user = comment.get("user")
            if not isinstance(user, dict) or user.get("login") != BOT:
                continue
            body = comment.get("body", "")
            if not isinstance(body, str):
                continue
            for line in body.splitlines():
                if not (line.startswith(MARKER) and line.endswith(END)):
                    continue
                try:
                    obj = json.loads(line[len(MARKER):-len(END)])
                except json.JSONDecodeError:
                    raise ValueError("invalid bot proposal receipt") from None
                if (not isinstance(obj, dict)
                    or set(obj) != {"config_sha256", "status", "issue"}
                    or obj["status"] != "PROPOSED_UNMEASURED"
                    or type(obj["issue"]) is not int or obj["issue"] != 1412
                    or not isinstance(obj["config_sha256"], str)
                    or SHA.fullmatch(obj["config_sha256"]) is None):
                    raise ValueError("invalid bot proposal authority/identity")
                found.add(obj["config_sha256"])
    return found


def candidate_configs(policy: dict[str, Any]):
    grammar = policy["search_space"]
    for values in itertools.product(*(grammar[key] for key in DIMENSIONS)):
        candidate = dict(zip(DIMENSIONS, values))
        # A learned operation filter remains advisory; host policy never changes.
        yield candidate


def priority(config: dict[str, Any], evidence: dict[str, Any]) -> tuple[int, int, int]:
    errors = evidence["failure_counts"]
    score = 0
    if config["retriever"] == "hybrid_lexical_dense":
        score += errors["supported_route_miss"] * 2
    if config["candidate_k"] == 10:
        score += errors["supported_route_miss"]
        score -= errors["unsupported_false_accept"]
    if config["candidate_k"] == 5:
        score += errors["supported_route_miss"] // 2
    if config["operation_filter"] == "advisory_contrastive":
        score += errors["wrong_operation"] * 2
    if config["no_fit"] == "explicit_negative_veto":
        score += errors["unsupported_false_accept"] * 2
    else:
        score += errors["supported_false_refusal"] * 2
    # These are hypothesis search priorities, never predicted quality scores.
    # Prefer the lower-complexity architecture at identical priority.
    complexity = (config["candidate_k"]
                  + (3 if config["retriever"] == "hybrid_lexical_dense" else 0)
                  + (2 if config["operation_filter"] != "host_only" else 0))
    return (-score, complexity, 0 if config["encoder"] == "multilingual_e5" else 1)


def make_proposal(policy: dict[str, Any], evidence: dict[str, Any],
                  seen: set[str]) -> dict[str, Any]:
    if len(seen) >= policy["max_pending_proposals"]:
        return {
            "status": "PAUSED_UNMEASURED_PROPOSALS",
            "pending_count": len(seen), "new_proposals": [],
            "may_score": False, "may_promote": False, "may_release": False,
        }
    source_identity = {
        "split": evidence["split"], "corpus_sha256": evidence["corpus_sha256"],
        "run_ids": evidence["run_ids"],
    }
    possibilities = sorted(
        candidate_configs(policy),
        key=lambda c: (*priority(c, evidence), digest(c)),
    )
    proposed: list[dict[str, Any]] = []
    for config in possibilities:
        # Stable config identity permits genuinely automatic combination
        # of approved operators; no hand-enumerated three experiment IDs.
        cfg_hash = digest({"grammar": policy["id"], "config": config})
        if cfg_hash in seen:
            continue
        proposed.append({
            "config": config,
            "config_sha256": cfg_hash,
            "basis": source_identity,
            "hypothesis_only": True,
            "experiment_status": "PROPOSED_UNMEASURED",
            "executor": "REVIEW_AND_REGISTER_PINNED_EXECUTOR",
            "required_next_stage": "NEW_DISJOINT_DEV_AND_REGISTERED_RUNNER",
            "required_final_stage": "BLINDED_INDEPENDENT_AGENT_EVALUATION",
        })
        if len(proposed) >= policy["max_new_proposals_per_wave"]:
            break
    status = "NEW_RESEARCH_PROPOSAL" if proposed else "SEARCH_GRAMMAR_EXHAUSTED"
    return {
        "status": status, "policy": policy["id"],
        "evidence_sha256": digest(evidence),
        "target_constraints": policy["targets"],
        "search_space_count": len(possibilities),
        "pending_count": len(seen),
        "new_proposals": proposed,
        "may_score": False, "may_promote": False, "may_release": False,
    }


def issue_comment(report: dict[str, Any]) -> str:
    if report["status"] != "NEW_RESEARCH_PROPOSAL":
        raise ValueError("no research proposal to comment")
    proposal, = report["new_proposals"]
    receipt = {
        "config_sha256": proposal["config_sha256"],
        "status": "PROPOSED_UNMEASURED", "issue": 1412,
    }
    return (
        "### Adaptive multilingual routing: automatically generated research proposal\n\n"
        "Objective: find a commercially viable quality/safety/latency Pareto point, "
        "not only demonstrate improvement on visible DEV data.\n\n"
        f"Generated config: `{json.dumps(proposal['config'], sort_keys=True)}`\n\n"
        f"Configuration SHA-256: `{proposal['config_sha256']}`\n"
        f"DEV evidence identity: `{report['evidence_sha256']}`\n\n"
        "**Status: PROPOSED, NOT RUN.** A source-pinned backend executor and "
        "new disjoint DEV data are not yet registered for this combination. "
        "No independent result, model authorization, automatic code modification, "
        "tool invocation, or v0.18 release permission is implied. More automatic "
        "proposals pause after the pending budget until measured evidence is linked.\n\n"
        f"{MARKER}{json.dumps(receipt, sort_keys=True, separators=(',', ':'))}{END}\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", type=Path, default=POLICY)
    ap.add_argument("--evidence", type=Path, default=SEED)
    ap.add_argument("--comments", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--comment-output", type=Path)
    args = ap.parse_args()
    report = make_proposal(
        load_policy(args.policy), load_evidence(args.evidence),
        proposals_from_comments(json.loads(args.comments.read_text(encoding="utf-8"))),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)
                           + "\n", encoding="utf-8")
    if report["status"] == "NEW_RESEARCH_PROPOSAL" and args.comment_output:
        args.comment_output.write_text(issue_comment(report), encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "new": len(report["new_proposals"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
