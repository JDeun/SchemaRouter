"""Generate fresh confirmation-only calibration data for the frozen graph candidate.

The generator is committed only after the development candidate is frozen.  The
result must never be used to change architecture, thresholds, route text, or models.
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
_GRAPH_DEV_GENERATOR = Path(__file__).with_name(
    "generate_decision_routing_graph_v1.py"
)


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_v2 = _load_module(_V2_GENERATOR, "generate_decision_routing_v2")
_graph_dev = _load_module(
    _GRAPH_DEV_GENERATOR,
    "generate_decision_routing_graph_v1",
)
CONFIG: dict[str, Any] = _v2.CONFIG
LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
DEV_SEED = "graph-v1-development-2026-09-26"

SUPPORTED_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "Before I continue, please {core}.",
        "For the task I'm working on, {core}.",
        "What I need next is to {core}.",
        "Handle this request for me: {core}.",
    ),
    "ko": (
        "다음 작업 전에 {core}.",
        "지금 하던 일에서 {core}.",
        "다음으로 필요한 건 {core}.",
        "이 요청을 처리해줘: {core}.",
    ),
    "es": (
        "Antes de continuar, por favor {core}.",
        "Para la tarea en la que estoy trabajando, {core}.",
        "Lo siguiente que necesito es {core}.",
        "Haz esta solicitud por mí: {core}.",
    ),
    "ja": (
        "次に進む前に{core}。",
        "今の作業のために{core}。",
        "次に必要なのは{core}ことです。",
        "この依頼を処理して: {core}。",
    ),
    "de": (
        "Bevor ich weitermache, bitte {core}.",
        "Für meine aktuelle Aufgabe: {core}.",
        "Als Nächstes brauche ich Folgendes: {core}.",
        "Bearbeite diese Anfrage für mich: {core}.",
    ),
    "mixed": (
        "다음 step 전에 {core}.",
        "지금 task에서 {core}.",
        "next로 필요한 건 {core}.",
        "이 request 처리해줘: {core}.",
    ),
}

NEAR_DOMAIN_FAMILIES: dict[str, dict[str, tuple[str, ...]]] = {
    "weather": {
        "en": (
            "show the precipitation radar image for Seoul",
            "give me the air quality index in Seoul",
            "subscribe me to severe weather alerts for Seoul",
            "show historical monthly rainfall normals for Seoul",
        ),
        "ko": (
            "서울 강수 레이더 이미지를 보여줘",
            "서울의 대기질 지수를 알려줘",
            "서울 기상특보 알림을 구독해줘",
            "서울의 과거 월별 평년 강수량을 보여줘",
        ),
        "es": (
            "muestra la imagen de radar de precipitación de Seúl",
            "dime el índice de calidad del aire de Seúl",
            "suscríbeme a alertas de tiempo severo para Seúl",
            "muestra los promedios históricos mensuales de lluvia de Seúl",
        ),
        "ja": (
            "ソウルの降水レーダー画像を表示して",
            "ソウルの大気質指数を教えて",
            "ソウルの悪天候警報を購読して",
            "ソウルの過去の月別平年降水量を表示して",
        ),
        "de": (
            "zeige das Niederschlagsradarbild für Seoul",
            "nenne mir den Luftqualitätsindex für Seoul",
            "abonniere Unwetterwarnungen für Seoul",
            "zeige historische monatliche Niederschlagsnormalwerte für Seoul",
        ),
        "mixed": (
            "서울 precipitation radar image를 보여줘",
            "서울 air quality index를 알려줘",
            "서울 severe weather alert를 subscribe해줘",
            "서울 historical monthly rainfall normal을 보여줘",
        ),
    },
    "materials": {
        "en": (
            "predict the melting point of LiFePO4 from its composition",
            "simulate the phonon dispersion of silicon",
            "generate a phase diagram for the Li Fe P O system",
            "optimize a battery composition for maximum ionic conductivity",
        ),
        "ko": (
            "LiFePO4 조성으로 녹는점을 예측해줘",
            "실리콘의 포논 분산을 시뮬레이션해줘",
            "Li Fe P O 계의 상평형도를 생성해줘",
            "이온전도도가 최대가 되도록 배터리 조성을 최적화해줘",
        ),
        "es": (
            "predice el punto de fusión de LiFePO4 a partir de su composición",
            "simula la dispersión de fonones del silicio",
            "genera un diagrama de fases para el sistema Li Fe P O",
            "optimiza una composición de batería para máxima conductividad iónica",
        ),
        "ja": (
            "LiFePO4の組成から融点を予測して",
            "シリコンのフォノン分散をシミュレーションして",
            "Li Fe P O系の相図を生成して",
            "イオン伝導度が最大になる電池組成を最適化して",
        ),
        "de": (
            "sage den Schmelzpunkt von LiFePO4 aus seiner Zusammensetzung voraus",
            "simuliere die Phononendispersion von Silizium",
            "erzeuge ein Phasendiagramm für das System Li Fe P O",
            "optimiere eine Batteriezusammensetzung für maximale Ionenleitfähigkeit",
        ),
        "mixed": (
            "LiFePO4 composition으로 melting point를 predict해줘",
            "silicon phonon dispersion을 simulate해줘",
            "Li Fe P O system phase diagram을 generate해줘",
            "ionic conductivity 최대 battery composition을 optimize해줘",
        ),
    },
    "papers": {
        "en": (
            "export BibTeX for DOI 10.5555/calibration-a",
            "download the full PDF for DOI 10.5555/calibration-b",
            "summarize the methods section of DOI 10.5555/calibration-c",
            "submit a manuscript to a journal for me",
        ),
        "ko": (
            "DOI 10.5555/calibration-a의 BibTeX를 내보내줘",
            "DOI 10.5555/calibration-b의 원문 PDF를 내려받아줘",
            "DOI 10.5555/calibration-c 논문의 방법론 부분을 요약해줘",
            "내 원고를 학술지에 투고해줘",
        ),
        "es": (
            "exporta BibTeX para el DOI 10.5555/calibration-a",
            "descarga el PDF completo del DOI 10.5555/calibration-b",
            "resume la sección de métodos del DOI 10.5555/calibration-c",
            "envía un manuscrito a una revista por mí",
        ),
        "ja": (
            "DOI 10.5555/calibration-a のBibTeXを書き出して",
            "DOI 10.5555/calibration-b の全文PDFをダウンロードして",
            "DOI 10.5555/calibration-c の手法セクションを要約して",
            "私の原稿を学術誌に投稿して",
        ),
        "de": (
            "exportiere BibTeX für DOI 10.5555/calibration-a",
            "lade das vollständige PDF für DOI 10.5555/calibration-b herunter",
            "fasse den Methodenteil von DOI 10.5555/calibration-c zusammen",
            "reiche ein Manuskript für mich bei einer Zeitschrift ein",
        ),
        "mixed": (
            "DOI 10.5555/calibration-a BibTeX를 export해줘",
            "DOI 10.5555/calibration-b full PDF를 download해줘",
            "DOI 10.5555/calibration-c methods section을 summarize해줘",
            "내 manuscript를 journal에 submit해줘",
        ),
    },
    "finance": {
        "en": (
            "calculate option implied volatility for AAPL",
            "buy ten shares of NVDA at market price",
            "forecast next quarter's dividend for KO",
            "convert 1000 US dollars to Korean won",
        ),
        "ko": (
            "AAPL 옵션의 내재변동성을 계산해줘",
            "NVDA 주식 10주를 시장가로 매수해줘",
            "KO의 다음 분기 배당금을 예측해줘",
            "미화 1000달러를 원화로 환산해줘",
        ),
        "es": (
            "calcula la volatilidad implícita de opciones de AAPL",
            "compra diez acciones de NVDA a precio de mercado",
            "pronostica el dividendo del próximo trimestre de KO",
            "convierte 1000 dólares estadounidenses a won coreano",
        ),
        "ja": (
            "AAPLオプションのインプライド・ボラティリティを計算して",
            "NVDA株を成行で10株買って",
            "KOの次四半期の配当を予測して",
            "1000米ドルを韓国ウォンに換算して",
        ),
        "de": (
            "berechne die implizite Volatilität einer AAPL-Option",
            "kaufe zehn NVDA-Aktien zum Marktpreis",
            "prognostiziere die Dividende von KO für das nächste Quartal",
            "rechne 1000 US-Dollar in koreanische Won um",
        ),
        "mixed": (
            "AAPL option implied volatility를 calculate해줘",
            "NVDA 10 shares를 market price로 buy해줘",
            "KO next-quarter dividend를 forecast해줘",
            "1000 USD를 KRW로 convert해줘",
        ),
    },
    "calendar": {
        "en": (
            "accept Alex's meeting invitation",
            "delete tomorrow's dentist appointment",
            "move Friday's project review to 4 PM",
            "email an invitation to everyone on the team",
        ),
        "ko": (
            "Alex가 보낸 회의 초대를 수락해줘",
            "내일 치과 일정을 삭제해줘",
            "금요일 프로젝트 리뷰를 오후 4시로 옮겨줘",
            "팀원 모두에게 회의 초대 메일을 보내줘",
        ),
        "es": (
            "acepta la invitación de reunión de Alex",
            "elimina la cita del dentista de mañana",
            "mueve la revisión del proyecto del viernes a las 4",
            "envía por correo una invitación a todo el equipo",
        ),
        "ja": (
            "Alexからの会議招待を承諾して",
            "明日の歯医者の予定を削除して",
            "金曜のプロジェクトレビューを16時に移動して",
            "チーム全員に会議招待メールを送って",
        ),
        "de": (
            "nimm Alex' Besprechungseinladung an",
            "lösche den Zahnarzttermin von morgen",
            "verschiebe die Projektbesprechung am Freitag auf 16 Uhr",
            "sende dem ganzen Team eine Einladung per E-Mail",
        ),
        "mixed": (
            "Alex meeting invitation을 accept해줘",
            "내일 dentist appointment를 delete해줘",
            "Friday project review를 4 PM으로 move해줘",
            "team 전체에 meeting invitation email을 send해줘",
        ),
    },
    "support": {
        "en": (
            "merge support ticket 4821 with duplicate ticket 4822",
            "close support ticket 5930 as resolved",
            "assign support ticket 6044 to agent Mina",
            "issue a refund to the customer in ticket 7001",
        ),
        "ko": (
            "고객지원 티켓 4821과 중복 티켓 4822를 병합해줘",
            "고객지원 티켓 5930을 해결됨으로 종료해줘",
            "고객지원 티켓 6044를 상담원 Mina에게 배정해줘",
            "티켓 7001의 고객에게 환불을 실행해줘",
        ),
        "es": (
            "fusiona el ticket de soporte 4821 con el duplicado 4822",
            "cierra el ticket de soporte 5930 como resuelto",
            "asigna el ticket de soporte 6044 a la agente Mina",
            "emite un reembolso al cliente del ticket 7001",
        ),
        "ja": (
            "サポートチケット4821と重複チケット4822を統合して",
            "サポートチケット5930を解決済みとして閉じて",
            "サポートチケット6044を担当者Minaに割り当てて",
            "チケット7001の顧客に返金して",
        ),
        "de": (
            "führe Support-Ticket 4821 mit Duplikat 4822 zusammen",
            "schließe Support-Ticket 5930 als gelöst",
            "weise Support-Ticket 6044 der Agentin Mina zu",
            "erstatte dem Kunden aus Ticket 7001 den Betrag",
        ),
        "mixed": (
            "support ticket 4821과 duplicate 4822를 merge해줘",
            "support ticket 5930을 resolved로 close해줘",
            "support ticket 6044를 agent Mina에게 assign해줘",
            "ticket 7001 customer에게 refund해줘",
        ),
    },
    "inventory": {
        "en": (
            "reserve five units of SKU-778 for order 9001",
            "transfer SKU-202 from warehouse A to warehouse B",
            "delete SKU-303 from the catalog",
            "create a purchase order for fifty units of SKU-404",
        ),
        "ko": (
            "주문 9001용으로 SKU-778 다섯 개를 예약해줘",
            "SKU-202를 A창고에서 B창고로 이동해줘",
            "SKU-303을 상품 카탈로그에서 삭제해줘",
            "SKU-404 50개에 대한 구매 주문을 만들어줘",
        ),
        "es": (
            "reserva cinco unidades de SKU-778 para el pedido 9001",
            "transfiere SKU-202 del almacén A al almacén B",
            "elimina SKU-303 del catálogo",
            "crea una orden de compra de cincuenta unidades de SKU-404",
        ),
        "ja": (
            "注文9001用にSKU-778を5個取り置きして",
            "SKU-202を倉庫Aから倉庫Bへ移して",
            "SKU-303をカタログから削除して",
            "SKU-404を50個購入する発注書を作成して",
        ),
        "de": (
            "reserviere fünf Einheiten von SKU-778 für Bestellung 9001",
            "verschiebe SKU-202 von Lager A nach Lager B",
            "lösche SKU-303 aus dem Katalog",
            "erstelle eine Bestellung über fünfzig Einheiten von SKU-404",
        ),
        "mixed": (
            "order 9001용 SKU-778 5개를 reserve해줘",
            "SKU-202를 warehouse A에서 B로 transfer해줘",
            "SKU-303을 catalog에서 delete해줘",
            "SKU-404 50개 purchase order를 create해줘",
        ),
    },
    "users": {
        "en": (
            "disable multi-factor authentication for user 314",
            "reset the password for user 271",
            "delete account 808",
            "create a new administrator account for Mina",
        ),
        "ko": (
            "사용자 314의 다중 인증을 비활성화해줘",
            "사용자 271의 비밀번호를 재설정해줘",
            "계정 808을 삭제해줘",
            "Mina의 새 관리자 계정을 만들어줘",
        ),
        "es": (
            "desactiva la autenticación multifactor del usuario 314",
            "restablece la contraseña del usuario 271",
            "elimina la cuenta 808",
            "crea una nueva cuenta de administrador para Mina",
        ),
        "ja": (
            "ユーザー314の多要素認証を無効にして",
            "ユーザー271のパスワードをリセットして",
            "アカウント808を削除して",
            "Minaの新しい管理者アカウントを作成して",
        ),
        "de": (
            "deaktiviere die Mehrfaktor-Authentifizierung für Benutzer 314",
            "setze das Passwort für Benutzer 271 zurück",
            "lösche Konto 808",
            "erstelle ein neues Administratorkonto für Mina",
        ),
        "mixed": (
            "user 314 MFA를 disable해줘",
            "user 271 password를 reset해줘",
            "account 808을 delete해줘",
            "Mina admin account를 create해줘",
        ),
    },
}

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "give me a vegetarian curry recipe",
        "write four lines of a birthday poem",
        "show me a beginner jazz guitar chord progression",
        "prove that the square root of two is irrational",
    ),
    "ko": (
        "채식 카레 레시피를 알려줘",
        "생일 축하 시를 네 줄로 써줘",
        "초보자용 재즈 기타 코드 진행을 알려줘",
        "루트 2가 무리수라는 걸 증명해줘",
    ),
    "es": (
        "dame una receta de curry vegetariano",
        "escribe cuatro versos de un poema de cumpleaños",
        "muéstrame una progresión de acordes de jazz para principiantes",
        "demuestra que la raíz cuadrada de dos es irracional",
    ),
    "ja": (
        "ベジタリアンカレーのレシピを教えて",
        "誕生日の詩を4行で書いて",
        "初心者向けのジャズギターコード進行を教えて",
        "2の平方根が無理数であることを証明して",
    ),
    "de": (
        "gib mir ein Rezept für vegetarisches Curry",
        "schreibe vier Zeilen eines Geburtstagsgedichts",
        "zeige mir eine Jazz-Gitarrenakkordfolge für Anfänger",
        "beweise dass die Quadratwurzel aus zwei irrational ist",
    ),
    "mixed": (
        "vegetarian curry recipe를 알려줘",
        "birthday poem을 네 줄로 써줘",
        "beginner jazz guitar chord progression을 알려줘",
        "sqrt 2가 irrational이라는 걸 prove해줘",
    ),
}

LABEL_REVEALING_CUES = (
    "unsupported",
    "not supported",
    "reject",
    "schema",
    "endpoint",
    "capability graph",
    "미지원",
    "거절",
    "스키마",
    "엔드포인트",
    "no soportad",
    "rechaza",
    "esquema",
    "未対応",
    "拒否",
    "スキーマ",
    "エンドポイント",
    "nicht unterstützt",
    "lehne",
)


def _normalize(query: str) -> str:
    return re.sub(r"[^\w]+", "", query.casefold())


def _route_map() -> dict[str, dict[str, Any]]:
    return {str(route["route"]): route for route in CONFIG["routes"]}


def _build(seed: str) -> list[dict[str, object]]:
    rng = random.Random(seed)
    routes = _route_map()
    cases: list[dict[str, object]] = []

    for route_name in [name for pair in _graph_dev.ROUTE_PAIRS for name in pair]:
        route = routes[route_name]
        route_id = route_name.replace(".", "-").replace("_", "-")
        values = list(route["values"])
        rng.shuffle(values)
        for language in LANGUAGES:
            wrappers = list(SUPPORTED_WRAPPERS[language])
            rng.shuffle(wrappers)
            language_values = list(values)
            rng.shuffle(language_values)
            for index, (value, wrapper) in enumerate(
                zip(language_values[:4], wrappers, strict=True)
            ):
                core = str(route["cores"][language]).replace("{v}", value)
                cases.append(
                    {
                        "id": f"graph-cal-{route_id}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": route_name,
                        "category": "graph_cal_supported_natural",
                        "expect_abstain": False,
                        "split": "calibration",
                        "language": language,
                    }
                )

    for first, _second in _graph_dev.ROUTE_PAIRS:
        domain = first.split(".", 1)[0]
        for language in LANGUAGES:
            for index, query in enumerate(NEAR_DOMAIN_FAMILIES[domain][language]):
                cases.append(
                    {
                        "id": f"graph-cal-near-{domain}-{language}-{index + 1:02d}",
                        "query": query,
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "expect_abstain": True,
                        "split": "calibration",
                        "language": language,
                    }
                )

    for language in LANGUAGES:
        for index, query in enumerate(OOD[language]):
            cases.append(
                {
                    "id": f"graph-cal-ood-{language}-{index + 1:02d}",
                    "query": query,
                    "expected": None,
                    "category": "out_of_domain",
                    "expect_abstain": True,
                    "split": "calibration",
                    "language": language,
                }
            )

    rng.shuffle(cases)
    return cases


def _prior_and_dev_normalized_queries() -> set[str]:
    seen = set(_graph_dev._prior_normalized_queries())
    seen.update(
        _normalize(str(case["query"]))
        for case in _graph_dev._build(DEV_SEED)
    )
    return seen


def _validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 600:
        raise ValueError(f"expected 600 calibration cases, got {len(cases)}")

    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate graph calibration case IDs")

    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized graph calibration query")

    overlap = _prior_and_dev_normalized_queries().intersection(normalized)
    if overlap:
        raise ValueError(
            "graph calibration normalized exact-query overlap with prior/dev corpora: "
            f"{len(overlap)}"
        )

    if sum(case["expected"] is not None for case in cases) != 384:
        raise ValueError("graph calibration supported count mismatch")
    if sum(
        case["category"] == "near_domain_unsupported_operation"
        for case in cases
    ) != 192:
        raise ValueError("graph calibration near-domain count mismatch")
    if sum(case["category"] == "out_of_domain" for case in cases) != 24:
        raise ValueError("graph calibration OOD count mismatch")

    for language in LANGUAGES:
        if sum(case["language"] == language for case in cases) != 100:
            raise ValueError(f"graph calibration language balance mismatch: {language}")

    route_counts: dict[str, int] = {}
    for case in cases:
        expected = case["expected"]
        if expected is not None:
            route_counts[str(expected)] = route_counts.get(str(expected), 0) + 1
    if len(route_counts) != 16 or set(route_counts.values()) != {24}:
        raise ValueError("graph calibration supported-route balance mismatch")

    near_queries = [
        str(case["query"]).casefold()
        for case in cases
        if case["category"] == "near_domain_unsupported_operation"
    ]
    leaks = [
        query
        for query in near_queries
        if any(cue in query for cue in LABEL_REVEALING_CUES)
    ]
    if leaks:
        raise ValueError(
            f"graph calibration contains label-revealing routing cues: {len(leaks)}"
        )


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
        "version": "graph-v1-calibration-natural",
        "status": "fresh_confirmation_only_calibration_generated",
        "role": "frozen_candidate_confirmation_only",
        "tuning_eligible": False,
        "seed": args.seed,
        "source_revision": args.source_revision,
        "corpus_sha256": digest,
        "case_count": 600,
        "supported_operation_cases": 384,
        "near_domain_unsupported_operation_cases": 192,
        "near_domain_unsupported_family_count": 32,
        "out_of_domain_cases": 24,
        "languages": {language: 100 for language in LANGUAGES},
        "supported_route_count": 16,
        "cases_per_supported_route": 24,
        "normalized_exact_overlap_with_prior_and_development_corpora": 0,
        "label_revealing_routing_cues_in_near_domain": 0,
        "candidate_was_frozen_before_generator_commit": True,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": 600,
                "corpus_sha256": digest,
                "tuning_eligible": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
