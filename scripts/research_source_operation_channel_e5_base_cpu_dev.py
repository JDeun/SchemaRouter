"""Source-only E5-base operation-identity channel vs native semantic description.

No model training, bilingual aliases, provider execution, or end-to-end agent
success. A fresh developer E1 cohort; not independent E2 or no-fit calibration.
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

from schemarouter.decisions import EmbeddingDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS, PRINCIPAL
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
from scripts.research_multilingual_e5_base_cpu_500_dev import load_base_cpu

ROOT = Path(__file__).resolve().parents[1]
ROUTES = 500
K = 5
# Fixed equal weighting in all languages and tasks, not calibrated on #1609.
DESCRIPTION_WEIGHT = 0.75
OPERATION_WEIGHT = 0.25
EVIDENCE_TIER = "SOURCE_ONLY_E5_BASE_OPERATION_CHANNEL_DEV_NO_E2"
# NEW manually authored tasks, distinct from previously published #1608/#1609
# requests and untouched after the first model run.
CASES = (
    ("en", "Locate measurements for a titanium nitride crystal.", "materials.search"),
    (
        "en", "Identify the physical units attached to formation-energy reporting.",
        "materials.units",
    ),
    ("en", "Get a bibliographic citation for DOI 10.5555/test-abc.", "papers.citations"),
    ("en", "Find scientific literature on battery electrolytes.", "papers.search"),
    ("en", "Find out whether flight GH302 has arrived on schedule.", "flights.status"),
    (
        "en", "Retrieve the historical exchange rate between yen and pounds.",
        "finance.exchange_history",
    ),
    ("ko", "질화티타늄 결정에 관한 측정 자료를 검색해.", "materials.search"),
    ("ko", "생성 에너지 데이터에 표시되는 측정 단위를 조회해 줘.", "materials.units"),
    ("ko", "DOI 10.5555/test-abc의 서지 인용 형식을 알려줘.", "papers.citations"),
    ("ko", "배터리 전해질 관련 학술 문헌을 검색해 줘.", "papers.search"),
    ("ko", "GH302편 비행기의 정시 도착 여부를 확인해.", "flights.status"),
    ("ko", "엔화와 파운드 환율의 역사적 변동을 찾아줘.", "finance.exchange_history"),
    ("ja", "窒化チタン結晶の測定データを検索してください。", "materials.search"),
    ("ja", "生成エネルギーの報告に用いる物理単位だけを教えて。", "materials.units"),
    ("ja", "DOI 10.5555/test-abcの書誌引用情報を取得してください。", "papers.citations"),
    ("ja", "電池電解質に関する研究論文を探してください。", "papers.search"),
    ("ja", "GH302便が予定どおりに到着したか確認してください。", "flights.status"),
    ("ja", "円と英ポンドの為替レートの過去の推移を見せて。", "finance.exchange_history"),
    ("en", "Delete the saved DOI citation from the database.", None),
    ("en", "Pay for and issue a new airline ticket.", None),
    ("ko", "새 논문을 출판사 사이트에 등록하고 제출해 줘.", None),
    ("ko", "은행 계좌에서 해외 송금을 실행해 줘.", None),
    ("ja", "材料データベースに測定結果を書き込んでください。", None),
    ("ja", "倉庫システムの在庫数を更新してください。", None),
)
EXPECTED = frozenset(gold for _, _, gold in CASES if gold is not None)


def source_catalog() -> tuple[Any, str, str]:
    if len(CASES) != 24 or len({query for _, query, _ in CASES}) != 24:
        raise ValueError("author-authored fixed corpus changed")
    for lang in ("en", "ko", "ja"):
        support = sum(language == lang and gold is not None
                      for language, _, gold in CASES)
        no_fit = sum(language == lang and gold is None
                     for language, _, gold in CASES)
        if (support, no_fit) != (6, 2):
            raise ValueError("language/gold denominators changed")
    corpus, sha = load_development_corpus(CORPUS)
    router, catalog_sha = build_scaled_authorized_router(corpus, ROUTES)
    names = {
        f"{tool.key}.{ep.name}"
        for tool in router.registry.tools() for ep in tool.endpoints
    }
    if len(names) != ROUTES or not EXPECTED.issubset(names):
        raise ValueError("native catalog count or route identity drift")
    # This source catalog has no typed output fields, as it is built from
    # English descriptions alone. Do not call our new channel "field-fit".
    if any(ep.output_fields for tool in router.registry.tools()
           for ep in tool.endpoints):
        raise ValueError("native source channel changed; new preregistration needed")
    return router, sha, catalog_sha


def _passages(rows: tuple[Any, ...]) -> tuple[list[str], list[str]]:
    full = []
    operation = []
    for route in rows:
        if type(route.route_id) is not str or not route.route_id.count(".") == 1:
            raise ValueError("invalid original native source route ID")
        if type(route.description) is not str:
            raise ValueError("invalid principal-authorized original source description")
        full.append(f"{route.route_id}\n{route.description}")
        suffix = route.route_id.rsplit(".", 1)[1].replace("_", " ").replace("-", " ")
        operation.append(f"Operation name: {suffix}")
    return full, operation


def weighted_rank(
    query_vector: list[float],
    full_vectors: list[list[float]],
    operation_vectors: list[list[float]],
    route_ids: tuple[str, ...],
    *,
    weight: float,
) -> list[str]:
    if (
        type(weight) is not float or not 0 <= weight <= 1
        or len(route_ids) != ROUTES
        or len(full_vectors) != ROUTES
        or len(operation_vectors) != ROUTES
        or len(set(route_ids)) != ROUTES
    ):
        raise ValueError("invalid native 500-route ranking")
    scored = []
    for index, (full, operation) in enumerate(
        zip(full_vectors, operation_vectors, strict=True)
    ):
        desc_cosine = EmbeddingDecisionBackend._cosine(query_vector, full)
        op_cosine = EmbeddingDecisionBackend._cosine(query_vector, operation)
        score = (1.0 - weight) * desc_cosine + weight * op_cosine
        if not math.isfinite(score):
            raise ValueError("nonfinite source-only semantic score")
        scored.append((index, score))
    ranked = sorted(scored, key=lambda row: (-row[1], row[0]))
    return [route_ids[index] for index, _ in ranked[:K]]


def _summary(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for lang in ("en", "ko", "ja"):
        positive = [r for r in rows if r["language"] == lang and r["supported"]]
        negative = [r for r in rows if r["language"] == lang and not r["supported"]]
        if len(positive) != 6 or len(negative) != 2:
            raise ValueError("invalid summary denominators")
        durations = [r[arm]["selection_ms"] for r in rows if r["language"] == lang]
        summary[lang] = {
            "supported": len(positive),
            "top1": sum(r[arm]["route_ids"][0] == r["expected"] for r in positive),
            "top5": sum(r["expected"] in r[arm]["route_ids"] for r in positive),
            "unsupported": len(negative),
            "unsupported_nonempty": sum(bool(r[arm]["route_ids"]) for r in negative),
            "selection_median_ms": round(statistics.median(durations), 3),
            "selection_p95_ms": round(percentile(durations, 95), 3),
        }
    return summary


def run() -> dict[str, Any]:
    router, source_sha, catalog_sha = source_catalog()
    backend, runtime = load_base_cpu()
    first = capture_authorized_agent_tool_surface(
        router, CASES[0][1], principal=PRINCIPAL,
    )
    rows = first._semantic_source_routes
    source_ids = first.visible_route_ids
    if len(rows) != ROUTES or tuple(r.route_id for r in rows) != source_ids:
        raise ValueError("incomplete authorized native source")
    descriptions, operations = _passages(rows)
    # Capture the model's exact E5 passage vectors from one original
    # source-scoped fixed corpus; all later queries reuse these vectors.
    started = time.perf_counter_ns()
    reference_query_vector, *vectors = backend.embedder(
        [CASES[0][1], *descriptions, *operations]
    )
    passage_ms = (time.perf_counter_ns() - started) / 1e6
    full_vectors = vectors[:ROUTES]
    operation_vectors = vectors[ROUTES:]
    if len(full_vectors) != ROUTES or len(operation_vectors) != ROUTES:
        raise RuntimeError("missing original source passage embedding")
    original_first = AuthorizedFixed5DecisionSelector(
        first, backend, max_model_input_bytes=262144,
    )(CASES[0][1], source_ids)
    # Match the existing source-authorized E5 comparator exactly; this is a
    # source-representation equivalence check, never a gold label check.
    observed_original = weighted_rank(
        reference_query_vector,
        full_vectors, operation_vectors, source_ids,
        weight=0.0,
    )
    if observed_original != original_first:
        raise RuntimeError("reference source-only model ranking disagrees")
    first.assert_source_unchanged()
    original_fps = tuple(
        (r.tool_fingerprint, r.endpoint_fingerprint) for r in rows
    )
    scored_rows = []
    for idx, (lang, query, gold) in enumerate(CASES, 1):
        captured = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        if (
            captured.visible_route_ids != source_ids
            or _passages(captured._semantic_source_routes) != (descriptions, operations)
            or tuple(
                (r.tool_fingerprint, r.endpoint_fingerprint)
                for r in captured._semantic_source_routes
            ) != original_fps
        ):
            raise RuntimeError("cross-query scope/source contract drift")
        start = time.perf_counter_ns()
        query_vector = backend.embedder([query])[0]
        encode_ms = (time.perf_counter_ns() - start) / 1e6
        arms: dict[str, Any] = {}
        for name, weight in (("source_e5", 0.0), ("operation_25", OPERATION_WEIGHT)):
            begin = time.perf_counter_ns()
            route_ids = weighted_rank(
                query_vector, full_vectors, operation_vectors,
                source_ids, weight=weight,
            )
            score_ms = (time.perf_counter_ns() - begin) / 1e6
            if len(route_ids) != K or len(set(route_ids)) != K:
                raise RuntimeError("not an exact registered K5")
            arms[name] = {
                "route_ids": route_ids,
                "selection_ms": round(encode_ms + score_ms, 3),
            }
        captured.assert_source_unchanged()
        scored_rows.append({
            "id": f"new-ops-channel-{idx:02d}",
            "language": lang,
            "supported": gold is not None,
            "expected": gold,
            **arms,
        })
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    path = "scripts/research_source_operation_channel_e5_base_cpu_dev.py"
    return {
        "tier": EVIDENCE_TIER,
        "source_commit": source_commit,
        "script_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
        "native_source_sha256": source_sha,
        "source_catalog_sha256": catalog_sha,
        "source_routes": ROUTES,
        "k": K,
        "model": runtime,
        "source_passage_precompute_ms": round(passage_ms, 3),
        "new_self_authored_queries": len(CASES),
        "original_native_field_specs_present": False,
        "gold_sent_to_encoder": False,
        "no_fit_calibrated": False,
        "independent_e2": False,
        "provider_executions": 0,
        "default_changed": False,
        "weights": {
            "source_description": DESCRIPTION_WEIGHT,
            "source_operation_name": OPERATION_WEIGHT,
        },
        "summary": {
            name: _summary(scored_rows, name)
            for name in ("source_e5", "operation_25")
        },
        "rows": scored_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("validate", "real-cpu"), required=True)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "artifacts/source-operation-channel-e5-cpu/report.json",
    )
    args = parser.parse_args()
    if args.mode == "validate":
        router, corpus_sha, catalog_sha = source_catalog()
        print(json.dumps({
            "native_routes": sum(len(tool.endpoints) for tool in router.registry.tools()),
            "new_fixed_cases": len(CASES),
            "source_sha256": corpus_sha,
            "catalog_sha256": catalog_sha,
            "native_output_field_specs": 0,
        }))
        return
    result = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "tier": result["tier"],
        "source_passage_precompute_ms": result["source_passage_precompute_ms"],
        "summary": result["summary"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
