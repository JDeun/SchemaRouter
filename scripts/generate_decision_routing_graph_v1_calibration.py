"""Generate the fresh graph-v1 calibration corpus after candidate freeze.

This corpus is confirmation-only. It must never be used to choose graph architecture,
thresholds, aliases, or escalation policy. The generator enforces exact normalized
isolation from all checked-in historical corpora and from the deterministic graph-v1
development corpus.
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
_DEV_GENERATOR = Path(__file__).with_name("generate_decision_routing_graph_v1.py")
_spec = importlib.util.spec_from_file_location(
    "generate_decision_routing_graph_v1",
    _DEV_GENERATOR,
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load graph-v1 development generator")
_dev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dev)

CONFIG: dict[str, Any] = _dev.CONFIG
LANGUAGES = _dev.LANGUAGES
ROUTE_PAIRS = _dev.ROUTE_PAIRS
DEVELOPMENT_SEED = "graph-v1-development-2026-09-26"

SUPPORTED_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "Confirm the exact registered action for this request and {core}.",
        "Using only the declared schema capability, {core}.",
        "Resolve the operation conservatively, then {core}.",
        "Keep the route inside the explicit contract and {core}.",
    ),
    "ko": (
        "이 요청의 정확한 등록 동작을 확인한 뒤 {core}.",
        "선언된 스키마 기능만 사용해서 {core}.",
        "동작을 보수적으로 판정한 다음 {core}.",
        "명시된 계약 범위 안에서 라우팅해서 {core}.",
    ),
    "es": (
        "Confirma la acción registrada exacta para esta solicitud y {core}.",
        "Usando solo la capacidad declarada del esquema, {core}.",
        "Resuelve la operación de forma conservadora y luego {core}.",
        "Mantén la ruta dentro del contrato explícito y {core}.",
    ),
    "ja": (
        "この依頼に対応する正確な登録操作を確認してから{core}。",
        "宣言済みのスキーマ機能だけを使って{core}。",
        "操作を保守的に判定してから{core}。",
        "明示された契約の範囲内でルーティングして{core}。",
    ),
    "de": (
        "Bestätige die genaue registrierte Aktion für diese Anfrage und {core}.",
        "Nutze nur die deklarierte Schema-Fähigkeit und {core}.",
        "Bestimme die Operation konservativ und {core}.",
        "Halte die Route innerhalb des expliziten Vertrags und {core}.",
    ),
    "mixed": (
        "이 request의 exact registered action을 확인하고 {core}.",
        "declared schema capability만 써서 {core}.",
        "operation을 conservative하게 resolve한 뒤 {core}.",
        "explicit contract 안에서 route해서 {core}.",
    ),
}

NEAR_DOMAIN: dict[str, dict[str, str]] = {
    "weather": {
        "en": "retrieve historical rainfall totals for Seoul last month",
        "ko": "서울의 지난달 누적 강수량 기록을 가져와",
        "es": "recupera los totales históricos de lluvia de Seúl del mes pasado",
        "ja": "ソウルの先月の過去降水量合計を取得して",
        "de": "hole die historischen Niederschlagssummen für Seoul im letzten Monat",
        "mixed": "서울 last month historical rainfall total을 가져와",
    },
    "materials": {
        "en": "calculate a phase diagram for the Li-Fe-P-O system",
        "ko": "Li-Fe-P-O 계의 상평형도를 계산해줘",
        "es": "calcula un diagrama de fases para el sistema Li-Fe-P-O",
        "ja": "Li-Fe-P-O系の相図を計算して",
        "de": "berechne ein Phasendiagramm für das Li-Fe-P-O-System",
        "mixed": "Li-Fe-P-O system phase diagram을 calculate해줘",
    },
    "papers": {
        "en": "export a RIS citation file for DOI 10.5555/calibration",
        "ko": "DOI 10.5555/calibration 논문의 RIS 인용 파일을 내보내줘",
        "es": "exporta un archivo de cita RIS para DOI 10.5555/calibration",
        "ja": "DOI 10.5555/calibration のRIS引用ファイルを書き出して",
        "de": "exportiere eine RIS-Zitationsdatei für DOI 10.5555/calibration",
        "mixed": "DOI 10.5555/calibration RIS citation file을 export해줘",
    },
    "finance": {
        "en": "calculate the dividend yield forecast for AAPL next year",
        "ko": "AAPL의 내년 예상 배당수익률을 계산해줘",
        "es": "calcula el rendimiento por dividendo previsto de AAPL para el próximo año",
        "ja": "AAPLの来年の予想配当利回りを計算して",
        "de": "berechne die erwartete Dividendenrendite von AAPL für nächstes Jahr",
        "mixed": "AAPL next year dividend yield forecast를 calculate해줘",
    },
    "calendar": {
        "en": "reschedule tomorrow's team sync to Friday afternoon",
        "ko": "내일 팀 미팅을 금요일 오후로 일정 변경해줘",
        "es": "reprograma la reunión de equipo de mañana para el viernes por la tarde",
        "ja": "明日のチームミーティングを金曜午後に変更して",
        "de": "verschiebe den morgigen Team-Termin auf Freitagnachmittag",
        "mixed": "내일 team sync를 Friday afternoon으로 reschedule해줘",
    },
    "support": {
        "en": "assign support ticket 4821 to the billing team",
        "ko": "고객지원 티켓 4821을 결제 팀에 할당해줘",
        "es": "asigna el ticket de soporte 4821 al equipo de facturación",
        "ja": "サポートチケット4821を請求チームに割り当てて",
        "de": "weise Support-Ticket 4821 dem Abrechnungsteam zu",
        "mixed": "support ticket 4821을 billing team에 assign해줘",
    },
    "inventory": {
        "en": "transfer ten units of SKU-778 from warehouse A to warehouse B",
        "ko": "SKU-778 열 개를 창고 A에서 창고 B로 이동해줘",
        "es": "transfiere diez unidades de SKU-778 del almacén A al almacén B",
        "ja": "SKU-778を10個、倉庫Aから倉庫Bへ移動して",
        "de": "übertrage zehn Einheiten von SKU-778 von Lager A nach Lager B",
        "mixed": "SKU-778 10개를 warehouse A에서 B로 transfer해줘",
    },
    "users": {
        "en": "reset the password for user account 314",
        "ko": "사용자 계정 314의 비밀번호를 재설정해줘",
        "es": "restablece la contraseña de la cuenta de usuario 314",
        "ja": "ユーザーアカウント314のパスワードをリセットして",
        "de": "setze das Passwort für Benutzerkonto 314 zurück",
        "mixed": "user account 314의 password를 reset해줘",
    },
}

NEAR_WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "The domain is correct, but do not approximate this action: {core}.",
        "Only route this if the registered contract explicitly supports it: {core}.",
        "A sibling operation is not an acceptable substitute; {core}.",
        "Treat this as no-route unless this exact operation exists: {core}.",
    ),
    "ko": (
        "도메인은 맞지만 이 동작을 근사해서 처리하면 안 돼: {core}.",
        "등록 계약이 명시적으로 지원할 때만 라우팅해: {core}.",
        "비슷한 형제 동작으로 대체하지 말고 {core}.",
        "정확한 동작이 없으면 no-route로 처리해: {core}.",
    ),
    "es": (
        "El dominio es correcto, pero no aproximes esta acción: {core}.",
        "Enruta solo si el contrato registrado lo admite explícitamente: {core}.",
        "Una operación hermana no es un sustituto aceptable; {core}.",
        "Trátalo como sin ruta si esta operación exacta no existe: {core}.",
    ),
    "ja": (
        "ドメインは合っていますが、この操作を近似してはいけません: {core}。",
        "登録契約が明示的に対応する場合だけルーティングして: {core}。",
        "似た兄弟操作で代替せず{core}。",
        "この正確な操作がなければno-routeとして扱って: {core}。",
    ),
    "de": (
        "Die Domäne stimmt, aber nähere diese Aktion nicht an: {core}.",
        "Route nur, wenn der registrierte Vertrag dies ausdrücklich unterstützt: {core}.",
        "Eine Schwesteroperation ist kein zulässiger Ersatz; {core}.",
        "Behandle dies als no-route, wenn diese genaue Operation nicht existiert: {core}.",
    ),
    "mixed": (
        "domain은 맞지만 이 action을 approximate하지 마: {core}.",
        "registered contract가 explicit support할 때만 route해: {core}.",
        "sibling operation으로 substitute하지 말고 {core}.",
        "exact operation이 없으면 no-route로 처리해: {core}.",
    ),
}

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "outline a mystery novel set on a train",
        "explain how sourdough fermentation works",
        "compose a short melody in D minor",
        "compare two styles of landscape painting",
    ),
    "ko": (
        "기차를 배경으로 한 미스터리 소설 개요를 만들어줘",
        "사워도우 발효 원리를 설명해줘",
        "D단조의 짧은 멜로디를 작곡해줘",
        "두 가지 풍경화 화풍을 비교해줘",
    ),
    "es": (
        "esboza una novela de misterio ambientada en un tren",
        "explica cómo funciona la fermentación de masa madre",
        "compón una melodía corta en re menor",
        "compara dos estilos de pintura de paisaje",
    ),
    "ja": (
        "列車を舞台にしたミステリー小説の概要を作って",
        "サワードウ発酵の仕組みを説明して",
        "ニ短調の短いメロディを作曲して",
        "2つの風景画のスタイルを比較して",
    ),
    "de": (
        "entwirf einen Kriminalroman, der in einem Zug spielt",
        "erkläre wie Sauerteigfermentation funktioniert",
        "komponiere eine kurze Melodie in d-Moll",
        "vergleiche zwei Stile der Landschaftsmalerei",
    ),
    "mixed": (
        "train 배경 mystery novel outline을 만들어줘",
        "sourdough fermentation이 어떻게 되는지 설명해줘",
        "D minor short melody를 compose해줘",
        "두 landscape painting style을 compare해줘",
    ),
}


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
                        "id": f"graph-cal-{route_id}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": route_name,
                        "category": "graph_calibration_supported_operation",
                        "expect_abstain": False,
                        "split": "calibration",
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
                        "id": f"graph-cal-near-{domain}-{language}-{index + 1:02d}",
                        "query": wrapper.replace("{core}", core),
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "expect_abstain": True,
                        "split": "calibration",
                        "language": language,
                    }
                )

    for language in LANGUAGES:
        cores = list(OOD[language])
        rng.shuffle(cores)
        for index, core in enumerate(cores):
            cases.append(
                {
                    "id": f"graph-cal-ood-{language}-{index + 1:02d}",
                    "query": core,
                    "expected": None,
                    "category": "out_of_domain",
                    "expect_abstain": True,
                    "split": "calibration",
                    "language": language,
                }
            )

    rng.shuffle(cases)
    return cases


def _development_normalized_queries() -> set[str]:
    return {
        _normalize(str(case["query"]))
        for case in _dev._build(DEVELOPMENT_SEED)
    }


def _validate(cases: list[dict[str, object]]) -> None:
    if len(cases) != 600:
        raise ValueError(f"expected 600 calibration cases, got {len(cases)}")

    ids = [str(case["id"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate graph calibration case IDs")

    normalized = [_normalize(str(case["query"])) for case in cases]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate normalized graph calibration query")

    historical_overlap = _dev._prior_normalized_queries().intersection(normalized)
    if historical_overlap:
        raise ValueError(
            "graph calibration exact-query overlap with historical corpora: "
            f"{len(historical_overlap)}"
        )

    development_overlap = _development_normalized_queries().intersection(normalized)
    if development_overlap:
        raise ValueError(
            "graph calibration exact-query overlap with graph-v1 development: "
            f"{len(development_overlap)}"
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
        "version": "graph-v1-calibration",
        "status": "fresh_confirmation_generated",
        "role": "confirmation_only",
        "tuning_eligible": False,
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
        "normalized_exact_overlap_with_historical_corpora": 0,
        "normalized_exact_overlap_with_graph_v1_development": 0,
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
