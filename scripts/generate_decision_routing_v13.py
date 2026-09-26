"""Generate the v13 blind-final routing corpus after the candidate freeze.

The exact corpus is created only inside the one-shot evaluation workflow. This script
prints aggregate metadata only; it never prints generated queries.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_V2_GENERATOR = Path(__file__).with_name("generate_decision_routing_v2.py")
_spec = importlib.util.spec_from_file_location("generate_decision_routing_v2", _V2_GENERATOR)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load decision-routing v2 generator")
_v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v2)
CONFIG: dict[str, Any] = _v2.CONFIG

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
ROUTE_PAIRS = (
    ("weather.current", "weather.forecast"),
    ("materials.search", "materials.structure"),
    ("papers.search", "papers.citations"),
    ("finance.quote", "finance.history"),
    ("calendar.list", "calendar.create"),
    ("support.search", "support.create_ticket"),
    ("inventory.search", "inventory.update"),
    ("users.lookup", "users.update"),
)

SUPPORTED_WRAPPERS = {
    "en": (
        "Handle exactly this request: {core}.",
        "The result I need is specifically this: {core}.",
        "Use the matching operation for this action only: {core}.",
        "Please route this by the requested action, then {core}.",
    ),
    "ko": (
        "이 요청만 정확히 처리해줘: {core}.",
        "내가 필요한 결과는 이것뿐이야: {core}.",
        "이 동작에 맞는 기능만 사용해서 {core}.",
        "요청한 동작 기준으로 라우팅해서 {core}.",
    ),
    "es": (
        "Gestiona exactamente esta solicitud: {core}.",
        "El resultado que necesito es específicamente este: {core}.",
        "Usa solo la operación que corresponde a esta acción: {core}.",
        "Enruta según la acción solicitada y después {core}.",
    ),
    "ja": (
        "この依頼だけを正確に処理して: {core}。",
        "必要な結果はこれだけです: {core}。",
        "この操作に合う機能だけを使って{core}。",
        "要求された操作に基づいてルーティングし、{core}。",
    ),
    "de": (
        "Bearbeite genau diese Anfrage: {core}.",
        "Ich brauche ausdrücklich nur dieses Ergebnis: {core}.",
        "Nutze nur die zu dieser Aktion passende Operation: {core}.",
        "Route nach der angeforderten Aktion und dann {core}.",
    ),
    "mixed": (
        "이 request만 정확히 처리해: {core}.",
        "내가 필요한 result는 이것뿐이야: {core}.",
        "이 action에 맞는 operation만 써서 {core}.",
        "requested action 기준으로 route한 뒤 {core}.",
    ),
}

NEAR_DOMAIN = {
    "weather": {
        "en": "show severe weather alerts for Seoul",
        "ko": "서울의 기상 특보를 보여줘",
        "es": "muestra las alertas meteorológicas severas de Seúl",
        "ja": "ソウルの気象警報を表示して",
        "de": "zeige Unwetterwarnungen für Seoul",
        "mixed": "서울 severe weather alert를 보여줘",
    },
    "materials": {
        "en": "predict synthesis conditions for LiFePO4",
        "ko": "LiFePO4의 합성 조건을 예측해줘",
        "es": "predice las condiciones de síntesis de LiFePO4",
        "ja": "LiFePO4の合成条件を予測して",
        "de": "sage Synthesebedingungen für LiFePO4 voraus",
        "mixed": "LiFePO4 synthesis condition을 predict해줘",
    },
    "papers": {
        "en": "download the full text PDF for DOI 10.5555/example",
        "ko": "DOI 10.5555/example 논문의 원문 PDF를 다운로드해줘",
        "es": "descarga el PDF de texto completo del DOI 10.5555/example",
        "ja": "DOI 10.5555/example の全文PDFをダウンロードして",
        "de": "lade das Volltext-PDF für DOI 10.5555/example herunter",
        "mixed": "DOI 10.5555/example full-text PDF를 download해줘",
    },
    "finance": {
        "en": "place a market buy order for AAPL",
        "ko": "AAPL 시장가 매수 주문을 넣어줘",
        "es": "coloca una orden de compra a mercado para AAPL",
        "ja": "AAPLの成行買い注文を出して",
        "de": "platziere eine Market-Kauforder für AAPL",
        "mixed": "AAPL market buy order를 place해줘",
    },
    "calendar": {
        "en": "delete tomorrow's team sync from my calendar",
        "ko": "내일 팀 미팅을 캘린더에서 삭제해줘",
        "es": "elimina la reunión de equipo de mañana de mi calendario",
        "ja": "明日のチームミーティングをカレンダーから削除して",
        "de": "lösche den Team-Termin morgen aus meinem Kalender",
        "mixed": "내일 team sync를 calendar에서 delete해줘",
    },
    "support": {
        "en": "close support ticket 4821 as resolved",
        "ko": "고객지원 티켓 4821을 해결됨으로 종료해줘",
        "es": "cierra el ticket de soporte 4821 como resuelto",
        "ja": "サポートチケット4821を解決済みとして閉じて",
        "de": "schließe Support-Ticket 4821 als gelöst",
        "mixed": "support ticket 4821을 resolved로 close해줘",
    },
    "inventory": {
        "en": "delete SKU-778 from the product catalog",
        "ko": "상품 카탈로그에서 SKU-778을 삭제해줘",
        "es": "elimina SKU-778 del catálogo de productos",
        "ja": "商品カタログからSKU-778を削除して",
        "de": "lösche SKU-778 aus dem Produktkatalog",
        "mixed": "product catalog에서 SKU-778을 delete해줘",
    },
    "users": {
        "en": "delete user account 314",
        "ko": "사용자 계정 314를 삭제해줘",
        "es": "elimina la cuenta de usuario 314",
        "ja": "ユーザーアカウント314を削除して",
        "de": "lösche Benutzerkonto 314",
        "mixed": "user account 314를 delete해줘",
    },
}

NEAR_WRAPPERS = {
    "en": (
        "Within this same domain, I need you to {core}.",
        "This is related to the tool, but the requested action is to {core}.",
        "Do not substitute a nearby supported operation; {core}.",
        "The exact action is unsupported unless the tool can {core}.",
    ),
    "ko": (
        "같은 도메인 요청이지만 {core}.",
        "이 도구와 관련은 있지만 필요한 동작은 {core}.",
        "비슷한 지원 동작으로 바꾸지 말고 {core}.",
        "정확히 필요한 동작은 {core}.",
    ),
    "es": (
        "Dentro del mismo dominio, necesito que {core}.",
        "Está relacionado con la herramienta, pero la acción solicitada es {core}.",
        "No sustituyas una operación compatible parecida; {core}.",
        "La acción exacta requerida es {core}.",
    ),
    "ja": (
        "同じドメインですが、必要なのは{core}。",
        "このツールに関連していますが、要求された操作は{core}。",
        "近い対応操作に置き換えず、{core}。",
        "正確に必要な操作は{core}。",
    ),
    "de": (
        "Im selben Bereich brauche ich, dass du {core}.",
        "Es gehört zum selben Tool, aber die angeforderte Aktion ist: {core}.",
        "Ersetze es nicht durch eine ähnliche unterstützte Operation; {core}.",
        "Die exakt benötigte Aktion lautet: {core}.",
    ),
    "mixed": (
        "same domain이지만 필요한 건 {core}.",
        "이 tool 관련이지만 requested action은 {core}.",
        "비슷한 supported operation으로 바꾸지 말고 {core}.",
        "exact action은 {core}.",
    ),
}

OOD = {
    "en": (
        "compose a four bar jazz piano voicing",
        "summarize the plot of a fictional detective novel",
        "suggest a stretching routine for a long flight",
        "translate this proverb into Latin",
        "design a logo concept for a bakery",
        "explain why ocean tides occur",
    ),
    "ko": (
        "재즈 피아노 4마디 보이싱을 만들어줘",
        "가상의 탐정 소설 줄거리를 요약해줘",
        "장거리 비행용 스트레칭 루틴을 추천해줘",
        "이 속담을 라틴어로 번역해줘",
        "빵집 로고 콘셉트를 디자인해줘",
        "바닷물의 조수가 생기는 이유를 설명해줘",
    ),
    "es": (
        "compón cuatro compases de voicings de piano jazz",
        "resume la trama de una novela detectivesca ficticia",
        "sugiere una rutina de estiramientos para un vuelo largo",
        "traduce este proverbio al latín",
        "diseña un concepto de logotipo para una panadería",
        "explica por qué ocurren las mareas oceánicas",
    ),
    "ja": (
        "ジャズピアノの4小節のボイシングを作って",
        "架空の推理小説のあらすじを要約して",
        "長時間フライト向けのストレッチを提案して",
        "このことわざをラテン語に翻訳して",
        "パン屋のロゴコンセプトを考えて",
        "海の潮汐が起こる理由を説明して",
    ),
    "de": (
        "komponiere vier Takte Jazz-Piano-Voicings",
        "fasse die Handlung eines fiktiven Kriminalromans zusammen",
        "empfiehl eine Dehnroutine für einen langen Flug",
        "übersetze dieses Sprichwort ins Lateinische",
        "entwirf ein Logo-Konzept für eine Bäckerei",
        "erkläre, warum Meeresgezeiten entstehen",
    ),
    "mixed": (
        "jazz piano 4-bar voicing을 만들어줘",
        "fictional detective novel plot을 요약해줘",
        "long flight용 stretching routine을 추천해줘",
        "이 proverb를 Latin으로 translate해줘",
        "bakery logo concept을 design해줘",
        "ocean tide가 생기는 이유를 explain해줘",
    ),
}

PRIOR_CORPORA = (
    "decision-routing-v1.json",
    "decision-routing-v2.json",
    "decision-routing-v3.json",
    "decision-routing-v4-operation-holdout.json",
    "decision-routing-v5-operation-calibration.json",
    "decision-routing-v6-operation-holdout.json",
    "decision-routing-v7-operation-post-change-holdout.json",
    "decision-routing-v8-operation-alias-holdout.json",
    "decision-routing-v9-operation-alias-holdout.json",
    "decision-routing-v10-operation-generalization-holdout.json",
    "decision-routing-v11-operation-generalization-holdout.json",
    "decision-routing-v12-operation-contrastive-holdout.json",
)


def _normalize(query: str) -> str:
    return re.sub(r"[^\w]+", "", query.casefold())


def _route_map() -> dict[str, dict[str, Any]]:
    return {str(route["route"]): route for route in CONFIG["routes"]}


def _build(seed: str) -> list[dict[str, object]]:
    rng = random.Random(seed)
    routes = _route_map()
    cases: list[dict[str, object]] = []

    for route_name in [name for pair in ROUTE_PAIRS for name in pair]:
        route = routes[route_name]
        route_id = route_name.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            values = list(route["values"])
            rng.shuffle(values)
            wrappers = list(SUPPORTED_WRAPPERS[language])
            rng.shuffle(wrappers)
            for index, wrapper in enumerate(wrappers):
                value = values[index]
                core = str(route["cores"][language]).replace("{v}", value)
                cases.append(
                    {
                        "id": f"v13-{route_id}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": route_name,
                        "category": "blind_operation_generalization",
                        "expect_abstain": False,
                        "split": "test",
                        "language": language,
                    }
                )

    for first, _second in ROUTE_PAIRS:
        domain = first.split(".", 1)[0]
        for language in LANGUAGES:
            wrappers = list(NEAR_WRAPPERS[language])
            rng.shuffle(wrappers)
            core = NEAR_DOMAIN[domain][language]
            for index, wrapper in enumerate(wrappers):
                cases.append(
                    {
                        "id": f"v13-near-{domain}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "expect_abstain": True,
                        "split": "test",
                        "language": language,
                    }
                )

    for language in LANGUAGES:
        cores = list(OOD[language])
        rng.shuffle(cores)
        for index, core in enumerate(cores[:4]):
            cases.append(
                {
                    "id": f"v13-ood-{language}-{index + 1:02d}",
                    "query": core,
                    "expected": None,
                    "category": "out_of_domain",
                    "expect_abstain": True,
                    "split": "test",
                    "language": language,
                }
            )

    rng.shuffle(cases)
    return cases


def _prior_normalized_queries() -> set[str]:
    seen: set[str] = set()
    for name in PRIOR_CORPORA:
        path = ROOT / "benchmarks" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"prior corpus is not a case list: {name}")
        seen.update(_normalize(str(case["query"])) for case in data)
    return seen


def _validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 600:
        raise ValueError(f"expected 600 cases, got {len(cases)}")
    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate v13 case IDs")

    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized v13 query")

    prior = _prior_normalized_queries()
    overlap = prior.intersection(normalized)
    if overlap:
        raise ValueError(f"v13 normalized exact-query overlap with prior corpora: {len(overlap)}")

    if sum(case["expected"] is not None for case in cases) != 384:
        raise ValueError("v13 supported count mismatch")
    if sum(case["category"] == "near_domain_unsupported_operation" for case in cases) != 192:
        raise ValueError("v13 near-domain unsupported count mismatch")
    if sum(case["category"] == "out_of_domain" for case in cases) != 24:
        raise ValueError("v13 OOD count mismatch")

    for language in LANGUAGES:
        if sum(case["language"] == language for case in cases) != 100:
            raise ValueError(f"v13 language balance mismatch: {language}")

    route_counts: dict[str, int] = {}
    for case in cases:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1
    if len(route_counts) != 16 or set(route_counts.values()) != {24}:
        raise ValueError("v13 supported-route balance mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--candidate-freeze-revision", required=True)
    args = parser.parse_args()

    cases = _build(args.seed)
    _validate(cases)

    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    manifest = {
        "version": "v13",
        "status": "generated_for_one_shot_scoring",
        "role": "blind_final_generalization_holdout",
        "seed": args.seed,
        "source_revision": args.source_revision,
        "candidate_freeze_revision": args.candidate_freeze_revision,
        "corpus_sha256": digest,
        "case_count": 600,
        "supported_operation_cases": 384,
        "near_domain_unsupported_operation_cases": 192,
        "out_of_domain_cases": 24,
        "languages": {language: 100 for language in LANGUAGES},
        "supported_route_count": 16,
        "cases_per_supported_route": 24,
        "normalized_exact_overlap_with_v1_v12": 0,
        "tuning_eligible": False,
    }
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"case_count": 600, "corpus_sha256": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
