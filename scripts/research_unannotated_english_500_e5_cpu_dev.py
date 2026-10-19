"""Actual pinned multilingual E5 vs native lexical K5 on English-only 500-route DEV.

All questions are newly authored E1-DEV (not independent E2). No task text,
expected result or annotation is sent to the model except the original query.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    CORPUS,
    PRINCIPAL,
    real_cpu_backend,
)
from scripts.evaluate_authorized_e5_scale_500_cpu_dev import (
    build_scaled_authorized_router,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import (
    load_development_corpus,
    percentile,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)

ROOT = Path(__file__).resolve().parents[1]
K = 5
ROUTES = 500
EVIDENCE_TIER = "REAL_PINNED_E5_CPU_ENGLISH_ONLY_NATIVE_500_E1_DEV"
# New unannotated Korean/Japanese questions; English routes retain only source
# English metadata, without user-language equivalences or gold-route injection.
# Supported and unsupported denominators were fixed BEFORE the first model run.
CASES = (
    ("en", "Retrieve the reported formation energy for silicon carbide.", "materials.search"),
    ("en", "How many units of SKU TR-91 remain in the warehouse?", "inventory.lookup"),
    ("en", "Is the departure of flight AB201 running late?", "flights.status"),
    (
        "en", "Show the past quarter's exchange-rate history for euros versus dollars.",
        "finance.exchange_history",
    ),
    ("en", "Find the bibliographic reference details of DOI 10.1038/sample.", "papers.citations"),
    (
        "en", "I only need the declared units of the material measurement, not its measured values.",
        "materials.units",
    ),
    ("ko", "탄화규소 시료의 측정된 밀도 자료를 찾아줘.", "materials.search"),
    ("ko", "품목 코드 TR-91이 창고에 몇 개 남아 있는지 조회해 줘.", "inventory.lookup"),
    ("ko", "항공편 AB201편이 지연 중인지 확인해 줘.", "flights.status"),
    ("ko", "지난 분기 유로와 달러 환율 변동 기록을 보여줘.", "finance.exchange_history"),
    ("ko", "DOI 10.1038/sample에 대한 논문 인용 정보를 확인해 줘.", "papers.citations"),
    ("ko", "소재 측정 결과의 단위 정보만 알려줘. 측정값은 필요 없어.", "materials.units"),
    ("ja", "炭化ケイ素の測定密度データを検索してください。", "materials.search"),
    ("ja", "SKU TR-91 の倉庫在庫数を調べてください。", "inventory.lookup"),
    ("ja", "便名 AB201 の遅延状況を確認してください。", "flights.status"),
    (
        "ja", "前四半期のユーロとドルの為替レート推移を表示してください。",
        "finance.exchange_history",
    ),
    ("ja", "DOI 10.1038/sample の引用書誌情報を教えてください。", "papers.citations"),
    ("ja", "材料測定の単位情報だけを取得してください。測定値は不要です。", "materials.units"),
    ("en", "Create and send a paid invoice to a customer.", None),
    ("en", "Purchase and issue a new airline ticket right now.", None),
    ("ko", "데이터베이스에서 재료 레코드를 영구 삭제해 줘.", None),
    ("ko", "주문을 결제하고 항공권을 발권해 줘.", None),
    ("ja", "在庫数を50個増やして保存してください。", None),
    ("ja", "登録済みのカレンダー予定を削除してください。", None),
)
SUPPORTED_ROUTES = frozenset(case[2] for case in CASES if case[2] is not None)


def validate_cases_and_source() -> tuple[dict[str, Any], str]:
    assert len(CASES) == 24 and len({c[1] for c in CASES}) == len(CASES)
    for lang in ("en", "ko", "ja"):
        assert sum(c[0] == lang and c[2] is not None for c in CASES) == 6
        assert sum(c[0] == lang and c[2] is None for c in CASES) == 2
    corpus, digest = load_development_corpus(CORPUS)
    router, _ = build_scaled_authorized_router(corpus, ROUTES)
    routes = {
        f"{tool.key}.{endpoint.name}": (tool, endpoint)
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    }
    if len(routes) != ROUTES or not SUPPORTED_ROUTES.issubset(routes):
        raise AssertionError("500 source-native English routes or gold mapping missing")
    for tool, endpoint in routes.values():
        content = " ".join((tool.description, endpoint.description))
        if any("\uac00" <= ch <= "\ud7a3" or "\u3040" <= ch <= "\u30ff" for ch in content):
            raise AssertionError("provider English source contains translated CJK hints")
        if not endpoint.read_only:
            raise AssertionError("native DEV source is not read only")
    return corpus, digest


def _summary(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    output = {}
    for lang in ("en", "ko", "ja"):
        positive = [r for r in rows if r["language"] == lang and r["supported"]]
        negative = [r for r in rows if r["language"] == lang and not r["supported"]]
        durations = [r["arms"][arm]["selection_ms"] for r in rows if r["language"] == lang]
        if len(positive) != 6 or len(negative) != 2:
            raise AssertionError("missing language-stratified DEV cases")
        output[lang] = {
            "supported_n": 6,
            "hit_at_1": sum(r["arms"][arm]["hit_1"] for r in positive),
            "hit_at_5": sum(r["arms"][arm]["hit_5"] for r in positive),
            "unsupported_n": 2,
            "unsupported_nonempty": sum(
                r["arms"][arm]["nonempty"] for r in negative
            ),
            "selection_ms_p50": round(statistics.median(durations), 3),
            "selection_ms_p95": round(percentile(durations, 95), 3),
        }
    return output


def run_real_cpu_dev(backend: Any, runtime: dict[str, Any]) -> dict[str, Any]:
    corpus, digest = validate_cases_and_source()
    router, catalog_digest = build_scaled_authorized_router(corpus, ROUTES)
    rows = []
    for index, (language, query, expected) in enumerate(CASES, 1):
        captured_at = time.perf_counter_ns()
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        source_capture_ms = (time.perf_counter_ns() - captured_at) / 1e6
        if len(view.visible_route_ids) != ROUTES:
            raise AssertionError("source or principal scoped route count drift")
        began = time.perf_counter_ns()
        lexical_result = router.retrieve_authorized(query, principal=PRINCIPAL, k=K)
        lexical_ms = (time.perf_counter_ns() - began) / 1e6
        lexical = tuple(c.route_id for c in lexical_result.candidates)
        # The backend receives only the ORIGINAL query and scoped native
        # English route descriptions, never the gold in expected.
        selector = AuthorizedFixed5DecisionSelector(
            view, backend, max_model_input_bytes=262144,
        )
        began = time.perf_counter_ns()
        e5 = tuple(selector(query, view.visible_route_ids))
        e5_ms = (time.perf_counter_ns() - began) / 1e6
        original_routes = set(view.visible_route_ids)
        if (
            lexical_result.total_ranked != ROUTES
            or len(lexical) != K or len(e5) != K
            or len(set(lexical)) != K or len(set(e5)) != K
            or not set(lexical).issubset(original_routes)
            or not set(e5).issubset(original_routes)
            or any(not math.isfinite(x) or x < 0
                   for x in (source_capture_ms, lexical_ms, e5_ms))
        ):
            raise AssertionError("not a source-authorized fixed K5 comparison")
        view.assert_source_unchanged()
        arms = {}
        for arm, ranking, elapsed in (
            ("lexical_k5", lexical, lexical_ms),
            ("real_e5_k5", e5, e5_ms),
        ):
            arms[arm] = {
                "route_ids": list(ranking),
                "hit_1": expected is not None and ranking[0] == expected,
                "hit_5": expected is not None and expected in ranking,
                "nonempty": len(ranking) > 0,
                "selection_ms": round(elapsed, 3),
            }
        rows.append({
            "id": f"original-english-source-e1dev-{index:02d}",
            "language": language,
            "supported": expected is not None,
            "expected_route": expected,
            "source_capture_ms": round(source_capture_ms, 3),
            "arms": arms,
        })
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if len(revision) != 40:
        raise RuntimeError("unverified runner revision")
    sources = (
        "scripts/research_unannotated_english_500_e5_cpu_dev.py",
        "benchmarks/multilingual-embedding-cpu-dev-20261015.json",
        "scripts/evaluate_authorized_e5_scale_500_cpu_dev.py",
    )
    return {
        "evidence_tier": EVIDENCE_TIER,
        "source_commit": revision,
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in sources
        },
        "catalog_sha256": catalog_digest,
        "source_input_corpus_sha256": digest,
        "source_routes": ROUTES,
        "top_k": K,
        "fresh_dev_cases": len(rows),
        "supported_cases": 18,
        "unsupported_cases": 6,
        "model_input": "original_untranslated_queries_and_english_native_source_only",
        "language_aliases": False,
        "real_model": True,
        "provider_executions": 0,
        "independent_quality_evidence": False,
        "calibrated_no_fit": False,
        "may_promote": False,
        "model_runtime": runtime,
        "summary": {
            arm: _summary(rows, arm)
            for arm in ("lexical_k5", "real_e5_k5")
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("validate", "real-e5-cpu"), required=True)
    parser.add_argument("--out", type=Path,
                        default=Path("artifacts/unannotated-en-500-e5-dev/report.json"))
    args = parser.parse_args()
    if args.mode == "validate":
        corpus, digest = validate_cases_and_source()
        print(json.dumps({
            "source_catalog_n": len(corpus["catalog"]),
            "synthetic_registered_n": ROUTES,
            "fresh_author_dev_cases": len(CASES),
            "supported": 18,
            "unsupported": 6,
            "source_corpus_sha256": digest,
            "evidence": "NEW_SELF_AUTHORED_DEV_MANIFEST_NOT_INDEPENDENT",
        }))
        return
    backend, runtime = real_cpu_backend()
    result = run_real_cpu_dev(backend, runtime)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": result["evidence_tier"],
        "source_commit": result["source_commit"],
        "source_routes": result["source_routes"],
        "model": runtime["model_id"],
        "model_revision": runtime["model_revision"],
        "summary": result["summary"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
