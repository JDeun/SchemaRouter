"""Research 0.14 gated experiment conveyor.

This controller is intentionally outcome-blind except for preregistered aggregate
gate booleans. It never consumes row-level failures to alter benchmark semantics.
It scans GitHub Actions state, dispatches only a ready downstream stage, and
fails closed when required provenance is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_B2_RUN = 36642658406
B2_ARTIFACT_PREFIX = "b2-smollm3-canonical-"
K3_WORKFLOW = "research-0.14-structural-k3-agent.yml"
K3_ARTIFACT_PREFIX = "structural-k3-agent-canonical-"
CORRECTIVE_WORKFLOW = "research-0.14-corrective-reretrieval.yml"
CORRECTIVE_ARTIFACT_PREFIX = "corrective-reretrieval-canonical-"
HELDOUT_WORKFLOW = "research-0.14-heldout-generalization.yml"
HELDOUT_ARTIFACT_PREFIX = "heldout-generalization-canonical-"
FINAL_WORKFLOW = "research-0.14-final-answer.yml"
FINAL_ARTIFACT_PREFIX = "final-answer-canonical-"
# #506 output-field projection. The development screen has no upstream
# dependency, so it is advanced before the B2 gate and never waits on the chain.
# The confirmation arm is appended after terminal evidence so that adding it
# cannot perturb any stage of the already-frozen DAG.
PROJECTION_DEV_WORKFLOW = "research-0.14-field-projection-dev.yml"
PROJECTION_DEV_ARTIFACT_PREFIX = "projection-dev-screen-"
PROJECTION_WORKFLOW = "research-0.14-field-projection.yml"
PROJECTION_ARTIFACT_PREFIX = "projection-canonical-"
# #506 needs its own frozen implementation identity. DOWNSTREAM_IMPLEMENTATION_SHA
# belongs to the already-frozen #431/#432/#424 chain and predates every file
# below, so dispatching a projection stage against it would check out a tree that
# cannot run the experiment. The projection source is frozen on first dispatch
# and then reused, exactly like the other stages recover their frozen source.
PROJECTION_REQUIRED_PATHS = (
    "scripts/agent_utility_v7_projection.py",
    "scripts/agent_utility_v7_dev_agent.py",
    "scripts/generate_agent_utility_v7_projection_corpus.py",
    "scripts/validate_agent_utility_v7_projection_corpus.py",
    "scripts/evaluate_agent_utility_v7_projection.py",
    "scripts/aggregate_agent_utility_v7_projection.py",
)
TRACKING_ISSUE = 500
# Exact scientific implementation frozen when the conveyor landed.
# Workflow-wrapper hotfixes must not alter downstream benchmark semantics.
DOWNSTREAM_IMPLEMENTATION_SHA = "30663de8f618bc88a893d9bf6214035a70e8e894"


@dataclass(frozen=True)
class StageRun:
    id: int
    status: str
    conclusion: str | None
    display_title: str
    created_at: str
    html_url: str
    run_attempt: int
    head_sha: str


class GitHubAPI:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.base = f"https://api.github.com/repos/{repository}"
        self.token = token

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, bytes]:
        url = path if path.startswith("https://") else self.base + path
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "schemarouter-research-0.14-conveyor",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API {method} {url} failed: {exc.code} {detail}"
            ) from exc

    def get(self, path: str) -> Any:
        _, content = self._request("GET", path)
        return json.loads(content.decode("utf-8"))

    def post(self, path: str, payload: dict[str, Any]) -> None:
        status, _ = self._request("POST", path, payload)
        if status not in {200, 201, 202, 204}:
            raise RuntimeError(f"unexpected GitHub POST status: {status}")

    def ref_sha(self, ref: str) -> str:
        data = self.get("/git/ref/heads/" + urllib.parse.quote(ref, safe=""))
        return str(data["object"]["sha"])

    def path_exists(self, path: str, *, ref: str) -> bool:
        """Whether `path` exists at `ref`.

        A stage workflow checks out an exact frozen revision before running its
        scripts, so dispatching a stage against a revision that predates those
        scripts fails at run time while every unit test stays green. This lets
        the controller refuse that dispatch instead.
        """
        try:
            self.get(
                "/contents/"
                + urllib.parse.quote(path)
                + "?ref="
                + urllib.parse.quote(ref, safe="")
            )
        except RuntimeError as exc:
            if " 404 " in str(exc):
                return False
            raise
        return True

    def run(self, run_id: int) -> dict[str, Any]:
        return dict(self.get(f"/actions/runs/{run_id}"))

    def workflow_runs(self, workflow_file: str) -> list[dict[str, Any]]:
        data = self.get(
            "/actions/workflows/"
            + urllib.parse.quote(workflow_file, safe="")
            + "/runs?per_page=100"
        )
        return [dict(row) for row in data.get("workflow_runs", [])]

    def artifacts(self, run_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get(
                f"/actions/runs/{run_id}/artifacts?per_page=100&page={page}"
            )
            batch = [dict(row) for row in data.get("artifacts", [])]
            rows.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return rows

    def artifact(self, run_id: int, prefix: str) -> dict[str, Any] | None:
        matches = [
            artifact
            for artifact in self.artifacts(run_id)
            if str(artifact.get("name", "")).startswith(prefix)
            and not bool(artifact.get("expired"))
        ]
        if not matches:
            return None
        matches.sort(key=lambda row: int(row["id"]), reverse=True)
        return matches[0]

    def artifact_json(
        self,
        artifact: dict[str, Any],
        canonical_filename: str,
    ) -> dict[str, Any]:
        _, payload = self._request(
            "GET",
            f"/actions/artifacts/{int(artifact['id'])}/zip",
        )
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            exact = [name for name in names if name.endswith(canonical_filename)]
            if len(exact) != 1:
                raise RuntimeError(
                    f"artifact {artifact['id']} expected one {canonical_filename}, "
                    f"found {exact!r}"
                )
            with archive.open(exact[0]) as handle:
                data = json.load(handle)
        if not isinstance(data, dict):
            raise RuntimeError("canonical artifact JSON root must be an object")
        return data

    def dispatch(
        self,
        workflow_file: str,
        *,
        ref: str,
        inputs: dict[str, str] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs
        self.post(
            "/actions/workflows/"
            + urllib.parse.quote(workflow_file, safe="")
            + "/dispatches",
            payload,
        )

    def rerun_failed_jobs(self, run_id: int) -> None:
        status, _ = self._request(
            "POST",
            f"/actions/runs/{run_id}/rerun-failed-jobs",
        )
        if status not in {200, 201, 202, 204}:
            raise RuntimeError(f"unexpected GitHub rerun status: {status}")

    def workflow_run_job_count(self, run_id: int) -> int:
        data = self.get(f"/actions/runs/{run_id}/jobs?per_page=1")
        return int(data.get("total_count") or 0)

    def cancel_run_and_wait(
        self,
        run_id: int,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        status, _ = self._request("POST", f"/actions/runs/{run_id}/cancel")
        if status not in {200, 201, 202, 204}:
            raise RuntimeError(f"unexpected GitHub cancel status: {status}")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            run = self.run(run_id)
            if run.get("status") == "completed":
                return
            time.sleep(1.0)
        raise RuntimeError(
            f"workflow run {run_id} did not reach terminal cancellation "
            f"within {timeout_seconds:g}s"
        )

    def issue_comments(self, issue_number: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get(
                f"/issues/{issue_number}/comments?per_page=100&page={page}"
            )
            batch = [dict(row) for row in data]
            rows.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return rows

    def comment_issue(self, issue_number: int, body: str) -> None:
        self.post(f"/issues/{issue_number}/comments", {"body": body})


def combine_digests(*values: str) -> str:
    canonical = "\n".join(values).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _stage_run(row: dict[str, Any]) -> StageRun:
    return StageRun(
        id=int(row["id"]),
        status=str(row["status"]),
        conclusion=(
            str(row["conclusion"])
            if row.get("conclusion") is not None
            else None
        ),
        display_title=str(row.get("display_title") or row.get("name") or ""),
        created_at=str(row.get("created_at") or ""),
        html_url=str(row.get("html_url") or ""),
        run_attempt=int(row.get("run_attempt") or 1),
        head_sha=str(row.get("head_sha") or ""),
    )


def find_marked_runs(
    api: GitHubAPI,
    workflow_file: str,
    marker: str,
) -> list[StageRun]:
    matches = [
        _stage_run(row)
        for row in api.workflow_runs(workflow_file)
        if marker in str(row.get("display_title") or "")
    ]
    matches.sort(key=lambda run: (run.created_at, run.id), reverse=True)
    return matches


def find_marked_run(
    api: GitHubAPI,
    workflow_file: str,
    marker: str,
) -> StageRun | None:
    matches = find_marked_runs(api, workflow_file, marker)
    return matches[0] if matches else None


def source_sha_from_run(run: StageRun) -> str:
    match = re.search(r"(?:^| )source=([0-9a-f]{40})(?:$| )", run.display_title)
    if match is not None:
        return match.group(1)
    if re.fullmatch(r"[0-9a-f]{40}", run.head_sha):
        return run.head_sha
    raise RuntimeError(f"unable to recover frozen source SHA from run {run.id}")


def find_k3_runs_after(api: GitHubAPI, *, not_before: str) -> list[StageRun]:
    candidates = [
        _stage_run(row)
        for row in api.workflow_runs(K3_WORKFLOW)
        if str(row.get("created_at") or "") >= not_before
    ]
    candidates.sort(key=lambda run: (run.created_at, run.id), reverse=True)
    return candidates


def find_k3_run_after(api: GitHubAPI, *, not_before: str) -> StageRun | None:
    candidates = find_k3_runs_after(api, not_before=not_before)
    return candidates[0] if candidates else None


def terminal_success(run: StageRun | None) -> bool:
    return bool(
        run is not None
        and run.status == "completed"
        and run.conclusion == "success"
    )


def terminal_failure(run: StageRun | None) -> bool:
    return bool(
        run is not None
        and run.status == "completed"
        and run.conclusion not in {None, "success"}
    )


MAX_INFRA_ATTEMPTS = 3


def retry_infrastructure_failure(
    api: GitHubAPI,
    run: StageRun,
    *,
    execute: bool,
    actions: list[str],
    label: str,
) -> bool:
    """Retry workflow infrastructure failures without changing frozen semantics."""
    if not terminal_failure(run):
        return False
    if run.run_attempt >= MAX_INFRA_ATTEMPTS:
        return False
    if execute:
        api.rerun_failed_jobs(run.id)
    actions.append(f"rerun_failed_{label}:run={run.id}:attempt={run.run_attempt + 1}")
    return True


def _artifact_digest(artifact: dict[str, Any]) -> str:
    digest = artifact.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise RuntimeError("required artifact is missing a SHA-256 digest")
    return digest


def _gate(payload: dict[str, Any], path: tuple[str, ...]) -> bool:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise RuntimeError("missing machine-readable gate: " + ".".join(path))
        value = value[key]
    if not isinstance(value, bool):
        raise RuntimeError("machine-readable gate is not boolean: " + ".".join(path))
    return value


def _age_seconds(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


STALE_QUEUED_WRAPPER_SECONDS = 1800.0
ZERO_JOB_PENDING_SECONDS = 180.0


def stale_zero_job_pending(
    run: StageRun | None,
    *,
    job_count: int,
    min_age_seconds: float = ZERO_JOB_PENDING_SECONDS,
) -> bool:
    """Whether a workflow is stuck before GitHub has created any jobs."""

    return bool(
        run is not None
        and run.status == "pending"
        and job_count == 0
        and _age_seconds(run.created_at) >= min_age_seconds
    )


def active_run_with_jobs(
    api: GitHubAPI,
    runs: list[StageRun],
) -> StageRun | None:
    """Return the newest non-terminal run that has created scientific jobs."""

    for run in runs:
        if run.status == "completed":
            continue
        if api.workflow_run_job_count(run.id) > 0:
            return run
    return None


def stale_pending_wrapper(
    run: StageRun | None,
    *,
    wrapper_sha: str,
    job_count: int,
    min_age_seconds: float = STALE_QUEUED_WRAPPER_SECONDS,
) -> bool:
    """Whether a queued/pending run is pinned to an obsolete workflow wrapper.

    Scientific source revisions are carried separately in workflow inputs. A
    fresh dispatch can therefore pick up infrastructure-only wrapper fixes
    without changing frozen experiment semantics.
    """
    return bool(
        run is not None
        and run.status in {"queued", "pending"}
        and job_count == 0
        and run.head_sha != wrapper_sha
        and _age_seconds(run.created_at) >= min_age_seconds
    )


def _status_line(label: str, run: StageRun | None) -> str:
    if run is None:
        return f"{label}=absent"
    return (
        f"{label}=run:{run.id} status:{run.status} "
        f"conclusion:{run.conclusion}"
    )


def projection_runs_oldest_first(
    api: GitHubAPI,
    workflow_file: str,
) -> list[StageRun]:
    runs = [_stage_run(row) for row in api.workflow_runs(workflow_file)]
    runs.sort(key=lambda run: (run.created_at, run.id))
    return runs


def frozen_projection_source(
    api: GitHubAPI,
    *,
    ref: str,
    actions: list[str],
) -> str | None:
    """The exact source revision #506 is frozen to, or None if it cannot be set.

    Once any projection run exists, its recorded source is the freeze and is
    reused verbatim; later commits to main must not silently move it. Before the
    first run, main is resolved and checked for the experiment's own files, so a
    revision that cannot run the experiment is never dispatched.
    """
    for workflow in (PROJECTION_DEV_WORKFLOW, PROJECTION_WORKFLOW):
        existing = projection_runs_oldest_first(api, workflow)
        if existing:
            return source_sha_from_run(existing[0])

    candidate = api.ref_sha(ref)
    missing = [
        path
        for path in PROJECTION_REQUIRED_PATHS
        if not api.path_exists(path, ref=candidate)
    ]
    if missing:
        actions.append(
            "blocked_projection_source_missing_experiment_files:"
            f"source={candidate}:missing={len(missing)}"
        )
        return None
    return candidate


def advance_projection_dev(
    api: GitHubAPI,
    *,
    ref: str,
    execute: bool,
    actions: list[str],
) -> None:
    """Advance the #506 development screen.

    It consumes no upstream artifact, so it is deliberately advanced before the
    B2 gate: queuing it behind the frozen chain would delay development evidence
    for no scientific reason.
    """
    source_sha = frozen_projection_source(api, ref=ref, actions=actions)
    if source_sha is None:
        return

    inputs = {"source_sha": source_sha}
    runs = find_marked_runs(api, PROJECTION_DEV_WORKFLOW, f"source={source_sha}")
    if not runs:
        if execute:
            api.dispatch(PROJECTION_DEV_WORKFLOW, ref=ref, inputs=inputs)
        actions.append(f"dispatch_projection_dev:source={source_sha}")
        return

    latest = runs[0]
    if not terminal_failure(latest):
        return

    failed = [run for run in runs if terminal_failure(run)]
    if len(failed) >= MAX_INFRA_ATTEMPTS:
        actions.append("stopped_projection_dev_infrastructure_failure_after_retries")
        return

    if execute:
        api.dispatch(PROJECTION_DEV_WORKFLOW, ref=ref, inputs=inputs)
    actions.append(
        "recover_dispatch_projection_dev_after_failure:"
        f"prior_run={latest.id}:attempt={len(failed) + 1}:source={source_sha}"
    )


def advance_projection_confirmation(
    api: GitHubAPI,
    *,
    ref: str,
    execute: bool,
    actions: list[str],
    terminal_digest: str,
) -> None:
    """Advance the #506 confirmation arm after terminal evidence.

    Appending it here rather than inserting it into the chain is deliberate: the
    DAG was preregistered before downstream corpus generation, so no existing
    stage's inputs, ordering, or frozen source may move.

    The source is #506's own frozen revision, never the #431 chain's frozen
    source, which predates every projection script.
    """
    source_sha = frozen_projection_source(api, ref=ref, actions=actions)
    if source_sha is None:
        return

    inputs = {"evidence_digest": terminal_digest, "source_sha": source_sha}
    runs = find_marked_runs(api, PROJECTION_WORKFLOW, terminal_digest)
    if not runs:
        if execute:
            api.dispatch(PROJECTION_WORKFLOW, ref=ref, inputs=inputs)
        actions.append("dispatch_projection_confirmation")
        return

    latest = runs[0]
    if not terminal_failure(latest):
        return

    failed = [run for run in runs if terminal_failure(run)]
    if len(failed) >= MAX_INFRA_ATTEMPTS:
        actions.append("stopped_projection_infrastructure_failure_after_retries")
        return

    if execute:
        api.dispatch(PROJECTION_WORKFLOW, ref=ref, inputs=inputs)
    actions.append(
        "recover_dispatch_projection_after_failure:"
        f"prior_run={latest.id}:attempt={len(failed) + 1}"
    )


def run_controller(
    api: GitHubAPI,
    *,
    ref: str,
    execute: bool,
    recover_missing_k3: bool = False,
) -> dict[str, Any]:
    actions: list[str] = []
    # Independent of the frozen chain; advanced first so an early return below
    # cannot starve it.
    advance_projection_dev(api, ref=ref, execute=execute, actions=actions)

    b2_row = api.run(CANONICAL_B2_RUN)
    b2 = _stage_run(b2_row)

    if b2.status != "completed":
        return {
            "state": "waiting_b2",
            "actions": actions,
            "status": [_status_line("b2", b2)],
        }
    if b2.conclusion != "success":
        return {
            "state": "stopped_b2_not_success",
            "actions": actions,
            "status": [_status_line("b2", b2)],
        }

    b2_artifact = api.artifact(CANONICAL_B2_RUN, B2_ARTIFACT_PREFIX)
    if b2_artifact is None:
        return {
            "state": "waiting_b2_canonical_artifact",
            "actions": actions,
            "status": [_status_line("b2", b2)],
        }
    b2_digest = _artifact_digest(b2_artifact)
    _wrapper_sha = api.ref_sha(ref)  # fail closed if workflow ref is missing
    source_sha = DOWNSTREAM_IMPLEMENTATION_SHA

    b2_terminal_time = str(b2_row.get("updated_at") or b2.created_at)
    k3_runs = find_k3_runs_after(api, not_before=b2_terminal_time)
    k3 = k3_runs[0] if k3_runs else None
    if k3 is None:
        # The K3 workflow already has its own exact-B2 workflow_run trigger.
        # Do not race that trigger on the same completion event. Only the
        # scheduled recovery scan may dispatch a missing K3 run.
        recovery_ready = _age_seconds(b2_terminal_time) >= 600.0
        if recover_missing_k3 and recovery_ready:
            if execute:
                api.dispatch(K3_WORKFLOW, ref=ref)
            actions.append("recover_dispatch_k3")
        else:
            actions.append("wait_for_k3_native_trigger")
    elif terminal_failure(k3):
        # A rerun of this historical run would reuse its old workflow wrapper.
        # Use a fresh workflow_dispatch so infrastructure-only fixes on main are
        # picked up while the frozen K3 implementation SHA remains unchanged.
        # Continue this controller pass so #431 can still launch in parallel.
        failed_k3_runs = [run for run in k3_runs if terminal_failure(run)]
        if len(failed_k3_runs) < MAX_INFRA_ATTEMPTS:
            failed_k3 = k3
            if execute:
                api.dispatch(K3_WORKFLOW, ref=ref)
            actions.append(
                f"recover_dispatch_k3_after_failure:prior_run={failed_k3.id}:"
                f"attempt={len(failed_k3_runs) + 1}"
            )
            k3 = None
        else:
            return {
                "state": "stopped_k3_infrastructure_failure_after_retries",
                "actions": actions,
                "status": [_status_line("k3", k3)],
            }

    corrective_runs = find_marked_runs(api, CORRECTIVE_WORKFLOW, b2_digest)
    active_corrective = active_run_with_jobs(api, corrective_runs)
    if active_corrective is not None:
        # GitHub can report a workflow as queued while its matrix jobs are
        # already running. Preserve that scientific run and remove only newer
        # pre-job pending duplicates created by earlier recovery attempts.
        redundant_pending = [
            run
            for run in corrective_runs
            if run.id != active_corrective.id
            and run.status == "pending"
            and api.workflow_run_job_count(run.id) == 0
        ]
        if execute:
            for redundant in redundant_pending:
                api.cancel_run_and_wait(redundant.id)
        actions.extend(
            "cancel_redundant_zero_job_pending_corrective:"
            f"run={run.id}:active={active_corrective.id}"
            for run in redundant_pending
        )
        corrective = active_corrective
    else:
        corrective = corrective_runs[0] if corrective_runs else None

    corrective_job_count = (
        api.workflow_run_job_count(corrective.id)
        if corrective is not None
        else 0
    )

    if corrective is None:
        if execute:
            api.dispatch(
                CORRECTIVE_WORKFLOW,
                ref=ref,
                inputs={
                    "evidence_digest": b2_digest,
                    "source_sha": source_sha,
                },
            )
        actions.append("dispatch_corrective")
    elif stale_zero_job_pending(
        corrective,
        job_count=corrective_job_count,
    ):
        # A workflow-level pending run with zero jobs has not begun scientific
        # work, regardless of which wrapper revision dispatched it. Cancel it
        # explicitly to release the concurrency group, then redispatch the exact
        # same frozen scientific inputs on current main.
        prior_zero_job_cancellations = [
            run
            for run in corrective_runs[1:]
            if run.status == "completed"
            and run.conclusion == "cancelled"
            and api.workflow_run_job_count(run.id) == 0
        ]
        if len(prior_zero_job_cancellations) >= MAX_INFRA_ATTEMPTS - 1:
            return {
                "state": "stopped_corrective_prejob_pending_after_retries",
                "actions": actions,
                "status": [_status_line("corrective", corrective)],
            }

        retry_source_sha = source_sha_from_run(corrective)
        if execute:
            api.cancel_run_and_wait(corrective.id)
            api.dispatch(
                CORRECTIVE_WORKFLOW,
                ref=ref,
                inputs={
                    "evidence_digest": b2_digest,
                    "source_sha": retry_source_sha,
                },
            )
        actions.append(
            "recover_dispatch_zero_job_pending_corrective:"
            f"prior_run={corrective.id}:"
            f"attempt={len(prior_zero_job_cancellations) + 2}:"
            f"source={retry_source_sha}:wrapper={_wrapper_sha}"
        )
        corrective = None
    elif stale_pending_wrapper(
        corrective,
        wrapper_sha=_wrapper_sha,
        job_count=corrective_job_count,
    ):
        # A long-queued run keeps the workflow wrapper SHA from dispatch time.
        # If an infrastructure-only wrapper fix has since landed, issue a fresh
        # dispatch while preserving the exact frozen scientific source input.
        retry_source_sha = source_sha_from_run(corrective)
        if execute:
            api.dispatch(
                CORRECTIVE_WORKFLOW,
                ref=ref,
                inputs={
                    "evidence_digest": b2_digest,
                    "source_sha": retry_source_sha,
                },
            )
        actions.append(
            "recover_dispatch_stale_pending_corrective_wrapper:"
            f"prior_run={corrective.id}:source={retry_source_sha}:"
            f"wrapper={_wrapper_sha}"
        )
        corrective = None
    elif terminal_failure(corrective):
        failed_corrective_runs = [
            run for run in corrective_runs if terminal_failure(run)
        ]
        if len(failed_corrective_runs) < MAX_INFRA_ATTEMPTS:
            retry_source_sha = source_sha_from_run(corrective)
            if execute:
                api.dispatch(
                    CORRECTIVE_WORKFLOW,
                    ref=ref,
                    inputs={
                        "evidence_digest": b2_digest,
                        "source_sha": retry_source_sha,
                    },
                )
            actions.append(
                "recover_dispatch_corrective_after_failure:"
                f"prior_run={corrective.id}:attempt={len(failed_corrective_runs) + 1}:"
                f"source={retry_source_sha}"
            )
            corrective = None
        else:
            return {
                "state": "stopped_corrective_infrastructure_failure_after_retries",
                "actions": actions,
                "status": [_status_line("corrective", corrective)],
            }

    if k3 is None or corrective is None or not (
        terminal_success(k3) and terminal_success(corrective)
    ):
        return {
            "state": "waiting_parallel_downstream",
            "actions": actions,
            "status": [
                _status_line("k3", k3),
                _status_line("corrective", corrective),
            ],
        }

    k3_artifact = api.artifact(k3.id, K3_ARTIFACT_PREFIX)
    corrective_artifact = api.artifact(
        corrective.id,
        CORRECTIVE_ARTIFACT_PREFIX,
    )
    if k3_artifact is None or corrective_artifact is None:
        return {
            "state": "waiting_parallel_canonical_artifacts",
            "actions": actions,
            "status": [
                _status_line("k3", k3),
                _status_line("corrective", corrective),
            ],
        }

    k3_payload = api.artifact_json(
        k3_artifact,
        "structural-k3-agent-canonical.json",
    )
    corrective_payload = api.artifact_json(
        corrective_artifact,
        "corrective-reretrieval-canonical.json",
    )
    corrective_corpus = api.artifact_json(
        corrective_artifact,
        "corrective-corpus.json",
    )
    frozen_source_sha = str(corrective_corpus.get("generator_source_revision") or "")
    if len(frozen_source_sha) != 40:
        raise RuntimeError("corrective corpus is missing frozen generator source SHA")
    include_k3 = _gate(k3_payload, ("primary_gate", "primary_gate_passed"))
    include_corrective = _gate(
        corrective_payload,
        ("primary_gate", "primary_gate_passed"),
    )
    parallel_digest = combine_digests(
        _artifact_digest(k3_artifact),
        _artifact_digest(corrective_artifact),
    )

    heldout_inputs = {
        "evidence_digest": parallel_digest,
        "source_sha": frozen_source_sha,
        "k3_run_id": str(k3.id),
        "corrective_run_id": str(corrective.id),
        "include_struct_fixed3": str(include_k3).lower(),
        "include_state_aware": str(include_corrective).lower(),
    }
    heldout_runs = find_marked_runs(api, HELDOUT_WORKFLOW, parallel_digest)
    heldout = heldout_runs[0] if heldout_runs else None
    if heldout is None:
        if execute:
            api.dispatch(HELDOUT_WORKFLOW, ref=ref, inputs=heldout_inputs)
        actions.append("dispatch_heldout")
        return {
            "state": "heldout_dispatched",
            "actions": actions,
            "optional_conditions": {
                "STRUCT-FIXED-3": include_k3,
                "SR-5-STATE-AWARE": include_corrective,
            },
        }
    if terminal_failure(heldout):
        failed_heldout_runs = [
            run for run in heldout_runs if terminal_failure(run)
        ]
        if len(failed_heldout_runs) < MAX_INFRA_ATTEMPTS:
            if execute:
                api.dispatch(HELDOUT_WORKFLOW, ref=ref, inputs=heldout_inputs)
            actions.append(
                "recover_dispatch_heldout_after_failure:"
                f"prior_run={heldout.id}:attempt={len(failed_heldout_runs) + 1}:"
                f"source={frozen_source_sha}"
            )
            return {
                "state": "retrying_heldout_infrastructure",
                "actions": actions,
                "status": [_status_line("heldout", heldout)],
            }
        return {
            "state": "stopped_heldout_infrastructure_failure_after_retries",
            "actions": actions,
            "status": [_status_line("heldout", heldout)],
        }
    if not terminal_success(heldout):
        return {
            "state": "waiting_heldout",
            "actions": actions,
            "status": [_status_line("heldout", heldout)],
        }

    heldout_artifact = api.artifact(heldout.id, HELDOUT_ARTIFACT_PREFIX)
    if heldout_artifact is None:
        return {
            "state": "waiting_heldout_canonical_artifact",
            "actions": actions,
        }
    heldout_digest = _artifact_digest(heldout_artifact)
    heldout_corpus = api.artifact_json(
        heldout_artifact,
        "heldout-corpus.json",
    )
    heldout_source_sha = str(heldout_corpus.get("generator_source_revision") or "")
    if heldout_source_sha != frozen_source_sha:
        raise RuntimeError(
            "held-out generator source SHA drifted from corrective frozen source"
        )

    final_inputs = {
        "evidence_digest": heldout_digest,
        "source_sha": frozen_source_sha,
        "heldout_run_id": str(heldout.id),
    }
    final_runs = find_marked_runs(api, FINAL_WORKFLOW, heldout_digest)
    final = final_runs[0] if final_runs else None
    if final is None:
        if execute:
            api.dispatch(FINAL_WORKFLOW, ref=ref, inputs=final_inputs)
        actions.append("dispatch_final_answer")
        return {
            "state": "final_answer_dispatched",
            "actions": actions,
        }
    if terminal_failure(final):
        failed_final_runs = [
            run for run in final_runs if terminal_failure(run)
        ]
        if len(failed_final_runs) < MAX_INFRA_ATTEMPTS:
            if execute:
                api.dispatch(FINAL_WORKFLOW, ref=ref, inputs=final_inputs)
            actions.append(
                "recover_dispatch_final_after_failure:"
                f"prior_run={final.id}:attempt={len(failed_final_runs) + 1}:"
                f"source={frozen_source_sha}"
            )
            return {
                "state": "retrying_final_answer_infrastructure",
                "actions": actions,
                "status": [_status_line("final", final)],
            }
        return {
            "state": "stopped_final_answer_infrastructure_failure_after_retries",
            "actions": actions,
            "status": [_status_line("final", final)],
        }
    if not terminal_success(final):
        return {
            "state": "waiting_final_answer",
            "actions": actions,
            "status": [_status_line("final", final)],
        }

    final_artifact = api.artifact(final.id, FINAL_ARTIFACT_PREFIX)
    if final_artifact is None:
        return {
            "state": "waiting_final_canonical_artifact",
            "actions": actions,
        }

    heldout_payload = api.artifact_json(
        heldout_artifact,
        "heldout-generalization-canonical.json",
    )
    final_payload = api.artifact_json(
        final_artifact,
        "final-answer-canonical.json",
    )
    final_digest = combine_digests(
        b2_digest,
        _artifact_digest(k3_artifact),
        _artifact_digest(corrective_artifact),
        heldout_digest,
        _artifact_digest(final_artifact),
    )
    marker = f"<!-- research-0.14-conveyor-terminal:{final_digest} -->"
    comments = api.issue_comments(TRACKING_ISSUE)
    already_commented = any(
        marker in str(comment.get("body") or "")
        for comment in comments
    )

    if not already_commented:
        body = "\n".join(
            [
                marker,
                "## Research 0.14 conveyor reached terminal state",
                "",
                f"- B2 canonical run: `{CANONICAL_B2_RUN}`",
                f"- Structural K3 agent run: `{k3.id}`",
                f"- Corrective re-retrieval run: `{corrective.id}`",
                f"- Held-out generalization run: `{heldout.id}`",
                f"- Final-answer run: `{final.id}`",
                f"- STRUCT-FIXED-3 promoted into held-out: `{include_k3}`",
                f"- State-aware corrective promoted into held-out: `{include_corrective}`",
                "- Held-out broad-claim gate: "
                + f"`{bool(heldout_payload.get('broad_claim_gate', {}).get('passed'))}`",
                "- Final-answer any deployable condition gate: "
                + f"`{bool(final_payload.get('any_deployable_condition_passed'))}`",
                f"- Terminal evidence digest: `{final_digest}`",
                "",
                "This comment records terminal machine-readable gates only. "
                "No failed rows were used for semantic retuning.",
            ]
        )
        if execute:
            api.comment_issue(TRACKING_ISSUE, body)
        actions.append("comment_terminal_summary")

    # Appended stage: the frozen DAG above is already terminal at this point, so
    # dispatching here cannot change any of its inputs or ordering.
    advance_projection_confirmation(
        api,
        ref=ref,
        execute=execute,
        actions=actions,
        terminal_digest=final_digest,
    )

    return {
        "state": "terminal",
        "actions": actions,
        "runs": {
            "b2": b2.id,
            "k3": k3.id,
            "corrective": corrective.id,
            "heldout": heldout.id,
            "final": final.id,
        },
        "terminal_evidence_digest": final_digest,
        "optional_conditions": {
            "STRUCT-FIXED-3": include_k3,
            "SR-5-STATE-AWARE": include_corrective,
        },
        "heldout_broad_claim_gate": bool(
            heldout_payload.get("broad_claim_gate", {}).get("passed")
        ),
        "final_answer_any_deployable_gate": bool(
            final_payload.get("any_deployable_condition_passed")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_TOKEN", ""),
    )
    parser.add_argument("--ref", default="main")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recover-missing-k3", action="store_true")
    parser.add_argument("--state-out", type=str, default="")
    args = parser.parse_args()

    if not args.repository or not args.token:
        raise SystemExit("repository and token are required")
    result = run_controller(
        GitHubAPI(args.repository, args.token),
        ref=args.ref,
        execute=args.execute,
        recover_missing_k3=args.recover_missing_k3,
    )
    if args.state_out:
        state_path = Path(args.state_out)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
