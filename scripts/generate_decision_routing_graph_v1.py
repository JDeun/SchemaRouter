"""Generate the fresh graph-v1 development corpus.

This corpus is the only dataset eligible for graph-projection-v3 candidate selection.
It is intentionally separate from the consumed v5 calibration, v12 stress, v13 blind
final, and the retired v14 reservation.

The generator prints aggregate metadata only. Query text is written only to the
requested output artifact.
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
_spec = importlib.util.spec_from_file_location(
    "generate_decision_routing_v2",
    _V2_GENERATOR,
)
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

SUPPORTED_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "Resolve this against the registered tool contract and {core}.",
        "Use only a declared endpoint for this request: {core}.",
        "Treat the requested operation as binding; {core}.",
        "Follow the schema capability literally and {core}.",
        "Choose the endpoint by action rather than topic, then {core}.",
        "Do not broaden the action beyond what I asked: {core}.",
        "Use the narrowest registered operation that can satisfy this: {core}.",
        "Route through the explicit capability graph, then {core}.",
    ),
    "ko": (
        "등록된 도구 계약 기준으로 판단해서 {core}.",
        "이 요청은 선언된 엔드포인트만 사용해서 처리해: {core}.",
        "요청한 동작 자체를 기준으로 삼아서 {core}.",
        "스키마에 선언된 기능을 그대로 따라 {core}.",
        "주제가 아니라 실제 동작을 기준으로 골라서 {core}.",
        "요청 범위를 넓히지 말고 정확히 {core}.",
        "이 요청을 만족하는 가장 좁은 등록 동작으로 {core}.",
        "명시된 capability graph를 따라 {core}.",
    ),
    "es": (
        "Resuelve esto según el contrato registrado y {core}.",
        "Usa solo un endpoint declarado para esta solicitud: {core}.",
        "Toma la operación solicitada como vinculante y {core}.",
        "Sigue literalmente la capacidad del esquema y {core}.",
        "Elige el endpoint por la acción, no por el tema, y {core}.",
        "No amplíes la acción solicitada; {core}.",
        "Usa la operación registrada más específica que permita {core}.",
        "Enruta por el grafo explícito de capacidades y {core}.",
    ),
    "ja": (
        "登録済みのツール契約に照らして判断し、{core}。",
        "この依頼では宣言済みのエンドポイントだけを使って{core}。",
        "要求された操作そのものを基準にして{core}。",
        "スキーマに宣言された機能をそのまま辿って{core}。",
        "話題ではなく実際の操作で選び、{core}。",
        "要求範囲を広げず正確に{core}。",
        "この依頼を満たす最も限定的な登録操作で{core}。",
        "明示された capability graph に沿って{core}。",
    ),
    "de": (
        "Prüfe den registrierten Tool-Vertrag und {core}.",
        "Nutze für diese Anfrage nur einen deklarierten Endpoint: {core}.",
        "Behandle die angeforderte Operation als bindend und {core}.",
        "Folge der im Schema deklarierten Fähigkeit wörtlich und {core}.",
        "Wähle den Endpoint nach Aktion statt Thema und {core}.",
        "Erweitere die angeforderte Aktion nicht; {core}.",
        "Nutze die engste registrierte Operation, die dies erfüllt: {core}.",
        "Route über den expliziten Capability-Graph und {core}.",
    ),
    "mixed": (
        "registered tool contract 기준으로 resolve해서 {core}.",
        "이 request는 declared endpoint만 써서 {core}.",
        "requested operation 자체를 binding으로 보고 {core}.",
        "schema capability를 literal하게 따라 {core}.",
        "topic 말고 action 기준으로 endpoint를 골라 {core}.",
        "requested action을 broaden하지 말고 {core}.",
        "가장 narrow한 registered operation으로 {core}.",
        "explicit capability graph를 따라서 {core}.",
    ),
}

SUPPORTED_CATEGORIES = (
    "graph_dev_supported_contract",
    "graph_dev_supported_contract",
    "graph_dev_supported_action",
    "graph_dev_supported_action",
    "graph_dev_supported_guarded",
    "graph_dev_supported_guarded",
    "graph_dev_supported_narrow",
    "graph_dev_supported_narrow",
)

NEAR_DOMAIN: dict[str, dict[str, str]] = {
    "weather": {
        "en": "show the precipitation radar layer for Seoul",
        "ko": "서울 강수 레이더 지도를 보여줘",
        "es": "muestra la capa de radar de precipitación de Seúl",
        "ja": "ソウルの降水レーダー画像を表示して",
        "de": "zeige die Niederschlagsradar-Karte für Seoul",
        "mixed": "서울 precipitation radar layer를 보여줘",
    },
    "materials": {
        "en": "estimate the melting point of LiFePO4 from composition",
        "ko": "LiFePO4 조성으로 녹는점을 추정해줘",
        "es": "estima el punto de fusión de LiFePO4 a partir de su composición",
        "ja": "LiFePO4の組成から融点を推定して",
        "de": "schätze den Schmelzpunkt von LiFePO4 aus der Zusammensetzung",
        "mixed": "LiFePO4 composition으로 melting point를 estimate해줘",
    },
    "papers": {
        "en": "export BibTeX for DOI 10.5555/graph-dev",
        "ko": "DOI 10.5555/graph-dev 논문의 BibTeX를 내보내줘",
        "es": "exporta BibTeX para el DOI 10.5555/graph-dev",
        "ja": "DOI 10.5555/graph-dev のBibTeXを書き出して",
        "de": "exportiere BibTeX für DOI 10.5555/graph-dev",
        "mixed": "DOI 10.5555/graph-dev의 BibTeX를 export해줘",
    },
    "finance": {
        "en": "calculate option implied volatility for AAPL",
        "ko": "AAPL 옵션의 내재변동성을 계산해줘",
        "es": "calcula la volatilidad implícita de opciones de AAPL",
        "ja": "AAPLオプションのインプライド・ボラティリティを計算して",
        "de": "berechne die implizite Volatilität einer AAPL-Option",
        "mixed": "AAPL option implied volatility를 calculate해줘",
    },
    "calendar": {
        "en": "accept the meeting invitation from Alex",
        "ko": "Alex가 보낸 회의 초대를 수락해줘",
        "es": "acepta la invitación a la reunión de Alex",
        "ja": "Alexからの会議招待を承諾して",
        "de": "nimm die Besprechungseinladung von Alex an",
        "mixed": "Alex의 meeting invitation을 accept해줘",
    },
    "support": {
        "en": "merge support ticket 4821 with duplicate ticket 4822",
        "ko": "고객지원 티켓 4821과 중복 티켓 4822를 병합해줘",
        "es": "fusiona el ticket de soporte 4821 con el duplicado 4822",
        "ja": "サポートチケット4821と重複チケット4822を統合して",
        "de": "führe Support-Ticket 4821 mit Duplikat 4822 zusammen",
        "mixed": "support ticket 4821과 duplicate 4822를 merge해줘",
    },
    "inventory": {
        "en": "reserve five units of SKU-778 for order 9001",
        "ko": "주문 9001용으로 SKU-778 다섯 개를 예약해줘",
        "es": "reserva cinco unidades de SKU-778 para el pedido 9001",
        "ja": "注文9001用にSKU-778を5個取り置きして",
        "de": "reserviere fünf Einheiten von SKU-778 für Bestellung 9001",
        "mixed": "order 9001용 SKU-778 5개를 reserve해줘",
    },
    "users": {
        "en": "disable multi-factor authentication for user 314",
        "ko": "사용자 314의 다중 인증을 비활성화해줘",
        "es": "desactiva la autenticación multifactor del usuario 314",
        "ja": "ユーザー314の多要素認証を無効にして",
        "de": "deaktiviere die Mehrfaktor-Authentifizierung für Benutzer 314",
        "mixed": "user 314의 MFA를 disable해줘",
    },
}

NEAR_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "Stay in this domain, but perform exactly this unsupported action: {core}.",
        "The topic matches the tool; the operation I need is instead: {core}.",
        "Do not substitute a sibling endpoint for this request: {core}.",
        "Reject nearby capabilities unless the schema explicitly supports this: {core}.",
        "This is intentionally adjacent to a supported action, but I need to {core}.",
        "Use no approximate operation; the exact request is to {core}.",
        "A domain match is not enough here; I specifically need to {core}.",
        "Treat this as unsupported if the registered graph cannot express it: {core}.",
    ),
    "ko": (
        "같은 도메인이지만 정확히 이 미지원 동작을 해줘: {core}.",
        "주제는 맞아도 내가 필요한 동작은 따로 있어: {core}.",
        "비슷한 형제 엔드포인트로 대체하지 말고 {core}.",
        "스키마가 명시적으로 지원하지 않으면 거절해야 해: {core}.",
        "지원 동작과 가깝지만 실제 필요한 건 {core}.",
        "근사한 동작은 쓰지 말고 정확히 {core}.",
        "도메인이 맞는 것만으로는 부족하고 구체적으로 {core}.",
        "등록 그래프로 표현할 수 없으면 미지원으로 처리해: {core}.",
    ),
    "es": (
        "Mantente en este dominio, pero realiza exactamente esta acción no soportada: {core}.",
        "El tema coincide con la herramienta, pero la operación que necesito es: {core}.",
        "No sustituyas esta solicitud por un endpoint hermano: {core}.",
        "Rechaza capacidades cercanas salvo que el esquema soporte explícitamente esto: {core}.",
        "Está cerca de una acción soportada, pero necesito {core}.",
        "No uses una operación aproximada; la solicitud exacta es {core}.",
        "Coincidir en dominio no basta; necesito específicamente {core}.",
        "Trátalo como no soportado si el grafo registrado no puede expresarlo: {core}.",
    ),
    "ja": (
        "同じドメインですが、この未対応操作を正確に実行して: {core}。",
        "話題はツールに合いますが必要な操作は別です: {core}。",
        "似た兄弟エンドポイントに置き換えず{core}。",
        "スキーマが明示的に対応していないなら拒否して: {core}。",
        "対応操作に近いですが実際に必要なのは{core}。",
        "近似操作を使わず正確に{core}。",
        "ドメイン一致だけでは不十分で、具体的には{core}。",
        "登録グラフで表現できなければ未対応として扱って: {core}。",
    ),
    "de": (
        "Bleibe in dieser Domäne, führe aber genau diese nicht unterstützte Aktion aus: {core}.",
        "Das Thema passt zum Tool, die benötigte Operation ist jedoch: {core}.",
        "Ersetze diese Anfrage nicht durch einen Schwester-Endpoint: {core}.",
        "Lehne ähnliche Fähigkeiten ab, wenn das Schema dies nicht explizit unterstützt: {core}.",
        "Die Aktion liegt nahe an einer unterstützten, aber ich brauche {core}.",
        "Nutze keine angenäherte Operation; die genaue Anfrage lautet {core}.",
        "Eine Domänenübereinstimmung reicht nicht; ich brauche konkret {core}.",
        "Behandle es als nicht unterstützt, wenn der registrierte Graph es nicht ausdrückt: {core}.",
    ),
    "mixed": (
        "same domain이지만 exact unsupported action은 이거야: {core}.",
        "topic은 맞아도 필요한 operation은 따로야: {core}.",
        "sibling endpoint로 substitute하지 말고 {core}.",
        "schema가 explicit support하지 않으면 reject해: {core}.",
        "supported action과 adjacent하지만 필요한 건 {core}.",
        "approximate operation 없이 exact하게 {core}.",
        "domain match만으로 부족하고 specifically {core}.",
        "registered graph로 express 못하면 unsupported로 처리해: {core}.",
    ),
}

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "write a twelve-line sonnet about winter",
        "explain the offside rule in football",
        "create a vegetarian ramen recipe",
        "suggest names for a science-fiction spaceship",
        "teach me a basic blues guitar turnaround",
        "compare impressionism and cubism",
        "draft a bedtime story about a fox",
        "explain how eclipses occur",
    ),
    "ko": (
        "겨울에 대한 12행 소네트를 써줘",
        "축구 오프사이드 규칙을 설명해줘",
        "채식 라멘 레시피를 만들어줘",
        "SF 우주선 이름을 추천해줘",
        "기초 블루스 기타 턴어라운드를 알려줘",
        "인상주의와 입체주의를 비교해줘",
        "여우가 나오는 잠자리 동화를 써줘",
        "일식과 월식이 생기는 원리를 설명해줘",
    ),
    "es": (
        "escribe un soneto de doce versos sobre el invierno",
        "explica la regla del fuera de juego en fútbol",
        "crea una receta de ramen vegetariano",
        "sugiere nombres para una nave de ciencia ficción",
        "enséñame un turnaround básico de guitarra blues",
        "compara impresionismo y cubismo",
        "escribe un cuento para dormir sobre un zorro",
        "explica cómo ocurren los eclipses",
    ),
    "ja": (
        "冬について12行のソネットを書いて",
        "サッカーのオフサイド規則を説明して",
        "ベジタリアンラーメンのレシピを作って",
        "SF宇宙船の名前を提案して",
        "基本的なブルースギターのターンアラウンドを教えて",
        "印象派とキュビスムを比較して",
        "キツネの寝る前の物語を書いて",
        "日食と月食が起こる仕組みを説明して",
    ),
    "de": (
        "schreibe ein zwölfzeiliges Sonett über den Winter",
        "erkläre die Abseitsregel im Fußball",
        "erstelle ein vegetarisches Ramen-Rezept",
        "schlage Namen für ein Science-Fiction-Raumschiff vor",
        "zeige mir einen einfachen Blues-Gitarren-Turnaround",
        "vergleiche Impressionismus und Kubismus",
        "schreibe eine Gute-Nacht-Geschichte über einen Fuchs",
        "erkläre wie Finsternisse entstehen",
    ),
    "mixed": (
        "winter 주제로 12-line sonnet을 써줘",
        "football offside rule을 설명해줘",
        "vegetarian ramen recipe를 만들어줘",
        "sci-fi spaceship name을 추천해줘",
        "basic blues guitar turnaround를 알려줘",
        "impressionism과 cubism을 비교해줘",
        "fox가 나오는 bedtime story를 써줘",
        "eclipse가 어떻게 생기는지 설명해줘",
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
    "decision-routing-v13-operation-contrastive-holdout.json",
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
            for index, (value, wrapper) in enumerate(
                zip(values[:8], wrappers, strict=True)
            ):
                core = str(route["cores"][language]).replace("{v}", value)
                cases.append(
                    {
                        "id": f"graph-v1-{route_id}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": route_name,
                        "category": SUPPORTED_CATEGORIES[index],
                        "expect_abstain": False,
                        "split": "dev",
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
                        "id": f"graph-v1-near-{domain}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "expect_abstain": True,
                        "split": "dev",
                        "language": language,
                    }
                )

    for language in LANGUAGES:
        cores = list(OOD[language])
        rng.shuffle(cores)
        for index, core in enumerate(cores):
            cases.append(
                {
                    "id": f"graph-v1-ood-{language}-{index + 1:02d}",
                    "query": core,
                    "expected": None,
                    "category": "out_of_domain",
                    "expect_abstain": True,
                    "split": "dev",
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
    if len(cases) != 1200:
        raise ValueError(f"expected 1200 cases, got {len(cases)}")

    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate graph-v1 case IDs")

    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized graph-v1 query")

    overlap = _prior_normalized_queries().intersection(normalized)
    if overlap:
        raise ValueError(
            "graph-v1 normalized exact-query overlap with prior corpora: "
            f"{len(overlap)}"
        )

    if sum(case["expected"] is not None for case in cases) != 768:
        raise ValueError("graph-v1 supported count mismatch")
    if sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in cases
    ) != 384:
        raise ValueError("graph-v1 near-domain unsupported count mismatch")
    if sum(case["category"] == "out_of_domain" for case in cases) != 48:
        raise ValueError("graph-v1 OOD count mismatch")

    for language in LANGUAGES:
        if sum(case["language"] == language for case in cases) != 200:
            raise ValueError(f"graph-v1 language balance mismatch: {language}")

    route_counts: dict[str, int] = {}
    for case in cases:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1
    if len(route_counts) != 16 or set(route_counts.values()) != {48}:
        raise ValueError("graph-v1 supported-route balance mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()

    cases = _build(args.seed)
    _validate(cases)

    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    manifest = {
        "version": "graph-v1-development",
        "status": "fresh_development_generated",
        "role": "candidate_selection_only",
        "tuning_eligible": True,
        "seed": args.seed,
        "source_revision": args.source_revision,
        "corpus_sha256": digest,
        "case_count": 1200,
        "supported_operation_cases": 768,
        "near_domain_unsupported_operation_cases": 384,
        "out_of_domain_cases": 48,
        "languages": {language: 200 for language in LANGUAGES},
        "supported_route_count": 16,
        "cases_per_supported_route": 48,
        "normalized_exact_overlap_with_prior_corpora": 0,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": 1200,
                "corpus_sha256": digest,
                "tuning_eligible": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
