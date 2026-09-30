"""GitHub-side controller for the frozen Research 0.14 experiment conveyor.

The controller advances only from exact terminal workflow/artifact evidence.
Scientific negative results are represented inside successful canonical artifacts;
workflow failure is therefore treated as infrastructure failure and may be retried
without changing frozen semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CANONICAL_B2_RUN = 36642658406
K3_WORKFLOW = "research-0.14-structural-k3-agent.yml"
CORRECTIVE_WORKFLOW = "research-0.14-corrective.yml"
HELDOUT_WORKFLOW = "research-0.14-heldout.yml"
FINAL_WORKFLOW = "research-0.14-final-answer.yml"
K3_WORKFLOW_NAME = "Research 0.14 Structural K3 Agent Utility"
CORRECTIVE_RUN_LABEL = "Research 0.14 Corrective"
HELDOUT_RUN_LABEL = "Research 0.14 Heldout"
FINAL_RUN_LABEL = "Research 0.14 Final Answer"
TRACKING_ISSUE = 500
MAX_INFRA_ATTEMPTS = 3


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class ArtifactEvidence:
    run_id: int
    artifact_id: int
    name: str
    digest: str


class GitHubClient:
    def __init__(self, repository: str, token: str) -> None:
        if "/" not in repository:
            raise ValueError("repository must be owner/name")
        if not token:
            raise ValueError("GitHub token is required")
        self.repository = repository
        self.token = token
        self.base = f"https://api.github.com/repos/{repository}"

    def request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        url = path if path.startswith("https://") else self.base + path
        body = None if data is None else json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "SchemaRouter-Research-0.14-Conveyor",
            },
        )
        with urllib.request.urlopen(request) as response:
            payload = response.read()
        if raw:
            return payload
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))

    def get_run(self, run_id: int) -> dict[str, Any]:
        value = self.request("GET", f"/actions/runs/{run_id}")
        if not isinstance(value, dict):
            raise RuntimeError(f"invalid workflow run response for {run_id}")
        return value

    def artifacts(self, run_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            value = self.request(
                "GET",
                f"/actions/runs/{run_id}/artifacts?per_page=100&page={page}",
            )
            batch = list(value.get("artifacts", []))
            rows.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return rows

    def artifact(
        self,
        run_id: int,
        *,
        prefix: str,
    ) -> ArtifactEvidence:
        matches = [
            row
            for row in self.artifacts(run_id)
            if str(row.get("name", "")).startswith(prefix)
            and not bool(row.get("expired"))
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one artifact prefix={prefix!r} for run {run_id}; "
                f"found {[row.get('name') for row in matches]}"
            )
        row = matches[0]
        digest = str(row.get("digest") or "")
        if not digest.startswith("sha256:"):
            raise RuntimeError(f"artifact {row.get('name')} has no SHA-256 digest")
        return ArtifactEvidence(
            run_id=run_id,
            artifact_id=int(row["id"]),
            name=str(row["name"]),
            digest=digest,
        )

    def artifact_json(
        self,
        evidence: ArtifactEvidence,
        *,
        basename: str,
    ) -> dict[str, Any]:
        payload = self.request(
            "GET",
            f"/actions/artifacts/{evidence.artifact_id}/zip",
            raw=True,
        )
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            matches = [
                name
                for name in archive.namelist()
                if Path(name).name == basename
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"expected one {basename!r} in artifact {evidence.name}; "
                    f"found {matches}"
                )
            value = json.loads(archive.read(matches[0]).decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError(f"{basename} root must be an object")
        return value

    def workflow_runs(self, workflow: str) -> list[dict[str, Any]]:
        encoded = urllib.parse.quote(workflow, safe="")
        value = self.request(
            "GET",
            f"/actions/workflows/{encoded}/runs?per_page=100",
        )
        return list(value.get("workflow_runs", []))

    def dispatch(
        self,
        workflow: str,
        *,
        inputs: dict[str, str] | None = None,
    ) -> None:
        encoded = urllib.parse.quote(workflow, safe="")
        self.request(
            "POST",
            f"/actions/workflows/{encoded}/dispatches",
            data={"ref": "main", "inputs": inputs or {}},
        )

    def rerun_failed(self, run_id: int) -> None:
        self.request("POST", f"/actions/runs/{run_id}/rerun-failed-jobs", data={})

    def issue_comments(self, issue_number: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.request(
                "GET",
                f"/issues/{issue_number}/comments?per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise RuntimeError("issue comments response must be an array")
            rows.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return rows

    def add_issue_comment(self, issue_number: int, body: str) -> None:
        self.request(
            "POST",
            f"/issues/{issue_number}/comments",
            data={"body": body},
        )


def b2_evidence(client: GitHubClient, run_id: int = CANONICAL_B2_RUN) -> tuple[dict[str, Any], ArtifactEvidence, str]:
    run = client.get_run(run_id)
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise RuntimeError(
            f"canonical B2 is not successful terminal: "
            f"status={run.get('status')} conclusion={run.get('conclusion')}"
        )
    artifact = client.artifact(
        run_id,
        prefix=f"b2-smollm3-canonical-{run_id}",
    )
    evidence_digest = _digest(
        {
            "run_id": run_id,
            "head_sha": run.get("head_sha"),
            "artifact_digest": artifact.digest,
        }
    )
    return run, artifact, evidence_digest


def corrective_upstream_digest(b2_digest: str) -> str:
    return _digest({"stage": 431, "canonical_b2_evidence": b2_digest})


def heldout_upstream_digest(
    b2_digest: str,
    k3: ArtifactEvidence,
    corrective: ArtifactEvidence,
) -> str:
    return _digest(
        {
            "stage": 432,
            "canonical_b2_evidence": b2_digest,
            "structural_k3": {
                "run_id": k3.run_id,
                "artifact_digest": k3.digest,
            },
            "corrective": {
                "run_id": corrective.run_id,
                "artifact_digest": corrective.digest,
            },
        }
    )


def final_upstream_digest(heldout: ArtifactEvidence) -> str:
    return _digest(
        {
            "stage": 424,
            "heldout": {
                "run_id": heldout.run_id,
                "artifact_digest": heldout.digest,
            },
        }
    )


def _run_title(label: str, digest: str) -> str:
    return f"{label} [{digest}]"


def _find_digest_run(
    client: GitHubClient,
    workflow: str,
    *,
    label: str,
    digest: str,
) -> dict[str, Any] | None:
    title = _run_title(label, digest)
    matches = [
        run
        for run in client.workflow_runs(workflow)
        if run.get("display_title") == title
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: int(row["id"]))


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.min
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _find_k3_run(
    client: GitHubClient,
    *,
    after: str | None,
) -> dict[str, Any] | None:
    threshold = _parse_time(after)
    matches = [
        run
        for run in client.workflow_runs(K3_WORKFLOW)
        if str(run.get("name")) == K3_WORKFLOW_NAME
        and _parse_time(run.get("created_at")) >= threshold
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: int(row["id"]))


def _ensure_run(
    client: GitHubClient,
    *,
    workflow: str,
    label: str,
    digest: str,
    inputs: dict[str, str],
) -> dict[str, Any] | None:
    run = _find_digest_run(
        client,
        workflow,
        label=label,
        digest=digest,
    )
    if run is None:
        client.dispatch(workflow, inputs=inputs)
        print(
            json.dumps(
                {
                    "event": "dispatched",
                    "workflow": workflow,
                    "digest": digest,
                },
                sort_keys=True,
            )
        )
        return None

    if run.get("status") == "completed" and run.get("conclusion") != "success":
        attempt = int(run.get("run_attempt") or 1)
        if attempt < MAX_INFRA_ATTEMPTS:
            client.rerun_failed(int(run["id"]))
            print(
                json.dumps(
                    {
                        "event": "rerun_failed_jobs",
                        "workflow": workflow,
                        "run_id": run["id"],
                        "attempt": attempt,
                    },
                    sort_keys=True,
                )
            )
            return None
    return run


def _successful_terminal(run: dict[str, Any] | None) -> bool:
    return bool(
        run is not None
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    )


def _gate_value(data: dict[str, Any], path: tuple[str, ...]) -> bool:
    value: Any = data
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise RuntimeError(f"missing gate path: {'.'.join(path)}")
        value = value[key]
    if not isinstance(value, bool):
        raise RuntimeError(f"gate path is not boolean: {'.'.join(path)}")
    return value


def verify_digest(
    client: GitHubClient,
    *,
    stage: str,
    expected: str,
    b2_run_id: int | None,
    k3_run_id: int | None,
    corrective_run_id: int | None,
    heldout_run_id: int | None,
) -> dict[str, Any]:
    if stage == "corrective":
        _, _, b2_digest = b2_evidence(client, b2_run_id or CANONICAL_B2_RUN)
        actual = corrective_upstream_digest(b2_digest)
    elif stage == "heldout":
        _, _, b2_digest = b2_evidence(client, b2_run_id or CANONICAL_B2_RUN)
        if k3_run_id is None or corrective_run_id is None:
            raise ValueError("heldout verification requires K3 and corrective run IDs")
        k3 = client.artifact(
            k3_run_id,
            prefix="structural-k3-agent-canonical-",
        )
        corrective = client.artifact(
            corrective_run_id,
            prefix="corrective-canonical-",
        )
        actual = heldout_upstream_digest(b2_digest, k3, corrective)
    elif stage == "final":
        if heldout_run_id is None:
            raise ValueError("final verification requires heldout run ID")
        heldout = client.artifact(
            heldout_run_id,
            prefix="heldout-canonical-",
        )
        actual = final_upstream_digest(heldout)
    else:
        raise ValueError(f"unknown stage: {stage}")

    if actual != expected:
        raise RuntimeError(
            f"{stage} upstream digest mismatch: expected={expected} actual={actual}"
        )
    return {"stage": stage, "upstream_digest": actual, "verified": True}


def advance(
    client: GitHubClient,
    *,
    implementation_sha: str,
    summary_out: Path | None,
) -> dict[str, Any]:
    b2 = client.get_run(CANONICAL_B2_RUN)
    state: dict[str, Any] = {
        "schema_version": 1,
        "cycle": "0.14-end-to-end-agent-utility",
        "canonical_b2_run": CANONICAL_B2_RUN,
        "b2_status": b2.get("status"),
        "b2_conclusion": b2.get("conclusion"),
    }
    if b2.get("status") != "completed" or b2.get("conclusion") != "success":
        state["state"] = "waiting_for_successful_b2"
        return state

    _, b2_artifact, b2_digest = b2_evidence(client)
    state["b2_artifact_digest"] = b2_artifact.digest
    state["b2_evidence_digest"] = b2_digest

    k3_run = _find_k3_run(client, after=b2.get("updated_at"))
    if k3_run is None:
        client.dispatch(K3_WORKFLOW)
        state["state"] = "dispatched_structural_k3"
        return state
    if k3_run.get("status") == "completed" and k3_run.get("conclusion") != "success":
        attempt = int(k3_run.get("run_attempt") or 1)
        if attempt < MAX_INFRA_ATTEMPTS:
            client.rerun_failed(int(k3_run["id"]))
        state["state"] = "waiting_for_structural_k3_retry"
        state["k3_run_id"] = int(k3_run["id"])
        return state

    corrective_digest = corrective_upstream_digest(b2_digest)
    corrective_run = _ensure_run(
        client,
        workflow=CORRECTIVE_WORKFLOW,
        label=CORRECTIVE_RUN_LABEL,
        digest=corrective_digest,
        inputs={
            "implementation_sha": implementation_sha,
            "upstream_digest": corrective_digest,
            "b2_run_id": str(CANONICAL_B2_RUN),
        },
    )
    state["k3_run_id"] = int(k3_run["id"])
    state["corrective_upstream_digest"] = corrective_digest
    state["corrective_run_id"] = (
        int(corrective_run["id"]) if corrective_run is not None else None
    )
    if not _successful_terminal(k3_run) or not _successful_terminal(corrective_run):
        state["state"] = "waiting_for_parallel_downstream"
        return state

    k3_artifact = client.artifact(
        int(k3_run["id"]),
        prefix="structural-k3-agent-canonical-",
    )
    corrective_artifact = client.artifact(
        int(corrective_run["id"]),
        prefix="corrective-canonical-",
    )
    k3_result = client.artifact_json(
        k3_artifact,
        basename="structural-k3-agent-canonical.json",
    )
    corrective_result = client.artifact_json(
        corrective_artifact,
        basename="corrective-canonical.json",
    )
    k3_gate = _gate_value(k3_result, ("primary_gate", "primary_gate_passed"))
    corrective_gate = _gate_value(
        corrective_result,
        ("primary_gate", "primary_gate_passed"),
    )
    state["k3_gate_passed"] = k3_gate
    state["corrective_gate_passed"] = corrective_gate
    state["k3_artifact_digest"] = k3_artifact.digest
    state["corrective_artifact_digest"] = corrective_artifact.digest

    heldout_digest = heldout_upstream_digest(
        b2_digest,
        k3_artifact,
        corrective_artifact,
    )
    heldout_run = _ensure_run(
        client,
        workflow=HELDOUT_WORKFLOW,
        label=HELDOUT_RUN_LABEL,
        digest=heldout_digest,
        inputs={
            "implementation_sha": implementation_sha,
            "upstream_digest": heldout_digest,
            "b2_run_id": str(CANONICAL_B2_RUN),
            "k3_run_id": str(k3_run["id"]),
            "corrective_run_id": str(corrective_run["id"]),
        },
    )
    state["heldout_upstream_digest"] = heldout_digest
    state["heldout_run_id"] = int(heldout_run["id"]) if heldout_run else None
    if not _successful_terminal(heldout_run):
        state["state"] = "waiting_for_heldout"
        return state

    heldout_artifact = client.artifact(
        int(heldout_run["id"]),
        prefix="heldout-canonical-",
    )
    heldout_result = client.artifact_json(
        heldout_artifact,
        basename="heldout-canonical.json",
    )
    state["heldout_artifact_digest"] = heldout_artifact.digest
    state["heldout_broad_claim_gate_passed"] = _gate_value(
        heldout_result,
        ("broad_claim_gate", "passed"),
    )

    final_digest = final_upstream_digest(heldout_artifact)
    final_run = _ensure_run(
        client,
        workflow=FINAL_WORKFLOW,
        label=FINAL_RUN_LABEL,
        digest=final_digest,
        inputs={
            "implementation_sha": implementation_sha,
            "upstream_digest": final_digest,
            "heldout_run_id": str(heldout_run["id"]),
        },
    )
    state["final_upstream_digest"] = final_digest
    state["final_run_id"] = int(final_run["id"]) if final_run else None
    if not _successful_terminal(final_run):
        state["state"] = "waiting_for_final_answer"
        return state

    final_artifact = client.artifact(
        int(final_run["id"]),
        prefix="final-answer-canonical-",
    )
    final_result = client.artifact_json(
        final_artifact,
        basename="final-answer-canonical.json",
    )
    state["final_artifact_digest"] = final_artifact.digest
    state["final_answer_gate_passed"] = bool(
        final_result.get("any_deployable_condition_passed")
    )
    terminal_digest = _digest(
        {
            "b2": b2_artifact.digest,
            "k3": k3_artifact.digest,
            "corrective": corrective_artifact.digest,
            "heldout": heldout_artifact.digest,
            "final": final_artifact.digest,
        }
    )
    state["terminal_digest"] = terminal_digest
    state["state"] = "terminal"

    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    marker = f"<!-- research-0.14-conveyor-terminal:{terminal_digest} -->"
    if not any(marker in str(comment.get("body", "")) for comment in client.issue_comments(TRACKING_ISSUE)):
        body = (
            marker
            + "\n## Research 0.14 conveyor reached terminal state\n\n"
            + f"- B2 run: \`{CANONICAL_B2_RUN}\`\n"
            + f"- structural K3 run: \`{k3_run['id']}\`; gate: \`{k3_gate}\`\n"
            + f"- corrective #431 run: \`{corrective_run['id']}\`; gate: \`{corrective_gate}\`\n"
            + f"- held-out #432 run: \`{heldout_run['id']}\`; broad gate: "
            + f"\`{state['heldout_broad_claim_gate_passed']}\`\n"
            + f"- final-answer #424 run: \`{final_run['id']}\`; any deployable gate: "
            + f"\`{state['final_answer_gate_passed']}\`\n"
            + f"- terminal evidence digest: \`{terminal_digest}\`\n\n"
            + "All stage selection was driven by preregistered machine-readable gates. "
            + "Negative scientific gates were preserved as evidence and were not retuned."
        )
        client.add_issue_comment(TRACKING_ISSUE, body)

    return state


def _client_from_args(args: argparse.Namespace) -> GitHubClient:
    repository = args.repository or os.environ.get("GITHUB_REPOSITORY", "")
    token = args.token or os.environ.get("GH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
    return GitHubClient(repository, token)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default="")
    parser.add_argument("--token", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    advance_parser = subparsers.add_parser("advance")
    advance_parser.add_argument("--implementation-sha", required=True)
    advance_parser.add_argument("--summary-out", type=Path)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--stage", choices=("corrective", "heldout", "final"), required=True)
    verify_parser.add_argument("--expected", required=True)
    verify_parser.add_argument("--b2-run-id", type=int)
    verify_parser.add_argument("--k3-run-id", type=int)
    verify_parser.add_argument("--corrective-run-id", type=int)
    verify_parser.add_argument("--heldout-run-id", type=int)

    args = parser.parse_args()
    client = _client_from_args(args)

    if args.command == "advance":
        result = advance(
            client,
            implementation_sha=args.implementation_sha,
            summary_out=args.summary_out,
        )
    else:
        result = verify_digest(
            client,
            stage=args.stage,
            expected=args.expected,
            b2_run_id=args.b2_run_id,
            k3_run_id=args.k3_run_id,
            corrective_run_id=args.corrective_run_id,
            heldout_run_id=args.heldout_run_id,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
