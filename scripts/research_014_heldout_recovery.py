"""Infrastructure-only, outcome-blind recovery of frozen Research 0.14 #432 shards.

The original workflow's 10-task jobs can hit GitHub's six-hour ceiling.
This module retains the original 780 task identities / three catalogs /
condition order, recovers only incomplete *execution* shards in 2-task
microbatches, and refuses an aggregate with incomplete or duplicate episodes.
No scientific result value is inspected to decide which shard to rerun.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

from scripts.research_014_conveyor import GitHubAPI

FROZEN_SOURCE = "30663de8f618bc88a893d9bf6214035a70e8e894"
PARENT_WORKFLOW = "research-0.14-heldout-generalization.yml"
RECOVERY_WORKFLOW = "research-0.14-heldout-recovery.yml"
CATALOGS = (100, 250, 500)
TASKS_PER_PARENT = 10
TASKS_PER_MICRO = 2
PARENTS_PER_WAVE = 40
EXPECTED_SHARDS = 234
RUNTIME_KEYS = (
    "machine", "python", "jinja2", "torch", "transformers",
    "tokenizers", "safetensors",
)
JOB_RE = re.compile(r"^evaluate \(c(100|250|500)-g(\d{2})(?:,|\))")
ARTIFACT_RE = re.compile(r"^heldout-shard-(c(?:100|250|500)-g\d{2})-(\d+)$")
MICRO_RE = re.compile(
    r"^heldout-recovery-part-(c(?:100|250|500)-g\d{2}-p\d{2})-(\d+)$"
)


def frozen_shards(corpus: dict[str, Any]) -> dict[str, tuple[int, tuple[str, ...]]]:
    ids = [str(t["semantic_task_id"]) for t in corpus["tasks"]]
    if len(ids) != 780 or len(set(ids)) != 780:
        raise ValueError("expected exactly 780 distinct frozen semantic tasks")
    if corpus.get("generator_source_revision") != FROZEN_SOURCE:
        raise ValueError("scientific source revision drift")
    chunks = [tuple(ids[i:i + TASKS_PER_PARENT]) for i in range(0, len(ids), TASKS_PER_PARENT)]
    if len(chunks) != 78 or any(len(chunk) != 10 for chunk in chunks):
        raise ValueError("frozen 10-task shard partition drift")
    result = {
        f"c{catalog}-g{i:02d}": (catalog, chunk)
        for catalog in CATALOGS
        for i, chunk in enumerate(chunks)
    }
    assert len(result) == EXPECTED_SHARDS
    return result


def latest_jobs(api: GitHubAPI, run_id: int) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    page = 1
    while True:
        data = api.get(f"/actions/runs/{run_id}/jobs?filter=latest&per_page=100&page={page}")
        batch = data["jobs"]
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return jobs


def successful_parent_shards(
    jobs: list[dict[str, Any]], artifacts: list[dict[str, Any]], parent_run: int
) -> set[str]:
    """Job success AND surviving named artifact are necessary, not sufficient.
    The eventual collector additionally verifies ZIP digests and payload identity.
    """
    conclusions: dict[str, str] = {}
    for job in jobs:
        match = JOB_RE.match(str(job.get("name", "")))
        if not match:
            continue
        shard = f"c{match.group(1)}-g{match.group(2)}"
        if shard in conclusions:
            raise ValueError(f"duplicate latest job identity: {shard}")
        conclusions[shard] = str(job.get("conclusion"))
    named: set[str] = set()
    for artifact in artifacts:
        match = ARTIFACT_RE.fullmatch(str(artifact.get("name", "")))
        if not match or int(match.group(2)) != parent_run or artifact.get("expired"):
            continue
        if not str(artifact.get("digest") or "").startswith("sha256:"):
            continue
        if match.group(1) in named:
            raise ValueError(f"duplicate parent artifact: {match.group(1)}")
        named.add(match.group(1))
    return {shard for shard, conclusion in conclusions.items()
            if conclusion == "success" and shard in named}


def wave_parts(
    shards: dict[str, tuple[int, tuple[str, ...]]],
    missing: list[str],
    wave: int,
) -> tuple[list[dict[str, Any]], int]:
    if wave < 0 or len(missing) != len(set(missing)):
        raise ValueError("invalid wave or duplicate missing parent shard")
    if any(s not in shards for s in missing):
        raise ValueError("unknown missing frozen parent shard")
    total_waves = math.ceil(len(missing) / PARENTS_PER_WAVE)
    if not 0 <= wave < total_waves:
        raise ValueError(f"wave {wave} outside 0..{total_waves - 1}")
    matrix: list[dict[str, Any]] = []
    for shard_id in missing[wave * PARENTS_PER_WAVE:(wave + 1) * PARENTS_PER_WAVE]:
        catalog, tasks = shards[shard_id]
        for i in range(0, TASKS_PER_PARENT, TASKS_PER_MICRO):
            matrix.append({
                "job_id": f"{shard_id}-p{i // TASKS_PER_MICRO:02d}",
                "catalog_size": catalog,
                "task_ids": ",".join(tasks[i:i + TASKS_PER_MICRO]),
            })
    if not matrix or len(matrix) > 200:
        raise ValueError("empty or oversized recovery matrix")
    return matrix, total_waves


def validate_shard(
    payload: dict[str, Any],
    *,
    corpus: dict[str, Any],
    catalog: int,
    task_ids: tuple[str, ...],
) -> None:
    """Validate episode identity without using pass/fail outcomes for selection."""
    conditions = tuple(corpus["condition_manifest"]["conditions"])
    if (
        payload.get("issue") != 432
        or payload.get("benchmark") != corpus["benchmark"]
        or payload.get("generator_source_revision") != FROZEN_SOURCE
        or payload.get("tasks_sha256") != corpus["tasks_sha256"]
        or payload.get("catalog_size") != catalog
        or set(payload.get("task_ids", [])) != set(task_ids)
        or len(payload.get("task_ids", [])) != len(task_ids)
        or tuple(payload.get("conditions", [])) != conditions
    ):
        raise ValueError("held-out shard source/corpus/condition/task mismatch")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("held-out shard has no complete row list")
    observed = [
        (str(row["task_id"]), int(row["catalog_size"]), str(row["condition"]))
        for row in rows
    ]
    expected = {(task, catalog, condition) for task in task_ids for condition in conditions}
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError("missing, duplicated or extraneous held-out episode identities")
    model = payload.get("model", {})
    if (model.get("name") != "HuggingFaceTB/SmolLM3-3B"
            or model.get("revision") != "a07cc9a04f16550a088caea529712d1d335b0ac1"
            or model.get("attention_implementation") != "sdpa"):
        raise ValueError("pinned scientific model drift")
    runtime = payload.get("runtime", {})
    if runtime.get("machine") not in {"aarch64", "arm64"} or runtime.get("python") != "3.12.14":
        raise ValueError("pinned ARM64 Python runtime drift")
    if runtime.get("torch") != "2.14.0+cpu" or runtime.get("transformers") != "4.57.6":
        raise ValueError("pinned torch/transformers runtime drift")


def _artifact_payload(api: GitHubAPI, artifact: dict[str, Any], filename: str) -> dict[str, Any]:
    """The GitHub digest is over the ZIP, not the JSON; verify it before parsing."""
    import io
    import zipfile

    _, raw = api._request("GET", f"/actions/artifacts/{int(artifact['id'])}/zip")
    expected = str(artifact.get("digest") or "")
    if expected != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError(f"artifact ZIP SHA256 mismatch: {artifact['id']}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [name for name in archive.namelist() if name.split("/")[-1] == filename]
        if len(names) != 1:
            raise ValueError(f"expected exactly one {filename} in artifact {artifact['id']}")
        with archive.open(names[0]) as handle:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("shard artifact JSON root must be an object")
    return payload


def plan(
    api: GitHubAPI, corpus: dict[str, Any], *, parent: int, wave: int,
    source: str, digest: str
) -> dict[str, Any]:
    if source != FROZEN_SOURCE or not digest.startswith("sha256:"):
        raise ValueError("unfrozen experiment identity")
    parent_run = api.run(parent)
    if not str(parent_run.get("path") or "").endswith(PARENT_WORKFLOW):
        raise ValueError("parent is not canonical held-out workflow")
    if parent_run.get("status") != "completed":
        raise ValueError("preserve materialized original while any parent jobs remain active")
    title = str(parent_run.get("display_title") or "")
    if digest not in title or f"source={source}" not in title:
        raise ValueError("parent provenance marker mismatch")
    shards = frozen_shards(corpus)
    jobs = latest_jobs(api, parent)
    if len(jobs) < EXPECTED_SHARDS + 2:
        raise ValueError("parent has no complete materialized matrix")
    artifacts = api.artifacts(parent)
    successful = successful_parent_shards(jobs, artifacts, parent)
    if not successful <= set(shards):
        raise ValueError("unknown successful shard")
    missing = sorted(set(shards) - successful)
    matrix, waves = wave_parts(shards, missing, wave)
    return {
        "schema_version": 1,
        "parent_run_id": parent,
        "source_sha": source,
        "evidence_digest": digest,
        "tasks_sha256": corpus["tasks_sha256"],
        "successful_parent_shards": sorted(successful),
        "missing_parent_shards": missing,
        "total_waves": waves,
        "wave": wave,
        "matrix": matrix,
        "conditions": list(corpus["condition_manifest"]["conditions"]),
    }


def collect(
    api: GitHubAPI, corpus: dict[str, Any], plan_data: dict[str, Any],
    *, current_recovery_run: int, out: Path,
) -> dict[str, Any]:
    """Copy only fully verified shards; no episode scoring or semantic retuning."""
    parent = int(plan_data["parent_run_id"])
    shards = frozen_shards(corpus)
    parent_success = set(plan_data["successful_parent_shards"])
    missing = plan_data["missing_parent_shards"]
    expected_parts: dict[str, tuple[int, tuple[str, ...]]] = {}
    for shard_id in missing:
        catalog, tasks = shards[shard_id]
        for i in range(0, len(tasks), TASKS_PER_MICRO):
            expected_parts[f"{shard_id}-p{i // TASKS_PER_MICRO:02d}"] = (
                catalog, tasks[i:i + TASKS_PER_MICRO]
            )
    outputs: dict[str, dict[str, Any]] = {}
    proof: dict[str, Any] = {}
    versions: dict[str, Any] | None = None

    def accept(name: str, payload: dict[str, Any], catalog: int, tasks: tuple[str, ...],
               artifact: dict[str, Any], run_id: int) -> None:
        nonlocal versions
        validate_shard(payload, corpus=corpus, catalog=catalog, task_ids=tasks)
        observed_versions = {
            "model": payload["model"],
            "runtime": {k: payload["runtime"].get(k) for k in RUNTIME_KEYS},
        }
        if versions is None:
            versions = observed_versions
        elif versions != observed_versions:
            raise ValueError("heterogeneous frozen model or library runtime")
        if name in outputs:
            raise ValueError(f"duplicate recovered artifact identity: {name}")
        outputs[name] = payload
        proof[name] = {"run_id": run_id, "artifact_id": artifact["id"],
                       "artifact_digest": artifact["digest"],
                       "tasks": list(tasks)}

    for artifact in api.artifacts(parent):
        match = ARTIFACT_RE.fullmatch(str(artifact.get("name", "")))
        if not match or int(match.group(2)) != parent or artifact.get("expired"):
            continue
        shard = match.group(1)
        if shard not in parent_success:
            continue  # Timed-out job artifact is NEVER a successful shard.
        catalog, tasks = shards[shard]
        accept(shard, _artifact_payload(api, artifact, f"{shard}.json"),
               catalog, tasks, artifact, parent)

    expected_waves = int(plan_data["total_waves"])
    run_rows = api.workflow_runs(RECOVERY_WORKFLOW)
    wave_runs: dict[int, int] = {}
    for row in run_rows:
        rid = int(row["id"])
        title = str(row.get("display_title") or "")
        matched = re.fullmatch(
            rf"Held-out recovery parent={parent} wave=(\d+) source={FROZEN_SOURCE}",
            title,
        )
        if not matched:
            continue
        w = int(matched.group(1))
        if w >= expected_waves:
            continue
        if rid == current_recovery_run:
            if w != expected_waves - 1:
                raise ValueError("canonical collection before last recovery wave")
        elif row.get("status") != "completed" or row.get("conclusion") != "success":
            continue
        if w in wave_runs:
            raise ValueError(f"duplicate successful wave {w}")
        wave_runs[w] = rid
    if set(wave_runs) != set(range(expected_waves)):
        raise ValueError(f"missing recovery waves: {set(range(expected_waves)) - set(wave_runs)}")

    for wave, run_id in wave_runs.items():
        selected, _ = wave_parts(shards, missing, wave)
        selected_ids = {part["job_id"] for part in selected}
        seen: set[str] = set()
        for artifact in api.artifacts(run_id):
            match = MICRO_RE.fullmatch(str(artifact.get("name", "")))
            if not match or int(match.group(2)) != run_id or artifact.get("expired"):
                continue
            part = match.group(1)
            if part not in selected_ids:
                raise ValueError("unexpected microshard in recovery wave")
            catalog, tasks = expected_parts[part]
            accept(part, _artifact_payload(api, artifact, f"{part}.json"),
                   catalog, tasks, artifact, run_id)
            seen.add(part)
        if seen != selected_ids:
            raise ValueError(f"incomplete recovery wave {wave}: {len(seen)}/{len(selected_ids)}")

    if set(outputs) != parent_success | set(expected_parts):
        raise ValueError("shard identity completeness check failed")
    out.mkdir(parents=True, exist_ok=True)
    episode_ids: set[tuple[str, int, str]] = set()
    for name, payload in sorted(outputs.items()):
        for row in payload["rows"]:
            identity = (str(row["task_id"]), int(row["catalog_size"]), str(row["condition"]))
            if identity in episode_ids:
                raise ValueError(f"duplicate recovered episode identity: {identity}")
            episode_ids.add(identity)
        (out / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    expected_episode_count = 780 * len(CATALOGS) * len(corpus["condition_manifest"]["conditions"])
    if len(episode_ids) != expected_episode_count:
        raise ValueError("not all frozen paired episodes recovered")
    return {"schema_version": 1, "parent_run_id": parent,
            "recovery_run_id": current_recovery_run, "source_sha": FROZEN_SOURCE,
            "tasks_sha256": corpus["tasks_sha256"], "episode_count": len(episode_ids),
            "parent_success_count": len(parent_success),
            "recovered_parent_count": len(missing), "artifacts": proof}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("plan", "collect"))
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--parent-run", required=True, type=int)
    parser.add_argument("--wave", type=int, default=0)
    parser.add_argument("--source-sha", default=FROZEN_SOURCE)
    parser.add_argument("--evidence-digest", required=True)
    parser.add_argument("--plan-out", type=Path, default=Path("artifacts/heldout-recovery-plan.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/heldout-verified"))
    parser.add_argument("--proof-out", type=Path, default=Path("artifacts/heldout-recovery-proof.json"))
    args = parser.parse_args()

    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    if args.mode == "plan":
        result = plan(api, corpus, parent=args.parent_run, wave=args.wave,
                      source=args.source_sha, digest=args.evidence_digest)
        args.plan_out.parent.mkdir(parents=True, exist_ok=True)
        args.plan_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
                for key, value in (
                    ("matrix", json.dumps({"include": result["matrix"]}, separators=(",", ":"))),
                    ("conditions", ",".join(result["conditions"])),
                    ("last_wave", str(result["wave"] == result["total_waves"] - 1).lower()),
                ):
                    handle.write(f"{key}={value}\n")
        print(f"frozen missing parent shards: {len(result['missing_parent_shards'])}; "
              f"recovery wave {args.wave + 1}/{result['total_waves']}; "
              f"microshards {len(result['matrix'])}")
    else:
        plan_data = json.loads(args.plan_out.read_text(encoding="utf-8"))
        if (plan_data["parent_run_id"] != args.parent_run
                or plan_data["source_sha"] != args.source_sha
                or plan_data["evidence_digest"] != args.evidence_digest):
            raise ValueError("recovery plan identity drift")
        result = collect(api, corpus, plan_data,
                         current_recovery_run=int(os.environ["GITHUB_RUN_ID"]),
                         out=args.out_dir)
        args.proof_out.parent.mkdir(parents=True, exist_ok=True)
        args.proof_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
        print(f"verified {result['episode_count']} frozen paired episodes")


if __name__ == "__main__":
    main()
