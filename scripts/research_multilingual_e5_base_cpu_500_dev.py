"""Fresh EN/KO/JA native English 500-route fixed-K5 real CPU model A/B.

Two pinned E5 encoders only. Research diagnostic, not product default, no-fit
calibration, actual provider execution or independent E2.
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

from schemarouter import E5CachedEmbedder, EmbeddingDecisionBackend
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
BASE_MODEL = "intfloat/multilingual-e5-base"
BASE_REVISION = "d13f1b27baf31030b7fd040960d60d909913633f"
K = 5
CATALOG_ROUTES = 500
# New author-written, frozen BEFORE any score from this CPU A/B. No translations
# or host-attested multilingual labels are added to the native English source.
CASES = (
    ("en", "What is the formation energy of a vanadium oxide specimen?", "materials.search"),
    ("en", "Give the measurement unit reported for the gap energy.", "materials.units"),
    ("en", "Find journal research on lithium recycling techniques.", "papers.search"),
    (
        "en", "Check when flight CD819 is scheduled to arrive and whether it is delayed.",
        "flights.status",
    ),
    ("en", "Show the historical dollar-to-won foreign exchange rates.", "finance.exchange_history"),
    ("en", "Find a walking route from the port to the library.", "maps.directions"),
    ("ko", "산화바나듐 시편의 생성 에너지 측정 결과를 검색해.", "materials.search"),
    ("ko", "밴드갭 실험값에 표기된 물리 단위만 확인해.", "materials.units"),
    ("ko", "리튬 배터리 재활용에 관한 학술 논문을 찾아줘.", "papers.search"),
    ("ko", "CD819 항공편이 지연됐는지 도착 상태를 알려줘.", "flights.status"),
    ("ko", "달러 대비 원화 환율의 과거 추이를 확인해.", "finance.exchange_history"),
    ("ko", "항구에서 도서관까지 도보 길찾기 경로를 안내해.", "maps.directions"),
    ("ja", "酸化バナジウム試料の生成エネルギーの測定記録を探して。", "materials.search"),
    ("ja", "測定されたバンドギャップの単位だけを調べてください。", "materials.units"),
    ("ja", "リチウム電池のリサイクルに関する学術論文を検索してください。", "papers.search"),
    ("ja", "CD819便が遅れているか到着状況を確認してください。", "flights.status"),
    ("ja", "ドルと韓国ウォンの過去の為替レートを一覧で見せて。", "finance.exchange_history"),
    ("ja", "港から図書館まで徒歩で行く経路を教えてください。", "maps.directions"),
    ("en", "Charge my debit card to buy a rail ticket.", None),
    ("en", "Remove a scientific paper from the publisher's archive permanently.", None),
    ("ko", "외화 계좌에서 다른 사람에게 직접 송금해줘.", None),
    ("ko", "창고의 재고 수량을 실제로 100개 늘려서 저장해줘.", None),
    ("ja", "航空券の購入手続きを完了して決済してください。", None),
    ("ja", "材料データベースの測定記録を削除してください。", None),
)
SUPPORTED_ROUTES = frozenset(r for _, _, r in CASES if r is not None)


def validate_manifest() -> tuple[dict[str, Any], str]:
    if len(CASES) != 24 or len({q for _, q, _ in CASES}) != len(CASES):
        raise ValueError("fixed NEW case manifest drifted")
    for lang in ("en", "ko", "ja"):
        positives = sum(language == lang and gold is not None for language, _, gold in CASES)
        negatives = sum(language == lang and gold is None for language, _, gold in CASES)
        if (positives, negatives) != (6, 2):
            raise ValueError("fixed supported and unsupported denominators drifted")
    corpus, source_sha = load_development_corpus(CORPUS)
    router, _ = build_scaled_authorized_router(corpus, CATALOG_ROUTES)
    observed = {
        f"{tool.key}.{ep.name}"
        for tool in router.registry.tools()
        for ep in tool.endpoints
    }
    if len(observed) != CATALOG_ROUTES or not SUPPORTED_ROUTES.issubset(observed):
        raise ValueError("original native English catalog identity drifted")
    for tool in router.registry.tools():
        for ep in tool.endpoints:
            desc = tool.description + " " + ep.description
            if any("\uac00" <= c <= "\ud7a3" or "\u3040" <= c <= "\u30ff" for c in desc):
                raise ValueError("unapproved Korean/Japanese source translation")
    return corpus, source_sha


def load_base_cpu() -> tuple[EmbeddingDecisionBackend, dict[str, Any]]:
    import resource

    import torch  # pyright: ignore[reportMissingImports]
    from sentence_transformers import SentenceTransformer  # pyright: ignore[reportMissingImports]

    torch.manual_seed(20261019)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    start = time.perf_counter()
    model = SentenceTransformer(
        BASE_MODEL,
        revision=BASE_REVISION,
        trust_remote_code=False,
        device="cpu",
    )
    model.eval()
    if model.device.type != "cpu":
        raise RuntimeError("E5 base must remain on CPU")

    def encode(texts: list[str]) -> list[list[float]]:
        values = model.encode(
            texts,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return values.tolist()

    return EmbeddingDecisionBackend(
        E5CachedEmbedder(encode, max_cached_passages=500),
    ), {
        "model_id": BASE_MODEL,
        "model_revision": BASE_REVISION,
        "device": "cpu",
        "dimensions": model.get_sentence_embedding_dimension(),
        "load_ms": round((time.perf_counter() - start) * 1000, 3),
        "rss_mb_before_scoring": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3,
        ),
        "cpu_torch_threads": torch.get_num_threads(),
    }


def _measure(backend: Any) -> dict[str, Any]:
    corpus, _ = validate_manifest()
    router, catalog_sha = build_scaled_authorized_router(corpus, CATALOG_ROUTES)
    rows = []
    for idx, (lang, query, expected) in enumerate(CASES, 1):
        source_start = time.perf_counter_ns()
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        capture_ms = (time.perf_counter_ns() - source_start) / 1e6
        if len(view.visible_route_ids) != CATALOG_ROUTES:
            raise RuntimeError("incomplete principal-authorized original catalog")
        start = time.perf_counter_ns()
        lexical = router.retrieve_authorized(query, principal=PRINCIPAL, k=K)
        lexical_ms = (time.perf_counter_ns() - start) / 1e6
        selector = AuthorizedFixed5DecisionSelector(
            view, backend, max_model_input_bytes=262144,
        )
        start = time.perf_counter_ns()
        model_routes = tuple(selector(query, view.visible_route_ids))
        model_ms = (time.perf_counter_ns() - start) / 1e6
        lexical_routes = tuple(item.route_id for item in lexical.candidates)
        if lexical.total_ranked != CATALOG_ROUTES:
            raise RuntimeError("lexical catalog incomplete")
        visible = set(view.visible_route_ids)
        for routes in (lexical_routes, model_routes):
            if len(routes) != K or len(set(routes)) != K or not set(routes).issubset(visible):
                raise RuntimeError("unverified fixed-K5 source selection")
        if any(not math.isfinite(x) or x < 0 for x in (
            capture_ms, lexical_ms, model_ms,
        )):
            raise RuntimeError("invalid CPU time")
        view.assert_source_unchanged()
        rows.append({
            "id": f"fresh-crosslingual-{idx:02d}",
            "language": lang,
            "supported": expected is not None,
            "expected_route": expected,
            "source_capture_ms": round(capture_ms, 3),
            "lexical": {
                "routes": lexical_routes,
                "ms": round(lexical_ms, 3),
            },
            "model": {
                "routes": model_routes,
                "ms": round(model_ms, 3),
            },
        })
    return {"catalog_sha256": catalog_sha, "rows": rows}


def _report_arm(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    out = {}
    for lang in ("en", "ko", "ja"):
        yes = [r for r in rows if r["language"] == lang and r["supported"]]
        no = [r for r in rows if r["language"] == lang and not r["supported"]]
        assert len(yes) == 6 and len(no) == 2
        times = [r[arm]["ms"] for r in rows if r["language"] == lang]
        out[lang] = {
            "supported": len(yes),
            "top1_hit": sum(r[arm]["routes"][0] == r["expected_route"] for r in yes),
            "top5_hit": sum(r["expected_route"] in r[arm]["routes"] for r in yes),
            "unsupported": len(no),
            "unsupported_nonempty": sum(bool(r[arm]["routes"]) for r in no),
            "selection_median_ms": round(statistics.median(times), 3),
            "selection_p95_ms": round(percentile(times, 95), 3),
        }
    return out


def run() -> dict[str, Any]:
    corpus, source_digest = validate_manifest()
    small_backend, small_runtime = real_cpu_backend()
    small = _measure(small_backend)
    # Importantly both models see THE SAME predeclared 24 requests and original
    # English native source. Never update the source after observing A results.
    base_backend, base_runtime = load_base_cpu()
    base = _measure(base_backend)
    if small["catalog_sha256"] != base["catalog_sha256"]:
        raise ValueError("cross-model catalog source drift")
    lexical_match = all(
        a["lexical"]["routes"] == b["lexical"]["routes"]
        for a, b in zip(small["rows"], base["rows"], strict=True)
    )
    if not lexical_match:
        raise ValueError("unfair lexical baseline drift between models")
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(source_commit) != 40:
        raise ValueError("unknown original source commit")
    origin = Path("scripts/research_multilingual_e5_base_cpu_500_dev.py")
    return {
        "evidence": "REAL_E5_SMALL_VS_BASE_CPU_FRESH_SELF_AUTHORED_500_EN_ONLY_DEV",
        "source_commit": source_commit,
        "script_sha256": hashlib.sha256((ROOT / origin).read_bytes()).hexdigest(),
        "original_english_dev_sha256": source_digest,
        "original_native_catalog_sha256": small["catalog_sha256"],
        "models": {"e5_small": small_runtime, "e5_base": base_runtime},
        "registered_native_routes": CATALOG_ROUTES,
        "fixed_top_k": K,
        "supported": 18,
        "unsupported": 6,
        "original_provider_executions": 0,
        "independent_e2": False,
        "no_fit_calibrated": False,
        "product_default_changed": False,
        "summary": {
            "lexical": _report_arm(small["rows"], "lexical"),
            "e5_small": _report_arm(small["rows"], "model"),
            "e5_base": _report_arm(base["rows"], "model"),
        },
        "rows": [
            {
                "id": a["id"],
                "language": a["language"],
                "supported": a["supported"],
                "expected_route": a["expected_route"],
                "lexical": a["lexical"],
                "e5_small": a["model"],
                "e5_base": b["model"],
            }
            for a, b in zip(small["rows"], base["rows"], strict=True)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("validate", "real-cpu"))
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "artifacts/e5-base-paired-500-dev/report.json",
    )
    args = parser.parse_args()
    if args.mode == "validate":
        corpus, digest = validate_manifest()
        print(json.dumps({
            "source_routes": CATALOG_ROUTES,
            "source_catalog_origins": len(corpus["catalog"]),
            "source_sha256": digest,
            "fresh_self_authored_cases": len(CASES),
            "gold_not_model_input": True,
        }))
        return
    report = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence": report["evidence"],
        "models": report["models"],
        "summary": report["summary"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
