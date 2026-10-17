"""Fail-closed qualification ledger checker and deterministic checklist generator."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "benchmarks/qualification-control-v1.json"
DASHBOARD = ROOT / "QUALIFICATION.md"
MATRIX = ROOT / "docs/research/product-north-star-and-test-matrix.md"
MATRIX_PATTERN = re.compile(r"^\| ([GSRAEI]\d{2}) (P[012]) \|", re.MULTILINE)
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_LINK = re.compile(
    r"https://github\.com/JDeun/SchemaRouter/"
    r"(issues|pull|actions/runs)/\d+\Z"
)
STATES = (
    "BLOCKED_EXTERNAL",
    "DEV_ONLY",
    "ENGINEERING_ONLY",
    "HISTORICAL_NEGATIVE",
    "NOT_VERIFIED",
    "QUALIFIED",
)
BASE = "https://github.com/JDeun/SchemaRouter"


def invalid(message: str) -> None:
    raise ValueError("qualification ledger: " + message)


def load_control() -> dict[str, Any]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def validate_control(data: dict[str, Any], matrix: str) -> None:
    """Require exact 19-row canonical matrix and never infer completion."""
    if type(data) is not dict or data.get("schema_version") != 1:
        invalid("schema version must be 1")
    if data.get("source_matrix") != "docs/research/product-north-star-and-test-matrix.md":
        invalid("source matrix cannot change")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("reviewed_at"))):
        invalid("reviewed_at date required")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(data.get("published_release"))):
        invalid("published release must be semantic version")
    release = data.get("release")
    promotion = data.get("promotion")
    for label, gate, owners in (
        ("release", release, {1345, 1346}),
        ("promotion", promotion, {1339, 1346, 1450, 1477}),
    ):
        if type(gate) is not dict or gate.get("decision") not in ("HOLD", "APPROVED"):
            invalid(label + " decision must be HOLD or review-backed APPROVED")
        refs = gate.get("owners")
        if (
            type(refs) is not list or not refs
            or any(type(num) is not int or num <= 0 for num in refs)
            or not owners.issubset(set(refs))
        ):
            invalid(label + " required issue owners absent")
        if type(gate.get("reason")) is not str or not gate["reason"].strip():
            invalid(label + " must describe hold")
    if release.get("candidate") != "0.18.0" or release.get("held_pr") != 1356:
        invalid("held release identity changed")
    # Approval requires a separate reviewer and a frozen evidence record.
    # Neither green CI nor a resolved issue silently promotes a candidate.
    for label, gate in (("release", release), ("promotion", promotion)):
        proof = gate.get("approval")
        if gate["decision"] == "HOLD":
            if proof is not None:
                invalid(label + " HOLD cannot carry an approval receipt")
            continue
        required = (
            "approval_record_url", "exact_head_ci_url", "source_sha256",
            "artifact_sha256", "approved_by", "approved_at",
        )
        if type(proof) is not dict or any(
            type(proof.get(name)) is not str or not proof[name].strip()
            for name in required
        ):
            invalid(label + " lacks independent approval evidence")
        if (
            not SOURCE_LINK.fullmatch(proof["approval_record_url"])
            or not SOURCE_LINK.fullmatch(proof["exact_head_ci_url"])
            or not SHA256.fullmatch(proof["source_sha256"])
            or not SHA256.fullmatch(proof["artifact_sha256"])
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", proof["approved_at"])
        ):
            invalid(label + " malformed approval provenance")
        signed = proof.get("signed_off_issue_ids")
        if (
            type(signed) is not list
            or any(type(n) is not int for n in signed)
            or sorted(signed) != sorted(gate["owners"])
        ):
            invalid(label + " requires exact owner gate sign-off")
    expected = MATRIX_PATTERN.findall(matrix)
    if len(expected) != 19 or len(set(expected)) != 19:
        invalid("canonical source must contain 19 unique matrix rows")
    entries = data.get("items")
    if type(entries) is not list or len(entries) != 19:
        invalid("one entry per 19 matrix rows required")
    actual: list[tuple[str, str]] = []
    for item in entries:
        if type(item) is not dict:
            invalid("malformed entry")
        ident = item.get("id")
        priority = item.get("priority")
        if type(ident) is not str or type(priority) is not str:
            invalid("entry id/priority must be strings")
        actual.append((ident, priority))
        if item.get("status") not in STATES:
            invalid(ident + " invalid evidence status")
        if type(item.get("owner_issue")) is not int or item["owner_issue"] <= 0:
            invalid(ident + " needs owner issue")
        for key in ("blocker", "next_action"):
            if type(item.get(key)) is not str or not item[key].strip():
                invalid(ident + " missing " + key)
        links = item.get("evidence_links")
        if (
            type(links) is not list
            or any(type(uri) is not str or not SOURCE_LINK.fullmatch(uri) for uri in links)
            or len(set(links)) != len(links)
        ):
            invalid(ident + " invalid or duplicate evidence link")
        proof = item.get("qualification")
        if item["status"] == "QUALIFIED":
            if type(proof) is not dict or proof.get("evidence_tier") != "E2_INDEPENDENT":
                invalid(ident + " E2-independent acceptance proof required")
            required = (
                "run_url", "acceptance_record_url", "source_sha256",
                "artifact_sha256", "frozen_split_id", "independent_reviewer",
            )
            if any(type(proof.get(k)) is not str or not proof[k].strip() for k in required):
                invalid(ident + " incomplete independent acceptance")
            if not SOURCE_LINK.fullmatch(proof["run_url"]):
                invalid(ident + " untrusted evidence run")
            if not SOURCE_LINK.fullmatch(proof["acceptance_record_url"]):
                invalid(ident + " untrusted acceptance review")
            if not SHA256.fullmatch(proof["source_sha256"]):
                invalid(ident + " unverified frozen source hash")
            if not SHA256.fullmatch(proof["artifact_sha256"]):
                invalid(ident + " unverified artifact hash")
            if proof["run_url"] not in links:
                invalid(ident + " independent run omitted from evidence")
        elif proof is not None:
            invalid(ident + " unqualified row cannot carry E2 proof")
    if actual != expected:
        invalid("matrix IDs, order or priorities drifted")
    if promotion["decision"] == "APPROVED" and any(
        item["status"] != "QUALIFIED"
        for item in entries if item["priority"] in ("P0", "P1")
    ):
        invalid("model/default promotion requires every P0/P1 independent E2 gate")


def render_dashboard(data: dict[str, Any]) -> str:
    """Generated checklist is a view, not a second editable source of truth."""
    counts = Counter(row["status"] for row in data["items"])
    completed = counts["QUALIFIED"]
    tick = chr(96)
    lines = [
        "# SchemaRouter qualification checklist",
        "",
        "> AUTO-GENERATED — edit benchmarks/qualification-control-v1.json, "
        "then run python scripts/qualification_control.py --write. "
        "Do not edit this page independently.",
        "",
        f"**Reviewed:** {data['reviewed_at']} · "
        f"**published:** v{data['published_release']} · "
        f"**v{data['release']['candidate']} release:** "
        f"**{data['release']['decision']}** · "
        "**production model/default promotion:** "
        f"**{data['promotion']['decision']}**",
        "",
        f"**Independent qualification: {completed}/19.** "
        "This counts verified E2 only; implemented code, green CI, "
        "positive DEV and historical negative evidence are not passes.",
        "",
        "| Evidence status | Count |",
        "| --- | ---: |",
    ]
    for state in STATES:
        lines.append(f"| {state} | {counts[state]} |")
    lines.extend([
        "",
        "## Qualification gates",
        "",
        "Checking one item requires independent provenance, a frozen split, "
        "reproducible artifacts, a separate reviewer and the gate acceptance record. "
        "Closing an owner issue never auto-checks an item.",
        "",
    ])
    for row in data["items"]:
        mark = "x" if row["status"] == "QUALIFIED" else " "
        n = row["owner_issue"]
        links = " · ".join(
            f"[evidence {i + 1}]({uri})" for i, uri in enumerate(row["evidence_links"])
        ) or "No qualifying independent evidence registered"
        lines.extend([
            f"- [{mark}] **{row['id']} {row['priority']}** — "
            f"{tick}{row['status']}{tick} — [owner #{n}]({BASE}/issues/{n})",
            f"  - Blocker: {row['blocker']}",
            f"  - Next action: {row['next_action']}",
            f"  - Evidence: {links}",
        ])
    lines.extend([
        "",
        "## Separately reviewed release and promotion decisions",
        "",
        f"- **v0.18.0 release {data['release']['decision']}:** [#1345]({BASE}/issues/1345), "
        f"[#1346]({BASE}/issues/1346), and held [PR #1356]({BASE}/pull/1356). "
        "Qualify feasible external suites, fix real defects, then pass exact-head checks. "
        "Do not merge/tag/publish before approval.",
        f"- **Experimental/model default promotion {data['promotion']['decision']}:** "
        f"[#1477]({BASE}/issues/1477) integrated paired agent E2; "
        f"[#1339]({BASE}/issues/1339) language, "
        f"[#1450]({BASE}/issues/1450) authority, "
        f"[#1346]({BASE}/issues/1346) external independence. "
        "The v0.18 release decision and model promotion are distinct.",
        "- Preserve frozen #432/#424/#506 negative experiments. "
        "A synthetic model-agent result is not real-provider E2.",
        "",
        "## Update procedure",
        "",
        "1. Review current owner issue, exact case/source and permitted evidence.",
        "2. Change the canonical JSON row only; preserve non-qualifying evidence as DEV/negative.",
        "3. Regenerate with python scripts/qualification_control.py --write "
        "and check with --check; review GitHub Actions.",
        "4. Scheduled/manual Actions also perform a read-only check that owners "
        "stay consistent with unresolved gates and PR #1356 release decision. "
        "API outages are failures, not passes.",
        "",
        f"See [canonical evaluation matrix](docs/research/product-north-star-and-test-matrix.md), "
        f"[research tracker #200]({BASE}/issues/200) and "
        "[release checklist](docs/release-checklist.md).",
        "",
    ])
    return "\n".join(lines)


def live_check(data: dict[str, Any]) -> None:
    """Fail on closed/missing owners or prematurely merged release PR."""
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SchemaRouter-Qualification"}
    if token:
        headers["Authorization"] = "Bearer " + token

    def fetch(uri: str) -> dict[str, Any]:
        try:
            with urlopen(Request(uri, headers=headers), timeout=12) as resp:
                result = json.load(resp)
        except (HTTPError, URLError, TimeoutError) as exc:
            invalid("live GitHub check unavailable (" + type(exc).__name__ + ")")
        if type(result) is not dict:
            invalid("malformed live API response")
        return result

    owners = {row["owner_issue"] for row in data["items"]}
    owners |= set(data["release"]["owners"])
    owners |= set(data["promotion"]["owners"])
    required_open = {
        item["owner_issue"] for item in data["items"] if item["status"] != "QUALIFIED"
    }
    for gate in (data["release"], data["promotion"]):
        if gate["decision"] == "HOLD":
            required_open.update(gate["owners"])
    for number in sorted(owners):
        issue = fetch(f"https://api.github.com/repos/JDeun/SchemaRouter/issues/{number}")
        if issue.get("state") not in ("open", "closed"):
            invalid(f"owner issue #{number} has unknown state")
        if issue["state"] == "closed" and number in required_open:
            invalid(f"owner issue #{number} closed while a tracked gate is still open")
    release_pr = fetch(
        f"https://api.github.com/repos/JDeun/SchemaRouter/pulls/"
        f"{data['release']['held_pr']}"
    )
    if data["release"]["decision"] == "HOLD":
        if release_pr.get("state") != "open" or release_pr.get("merged_at") is not None:
            invalid("held release PR changed state; review before publishing")
    elif release_pr.get("state") == "closed" and release_pr.get("merged_at") is None:
        invalid("approved release PR was closed without a merge")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--check", action="store_true")
    choice.add_argument("--write", action="store_true")
    choice.add_argument("--summary", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    try:
        control = load_control()
        validate_control(control, MATRIX.read_text(encoding="utf-8"))
        expected = render_dashboard(control)
        if args.write:
            DASHBOARD.write_text(expected, encoding="utf-8")
            print("Updated " + str(DASHBOARD.relative_to(ROOT)))
        elif args.check:
            if not DASHBOARD.exists() or DASHBOARD.read_text(encoding="utf-8") != expected:
                invalid("generated page stale: run --write and commit")
            print("Qualification ledger consistent; this is NOT an E2 PASS.")
        else:
            counts = Counter(item["status"] for item in control["items"])
            print("Qualification: " + str(counts["QUALIFIED"]) + "/19; "
                  "release " + control["release"]["decision"] + "; model promotion "
                  + control["promotion"]["decision"])
            for status in STATES:
                print(status + ": " + str(counts[status]))
        if args.live:
            live_check(control)
            print("Owner issues and held PR checked live; no status automatically promoted.")
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
