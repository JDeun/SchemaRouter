"""Unscored, fail-closed preregistration and blinding preflight for SafeAct V1 repeats.

This checker never authorizes an experiment, imports the official scorer,
reads evaluator/gold files or runs a model. It validates public cohort IDs only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from itertools import product
from pathlib import Path
from typing import Any

ARMS = (
    "SAFEACT-UNGATED",
    "SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE",
    "SAFEACT-SCHEMAROUTER-EVIDENCE-GATE",
)
UPSTREAM_V1 = "841816cf1e376e6fbf8600cffac5df1736e1d369"
REQUIRED_METHODS = {
    "precision_rationale", "session_reset", "retry_policy",
    "missingness_policy", "randomness_policy", "blinding_limitations",
}


def digest(value: Any) -> str:
    """Canonical digest, with nonfinite JSON values disallowed."""
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def exact(value: Any, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label}: missing or unknown keys")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label}: nonempty normalized text required")
    return value


def hex_digest(value: Any, digits: int, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(
        rf"[0-9a-f]{{{digits}}}", value
    ) is None:
        raise ValueError(f"{label}: lowercase {digits}-digit hex required")


def validate_plan(plan: Any, public_case_ids: Any) -> int:
    """Validate design completeness, not independent review or approval."""
    if (
        not isinstance(public_case_ids, list)
        or len(public_case_ids) != 131
        or any(not isinstance(i, str) or not i.strip() or i != i.strip()
               for i in public_case_ids)
        or len(set(public_case_ids)) != 131
    ):
        raise ValueError("public cohort must contain 131 distinct public V1 IDs")
    p = exact(plan, {
        "schema_version", "study", "status", "approved", "pins",
        "arms", "seeds", "repetitions", "analysis", "methods",
    }, "preregistration")
    if (
        (not isinstance(p["schema_version"], int)
            or isinstance(p["schema_version"], bool))
        or p["schema_version"] != 1
        or p["study"] != "safeact-v1-repeated-trajectory"
        or p["status"] != "draft" or p["approved"] is not False
    ):
        raise ValueError("only unapproved V1 repeated-study drafts are accepted")
    pins = exact(p["pins"], {
        "upstream_sha", "model", "model_revision", "adapter_sha",
        "contracts_sha256", "runtime_sha256", "rubric_sha256",
        "public_cases_sha256",
    }, "identity pins")
    if pins["upstream_sha"] != UPSTREAM_V1:
        raise ValueError("pinned official SafeAct V1 revision differs")
    hex_digest(pins["adapter_sha"], 40, "adapter_sha")
    for name in ("contracts_sha256", "runtime_sha256", "rubric_sha256",
                 "public_cases_sha256"):
        hex_digest(pins[name], 64, name)
    text(pins["model"], "model")
    text(pins["model_revision"], "model revision")
    if pins["public_cases_sha256"] != digest(sorted(public_case_ids)):
        raise ValueError("public cohort digest mismatch")
    if p["arms"] != list(ARMS):
        raise ValueError("exactly the three predefined arms in fixed order required")
    seeds = p["seeds"]
    if (
        not isinstance(seeds, list) or len(seeds) < 2
        or any(not isinstance(s, str) or not s.strip()
               or s != s.strip() for s in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("at least two distinct preregistered seed IDs required")
    if (not isinstance(p["repetitions"], int)
            or isinstance(p["repetitions"], bool)
            or p["repetitions"] != len(seeds)):
        raise ValueError("repetition count must exactly match registered seeds")
    analysis = exact(p["analysis"], {
        "cluster_unit", "annotation_sample", "annotators_per_item",
    }, "analysis")
    if (
        analysis["cluster_unit"] != "case_id"
        or analysis["annotation_sample"] != "all"
        or not isinstance(analysis["annotators_per_item"], int)
        or isinstance(analysis["annotators_per_item"], bool)
        or analysis["annotators_per_item"] < 2
    ):
        raise ValueError("require all-trajectory, >=2-rater case-clustered analysis")
    methods = exact(p["methods"], REQUIRED_METHODS, "methods")
    for name, value in methods.items():
        text(value, name)
    return 131 * len(seeds) * len(ARMS)


def audit_schedule(plan: Any, public_case_ids: Any, schedule: Any) -> int:
    expected_count = validate_plan(plan, public_case_ids)
    doc = exact(schedule, {"schema_version", "plan_sha256", "runs"}, "schedule")
    if doc["schema_version"] != 1 or doc["plan_sha256"] != digest(plan):
        raise ValueError("schedule not pinned to exact preregistration")
    rows = doc["runs"]
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError("missing, extra or duplicated scheduled trajectories")
    valid = set(product(public_case_ids, plan["seeds"], ARMS))
    seen: set[tuple[str, str, str]] = set()
    executions: set[str] = set()
    sessions: set[str] = set()
    for row in rows:
        item = exact(row, {
            "case_id", "seed_id", "arm", "execution_id", "session_id",
        }, "run")
        triple = (
            text(item["case_id"], "case_id"),
            text(item["seed_id"], "seed_id"),
            text(item["arm"], "arm"),
        )
        execution = text(item["execution_id"], "execution_id")
        session = text(item["session_id"], "session_id")
        if triple not in valid or triple in seen:
            raise ValueError("unknown or duplicated paired case/seed/arm")
        if execution in executions or session in sessions:
            raise ValueError("execution/session reused across arm or repetition")
        seen.add(triple)
        executions.add(execution)
        sessions.add(session)
    if seen != valid:
        raise ValueError("missing complete matched case/seed/arm triples")
    return len(rows)


def make_blind_queue(
    plan: dict, public_case_ids: list[str], schedule: dict,
) -> tuple[dict, dict]:
    """Produce separate reviewer-safe identifiers and private provenance.

    The actual trajectory renderer MUST independently remove identifying
    tool/event/condition markers. This only blinds the indexing metadata.
    """
    audit_schedule(plan, public_case_ids, schedule)
    shuffled = list(schedule["runs"])
    secrets.SystemRandom().shuffle(shuffled)
    entries = []
    private = []
    for run in shuffled:
        blind_id = secrets.token_hex(16)
        entries.append({"blind_id": blind_id})
        private.append({"blind_id": blind_id, **run})
    info = {"schema_version": 1, "plan_sha256": digest(plan)}
    return (
        {**info, "entries": entries},
        {**info, "entries": private},
    )



def audit_blind_linkage(
    plan: dict, public_case_ids: list[str], schedule: dict,
    reviewer_queue: Any, private_linkage: Any,
) -> int:
    """Prove reviewer IDs are a bijective reindexing of frozen executions."""
    size = audit_schedule(plan, public_case_ids, schedule)
    required = {"schema_version", "plan_sha256", "entries"}
    public = exact(reviewer_queue, required, "reviewer queue")
    private = exact(private_linkage, required, "private linkage")
    for doc in (public, private):
        if doc["schema_version"] != 1 or doc["plan_sha256"] != digest(plan):
            raise ValueError("blinded metadata revision does not match plan")
        if not isinstance(doc["entries"], list) or len(doc["entries"]) != size:
            raise ValueError("incomplete blind-index coverage")
    public_ids = []
    for row in public["entries"]:
        value = exact(row, {"blind_id"}, "public blind entry")
        public_ids.append(text(value["blind_id"], "blind ID"))
    public_ids_set = set(public_ids)
    if len(public_ids_set) != size:
        raise ValueError("duplicate or absent public blind IDs")
    expected = {row["execution_id"]: row for row in schedule["runs"]}
    bound: set[str] = set()
    executions: set[str] = set()
    for row in private["entries"]:
        info = exact(row, {
            "blind_id", "execution_id", "session_id",
            "case_id", "seed_id", "arm",
        }, "private blind link")
        blind_id = text(info["blind_id"], "private blind ID")
        execution = text(info["execution_id"], "private execution ID")
        if blind_id not in public_ids_set or blind_id in bound:
            raise ValueError("private linkage has unknown or duplicate blind ID")
        if execution not in expected or execution in executions:
            raise ValueError("private linkage reuses or invents an execution")
        if {k: v for k, v in info.items() if k != "blind_id"} != expected[execution]:
            raise ValueError("private linkage does not match frozen schedule")
        bound.add(blind_id)
        executions.add(execution)
    if bound != public_ids_set or executions != set(expected):
        raise ValueError("private linkage is not a one-to-one schedule mapping")
    return size


def audit_annotations(plan: dict, queue: Any, annotations: Any) -> int:
    """Validate independent assignment coverage without reading annotations."""
    q = exact(queue, {"schema_version", "plan_sha256", "entries"}, "blind queue")
    a = exact(annotations, {"schema_version", "plan_sha256", "items"}, "annotations")
    if (
        q["schema_version"] != 1 or a["schema_version"] != 1
        or q["plan_sha256"] != digest(plan)
        or a["plan_sha256"] != digest(plan)
    ):
        raise ValueError("annotation/queue not pinned to exact plan")
    if not isinstance(q["entries"], list) or not isinstance(a["items"], list):
        raise ValueError("blind queue and annotations must be lists")
    ids = []
    for entry in q["entries"]:
        ids.append(text(exact(entry, {"blind_id"}, "blind entry")["blind_id"], "blind_id"))
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate reviewer blind identifiers")
    required = plan["analysis"]["annotators_per_item"]
    if len(ids) != 131 * plan["repetitions"] * len(ARMS):
        raise ValueError("blind queue lacks registered schedule coverage")
    reviewers: dict[str, set[str]] = {key: set() for key in ids}
    for item in a["items"]:
        row = exact(item, {
            "blind_id", "annotator_id", "decision_sha256",
        }, "annotation assignment")
        blind_id = text(row["blind_id"], "blind_id")
        reviewer = text(row["annotator_id"], "annotator_id")
        hex_digest(row["decision_sha256"], 64, "annotation digest")
        if blind_id not in reviewers:
            raise ValueError("unknown blind identifier in annotations")
        if reviewer in reviewers[blind_id]:
            raise ValueError("same annotator repeated for one blinded trajectory")
        reviewers[blind_id].add(reviewer)
    if any(len(people) < required for people in reviewers.values()):
        raise ValueError("incomplete independently annotated trajectory coverage")
    return len(reviewers)



def audit_receipts(
    plan: dict, public_case_ids: list[str], schedule: dict, receipts: Any,
) -> dict[str, int]:
    """Check pre-aggregate identity/missingness, never outcome scores.

    An artifact SHA shape is not proof of actual contents: the trusted runner
    must check every artifact byte and observed runtime identity separately.
    """
    audit_schedule(plan, public_case_ids, schedule)
    doc = exact(receipts, {"schema_version", "plan_sha256", "runs"}, "receipts")
    if doc["schema_version"] != 1 or doc["plan_sha256"] != digest(plan):
        raise ValueError("receipts not pinned to exact preregistration")
    rows = doc["runs"]
    if not isinstance(rows, list) or len(rows) != len(schedule["runs"]):
        raise ValueError("receipts missing an intention-to-treat execution")
    expected = {row["execution_id"]: row["session_id"] for row in schedule["runs"]}
    visited: set[str] = set()
    totals = {"completed": 0, "missing": 0, "infra_failed": 0}
    for row in rows:
        entry = exact(row, {
            "execution_id", "session_id", "state", "artifact_sha256",
        }, "execution receipt")
        execution = text(entry["execution_id"], "receipt execution")
        if execution not in expected or execution in visited:
            raise ValueError("unknown or duplicated execution receipt")
        if entry["session_id"] != expected[execution]:
            raise ValueError("receipt session differs from registered isolation")
        state = entry["state"]
        if not isinstance(state, str) or state not in totals:
            raise ValueError("unknown receipt state, do not infer scored outcome")
        if state == "completed":
            hex_digest(entry["artifact_sha256"], 64, "completed artifact")
        elif entry["artifact_sha256"] is not None:
            raise ValueError("missing/infra-failed receipt cannot claim artifact")
        totals[state] += 1
        visited.add(execution)
    if visited != set(expected):
        raise ValueError("scheduled execution has no receipt")
    return totals


def write_new_private_file(path: Path, data: dict) -> None:
    """Never overwrite review/linkage evidence or follow a preexisting symlink."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--public-case-ids", required=True, type=Path)
    parser.add_argument("--schedule", required=True, type=Path)
    parser.add_argument("--blind-queue-out", type=Path)
    parser.add_argument("--private-linkage-out", type=Path)
    parser.add_argument("--blind-queue-in", type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--private-linkage-in", type=Path)
    parser.add_argument("--receipts", type=Path)
    args = parser.parse_args()
    if bool(args.blind_queue_out) != bool(args.private_linkage_out):
        parser.error("blind queue and private linkage outputs must be supplied together")
    if bool(args.blind_queue_in) != bool(args.annotations or args.private_linkage_in):
        parser.error("annotation/linkage audit requires a blind queue input")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    public_ids = json.loads(args.public_case_ids.read_text(encoding="utf-8"))
    schedule = json.loads(args.schedule.read_text(encoding="utf-8"))
    size = audit_schedule(plan, public_ids, schedule)
    if args.receipts:
        receipt_doc = json.loads(args.receipts.read_text(encoding="utf-8"))
        print("UNSCORED receipt counts:", audit_receipts(
            plan, public_ids, schedule, receipt_doc,
        ))
    if args.blind_queue_out:
        if args.blind_queue_out.parent.resolve() == args.private_linkage_out.parent.resolve():
            parser.error("public queue and private linkage require separate directories")
        if args.blind_queue_out.exists() or args.private_linkage_out.exists():
            parser.error("refusing to overwrite any blinded provenance file")
        public, private = make_blind_queue(plan, public_ids, schedule)
        write_new_private_file(args.private_linkage_out, private)
        write_new_private_file(args.blind_queue_out, public)
    if args.blind_queue_in:
        queue = json.loads(args.blind_queue_in.read_text(encoding="utf-8"))
        if args.private_linkage_in:
            link = json.loads(args.private_linkage_in.read_text(encoding="utf-8"))
            audit_blind_linkage(plan, public_ids, schedule, queue, link)
        if args.annotations:
            items = json.loads(args.annotations.read_text(encoding="utf-8"))
            audit_annotations(plan, queue, items)
    print(f"UNSCORED V1 repetition integrity OK: {size} planned trajectories; "
          "no model launch or review approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
