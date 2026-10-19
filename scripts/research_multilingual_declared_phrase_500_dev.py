"""Prospective 500-route EN/KO/JA self-authored paired Top1 E0 stress test.

Not frozen #432, no model, no independent E2, no source tool execution.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import time

from schemarouter import EndpointSpec, FieldSpec, ToolSpec
from scripts.research_multilingual_declared_phrase_dev import ROOT, VIEWER, build_router

ROUTES = 500
# Never reuse the first 16 author-written cases or the historical frozen cohort.
CASES = (
    ("ko", "이 소재의 탄성계수는 얼마나 되는지 알려주세요.", "z_mechanics.read"),
    ("ja", "この試料の熱伝導率を一覧で示してください。", "z_thermal.read"),
    ("ko", "측정 결과에 나온 라만피크를 정리해 주세요.", "z_spectroscopy.read"),
    ("ja", "試験片のヤング率を教えていただけますか。", "z_mechanics.read"),
    ("en", "What is the thermal conductivity of this material?", "z_thermal.read"),
    ("en", "Find the measured Raman peak on this sample.", "z_spectroscopy.read"),
    ("ko", "여행 일정 알림을 끄고 싶어요.", None),
    ("ja", "書類の署名をお願いします。", None),
    ("ko", "탄성계수와 열전도율 둘 다 비교해야 합니다.", None),
    ("ja", "ヤング率は使わないでください。", None),
    ("en", "Do not select Raman peak for this calculation.", None),
)


def build_500_router(mode: str):
    router = build_router(mode)
    for i in range(ROUTES - 4):
        router.add_tool(ToolSpec(
            name=f"noise_catalog_{i:03d}",
            description="English only archive capability",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[
                    FieldSpec(
                        name="public_value", semantic_id=f"archive.noise_{i:03d}",
                        json_schema={"type": "number"},
                    ),
                    FieldSpec(name="private_value"),
                ],
            )],
        ))
    assert len(router.registry.tools()) == ROUTES
    return router


def evaluate() -> dict:
    routers = {mode: build_500_router(mode) for mode in ("exact", "bounded_phrase")}
    rows = []
    for number, (language, query, expected) in enumerate(CASES, start=1):
        arms = {}
        for name, router in routers.items():
            start = time.perf_counter_ns()
            retrieval = router.retrieve_authorized(query, principal=VIEWER, k=1)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            assert retrieval.total_ranked == ROUTES
            assert len(retrieval.candidates) == 1
            top = retrieval.candidates[0]
            assert top.tool_fingerprint and top.endpoint_fingerprint
            assert all(f.name != "private_value" for f in top.output_fields)
            arms[name] = {
                "top1_route": top.route_id,
                "positive_evidence": top.score > 0,
                "supported_hit": (
                    expected is not None and top.route_id == expected
                    and top.score > 0
                ),
                "wall_ms": round(elapsed_ms, 3),
            }
        rows.append({
            "id": f"new-e0-{number:02d}",
            "language": language,
            "supported": expected is not None,
            "expected": expected,
            "arms": arms,
        })
    summary = {}
    for mode in routers:
        summary[mode] = {}
        for lang in ("en", "ko", "ja"):
            positive = [r for r in rows if r["language"] == lang and r["supported"]]
            negative = [r for r in rows if r["language"] == lang and not r["supported"]]
            durations = [r["arms"][mode]["wall_ms"] for r in rows if r["language"] == lang]
            summary[mode][lang] = {
                "supported_n": len(positive),
                "correct_positive_top1": sum(r["arms"][mode]["supported_hit"] for r in positive),
                "unsupported_n": len(negative),
                "unsupported_positive": sum(
                    r["arms"][mode]["positive_evidence"] for r in negative
                ),
                "diagnostic_wall_ms_median": round(statistics.median(durations), 3),
                "diagnostic_wall_ms_max": max(durations),
            }
    sources = (
        "scripts/research_declared_concept_graph_bridge_e0.py",
        "scripts/research_multilingual_declared_phrase_dev.py",
        "scripts/research_multilingual_declared_phrase_500_dev.py",
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "evidence_tier": "E0_AUTHOR_WRITTEN_500_ROUTES_NOT_E2",
        "source_commit": revision,
        "sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sources
        },
        "catalog_routes": ROUTES,
        "k": 1,
        "no_model": True,
        "tool_executions": 0,
        "independent": False,
        "promotable": False,
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    report = evaluate()
    target = ROOT / "artifacts" / "declared-phrase-500-e0" / "report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {"evidence_tier": report["evidence_tier"], "summary": report["summary"]},
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
