"""Developer-authored EN/KO/JA phrase bridge A/B on original native Top-K.

An E0 *engineering* diagnostic, not independent English-only multilingual
generalization, learned translation or external model task success.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import SemanticEquivalence
from scripts.research_declared_concept_graph_bridge_e0 import (
    DeclaredConceptGraphAnalyzer,
)

ROOT = Path(__file__).resolve().parents[1]
K = 1
VIEWER = PrincipalContext(subject="dev-viewer", roles=("viewer",))

CONCEPTS = (
    SemanticEquivalence(
        canonical_id="mechanical.elastic_modulus",
        aliases={"탄성계수", "ヤング率", "Youngs modulus"},
    ),
    SemanticEquivalence(
        canonical_id="thermal.conductivity",
        aliases={"열전도율", "熱伝導率", "thermal conductivity"},
    ),
    SemanticEquivalence(
        canonical_id="spectroscopy.raman_shift",
        aliases={"라만피크", "ラマンピーク", "Raman peak"},
    ),
)

# Newly author-written visible DEV, not a real publisher/independent cohort.
CASES = (
    ("ko", "탄성계수를 조회해 주세요.", "z_mechanics.read"),
    ("ja", "ヤング率を確認してください。", "z_mechanics.read"),
    ("en", "Please retrieve Youngs modulus for the sample.", "z_mechanics.read"),
    ("ko", "열전도율 값을 확인해 주세요.", "z_thermal.read"),
    ("ja", "熱伝導率を調べてください。", "z_thermal.read"),
    ("en", "Fetch thermal conductivity for the sample.", "z_thermal.read"),
    ("ko", "라만피크를 분석해 주세요.", "z_spectroscopy.read"),
    ("ja", "ラマンピークを教えてください。", "z_spectroscopy.read"),
    ("en", "Show Raman peak for the sample.", "z_spectroscopy.read"),
    ("ko", "로그인 암호를 변경해 주세요.", None),
    ("ja", "航空券を予約してください。", None),
    ("en", "Please transfer funds to another bank.", None),
    ("ko", "탄성계수는 제외하고 조회해 주세요.", None),
    ("ja", "ヤング率は使わないでください。", None),
    ("en", "Do not use Youngs modulus.", None),
    ("ko", "탄성계수 열전도율 둘 다 비교해 주세요.", None),
)
assert len(CASES) == 16


def build_router(mode: str) -> SchemaRouter:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("viewer",),
        ),),
        data_rules=(
            DataScopeRule(
                operation="*.*", roles_any=("viewer",),
                visible_fields=("public_value",),
            ),
        ),
    )
    router = SchemaRouter(
        authorization_policy=policy,
        analyzer=(
            DeclaredConceptGraphAnalyzer(CONCEPTS, match_mode=mode)
            if mode in ("exact", "bounded_phrase") else None
        ),
    )
    registrations = (
        ("a_decoy", "unrelated.records"),
        ("z_mechanics", "mechanical.elastic_modulus"),
        ("z_thermal", "thermal.conductivity"),
        ("z_spectroscopy", "spectroscopy.raman_shift"),
    )
    for name, concept in registrations:
        router.add_tool(ToolSpec(
            name=name,
            description="English-only native capability metadata",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[
                    FieldSpec(
                        name="public_value", semantic_id=concept,
                        json_schema={"type": "number"},
                    ),
                    FieldSpec(name="private_value", json_schema={"type": "number"}),
                ],
            )],
        ))
    return router


def evaluate() -> dict:
    routers = {
        name: build_router(name)
        for name in ("exact", "bounded_phrase")
    }
    rows = []
    for index, (language, query, expected) in enumerate(CASES):
        observed = {}
        for arm, router in routers.items():
            before = time.perf_counter_ns()
            result = router.retrieve_authorized(query, principal=VIEWER, k=K)
            elapsed = (time.perf_counter_ns() - before) / 1e6
            if len(result.candidates) != K or result.total_ranked != 4:
                raise AssertionError("unbounded or incomplete fixed-K DEV catalog")
            candidate = result.candidates[0]
            if candidate.route_id not in {
                "a_decoy.read", "z_mechanics.read", "z_thermal.read",
                "z_spectroscopy.read",
            } or not candidate.tool_fingerprint:
                raise AssertionError("invalid original registered route receipt")
            observed[arm] = {
                "route_id": candidate.route_id,
                "score": round(candidate.score, 5),
                "positive_evidence": candidate.score > 0,
                "latency_ms": round(elapsed, 5),
                "supported_hit": bool(
                    expected is not None and
                    candidate.route_id == expected and candidate.score > 0
                ),
            }
        rows.append({
            "case_id": f"prospective-dev-{index + 1:02d}",
            "language": language,
            "supported": expected is not None,
            "expected_route_id": expected,
            "arms": observed,
        })

    summary = {}
    for arm in routers:
        summary[arm] = {}
        for lang in ("en", "ko", "ja"):
            positives = [
                r["arms"][arm] for r in rows
                if r["language"] == lang and r["supported"]
            ]
            negatives = [
                r["arms"][arm] for r in rows
                if r["language"] == lang and not r["supported"]
            ]
            if len(positives) != 3 or not negatives:
                raise AssertionError("lost prospective DEV denominator")
            summary[arm][lang] = {
                "supported_n": len(positives),
                "positive_evidence_top1_hits": sum(
                    r["supported_hit"] for r in positives
                ),
                "unsupported_n": len(negatives),
                "unsupported_positive_evidence": sum(
                    r["positive_evidence"] for r in negatives
                ),
            }
    sources = (
        "scripts/research_declared_concept_graph_bridge_e0.py",
        "scripts/research_multilingual_declared_phrase_dev.py",
    )
    identity = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in sources
    }
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        check=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "evidence_tier": "E0_SELF_AUTHORED_DEV_NOT_INDEPENDENT",
        "source_commit": revision,
        "source_file_sha256": identity,
        "k": K,
        "native_tool_routes": 4,
        "models_used": False,
        "tool_executions": 0,
        "independent_confirmation": False,
        "may_promote": False,
        "may_release": False,
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    report = evaluate()
    destination = ROOT / "artifacts" / "multilingual-phrase-e0" / "report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "source_commit": report["source_commit"],
        "summary": report["summary"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
