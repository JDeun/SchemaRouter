"""Generate disjoint 0.12-B corpora for semantic-action-ontology experiment #349."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from benchmarks.operation_routing_v5b_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.semantic_action_ontology import compile_registry_contracts  # noqa: E402

ACTION_SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "read": {
        "en": ("pull up {obj}", "show me {obj}"),
        "ko": ("{obj} 확인해줘", "{obj} 보여줘"),
        "es": ("consulta {obj}", "muéstrame {obj}"),
        "ja": ("{obj}を確認して", "{obj}を見せて"),
        "de": ("ruf {obj} ab", "zeig mir {obj}"),
        "mixed": ("{obj} 확인해줘", "show {obj}"),
    },
    "create": {
        "en": ("register a new {obj}", "make a fresh {obj}"),
        "ko": ("새 {obj} 등록해줘", "{obj} 새로 만들어줘"),
        "es": ("registra un nuevo {obj}", "crea un {obj} nuevo"),
        "ja": ("新しい{obj}を登録して", "{obj}を新規作成して"),
        "de": ("registriere ein neues {obj}", "lege ein neues {obj} an"),
        "mixed": ("new {obj} 등록해줘", "{obj} 새로 create해줘"),
    },
    "update": {
        "en": ("revise {obj}", "change the details of {obj}"),
        "ko": ("{obj} 내용 고쳐줘", "{obj} 정보 바꿔줘"),
        "es": ("modifica {obj}", "cambia los datos de {obj}"),
        "ja": ("{obj}を修正して", "{obj}の内容を変更して"),
        "de": ("überarbeite {obj}", "ändere die Angaben von {obj}"),
        "mixed": ("{obj} 내용 update해줘", "{obj} details 바꿔줘"),
    },
    "delete": {
        "en": ("erase {obj}", "get rid of {obj} permanently"),
        "ko": ("{obj} 지워줘", "{obj} 완전히 없애줘"),
        "es": ("borra {obj}", "quita {obj} de forma permanente"),
        "ja": ("{obj}を消して", "{obj}を完全に削除して"),
        "de": ("entferne {obj}", "lösche {obj} dauerhaft"),
        "mixed": ("{obj} 지워줘", "{obj} permanently remove해줘"),
    },
    "cancel": {
        "en": ("stop {obj}", "call off {obj}"),
        "ko": ("{obj} 중단해줘", "{obj} 취소 처리해줘"),
        "es": ("detén {obj}", "anula {obj}"),
        "ja": ("{obj}を中止して", "{obj}を取り消して"),
        "de": ("brich {obj} ab", "storniere {obj}"),
        "mixed": ("{obj} 중단해줘", "cancel {obj}"),
    },
    "refund": {
        "en": ("return the money for {obj}", "issue money back for {obj}"),
        "ko": ("{obj} 돈 돌려줘", "{obj} 환불 처리해줘"),
        "es": ("devuelve el dinero de {obj}", "tramita el reembolso de {obj}"),
        "ja": ("{obj}のお金を返して", "{obj}を払い戻して"),
        "de": ("zahle das Geld für {obj} zurück", "erstatte {obj}"),
        "mixed": ("{obj} money 돌려줘", "refund {obj}"),
    },
    "send": {
        "en": ("forward {obj}", "deliver {obj}"),
        "ko": ("{obj} 전달해줘", "{obj} 전송해줘"),
        "es": ("reenvía {obj}", "entrega {obj}"),
        "ja": ("{obj}を転送して", "{obj}を送って"),
        "de": ("leite {obj} weiter", "verschicke {obj}"),
        "mixed": ("{obj} 전달해줘", "send {obj}"),
    },
    "share": {
        "en": ("give someone access to {obj}", "make {obj} available to another user"),
        "ko": ("다른 사람에게 {obj} 접근권한 줘", "{obj} 다른 사용자와 공유해줘"),
        "es": ("da acceso a {obj}", "comparte {obj} con otro usuario"),
        "ja": ("{obj}へのアクセスを他の人に与えて", "{obj}を別のユーザーと共有して"),
        "de": ("gib jemandem Zugriff auf {obj}", "teile {obj} mit einem anderen Nutzer"),
        "mixed": ("{obj} access 공유해줘", "share {obj}"),
    },
    "export": {
        "en": ("save {obj} out to a file", "download a file for {obj}"),
        "ko": ("{obj} 파일로 저장해줘", "{obj} 내려받아줘"),
        "es": ("guarda {obj} en un archivo", "descarga un archivo de {obj}"),
        "ja": ("{obj}をファイルに保存して", "{obj}をダウンロードして"),
        "de": ("speichere {obj} als Datei", "lade {obj} als Datei herunter"),
        "mixed": ("{obj} file로 저장해줘", "download {obj}"),
    },
    "translate": {
        "en": ("render {obj} in another language", "convert the language of {obj}"),
        "ko": ("{obj} 다른 언어로 옮겨줘", "{obj} 언어 바꿔줘"),
        "es": ("pasa {obj} a otro idioma", "cambia el idioma de {obj}"),
        "ja": ("{obj}を別の言語にして", "{obj}の言語を変えて"),
        "de": ("übertrage {obj} in eine andere Sprache", "ändere die Sprache von {obj}"),
        "mixed": ("{obj} 다른 language로 바꿔줘", "translate {obj}"),
    },
    "summarize": {
        "en": ("condense {obj}", "give only the main points of {obj}"),
        "ko": ("{obj} 핵심만 줄여줘", "{obj} 중요한 내용만 정리해줘"),
        "es": ("condensa {obj}", "dame solo los puntos principales de {obj}"),
        "ja": ("{obj}を短くまとめて", "{obj}の要点だけ教えて"),
        "de": ("kürze {obj} auf die Kernaussagen", "gib nur die Hauptpunkte von {obj}"),
        "mixed": ("{obj} 핵심만 줄여줘", "summarize {obj}"),
    },
    "compare": {
        "en": ("set {obj} side by side", "tell me the differences in {obj}"),
        "ko": ("{obj} 나란히 비교해줘", "{obj} 차이점 알려줘"),
        "es": ("pon {obj} lado a lado", "dime las diferencias de {obj}"),
        "ja": ("{obj}を並べて比べて", "{obj}の違いを教えて"),
        "de": ("stelle {obj} gegenüber", "nenne die Unterschiede bei {obj}"),
        "mixed": ("{obj} 차이 compare해줘", "compare {obj}"),
    },
    "merge": {
        "en": ("join {obj} together", "consolidate {obj} into one"),
        "ko": ("{obj} 하나로 합쳐줘", "{obj} 통합해줘"),
        "es": ("une {obj}", "consolida {obj} en uno"),
        "ja": ("{obj}を一つにまとめて", "{obj}を統合して"),
        "de": ("führe {obj} zusammen", "vereinige {obj} zu einem"),
        "mixed": ("{obj} 하나로 merge해줘", "combine {obj}"),
    },
    "restart": {
        "en": ("cycle {obj}", "bring {obj} back up"),
        "ko": ("{obj} 다시 시작해줘", "{obj} 껐다 켜줘"),
        "es": ("vuelve a iniciar {obj}", "arranca de nuevo {obj}"),
        "ja": ("{obj}をもう一度起動して", "{obj}を再始動して"),
        "de": ("starte {obj} erneut", "fahre {obj} neu hoch"),
        "mixed": ("{obj} 다시 start해줘", "restart {obj}"),
    },
    "execute": {
        "en": ("launch {obj}", "fire off {obj}"),
        "ko": ("{obj} 돌려줘", "{obj} 시작해줘"),
        "es": ("lanza {obj}", "pon en marcha {obj}"),
        "ja": ("{obj}を起動して", "{obj}を走らせて"),
        "de": ("starte {obj}", "stoße {obj} an"),
        "mixed": ("{obj} 돌려줘", "run {obj}"),
    },
    "forecast": {
        "en": ("estimate what comes next for {obj}", "project the future of {obj}"),
        "ko": ("{obj} 앞으로 어떻게 될지 예측해줘", "{obj} 미래 값 전망해줘"),
        "es": ("estima lo que viene para {obj}", "proyecta el futuro de {obj}"),
        "ja": ("{obj}の今後を見積もって", "{obj}の将来値を予測して"),
        "de": ("schätze die zukünftige Entwicklung von {obj}", "projiziere die Zukunft von {obj}"),
        "mixed": ("{obj} future 예측해줘", "forecast {obj}"),
    },
}

TEMPORAL_WORDS: dict[str, dict[str, str]] = {
    "current": {
        "en": "right now",
        "ko": "지금",
        "es": "ahora",
        "ja": "今の",
        "de": "jetzt",
        "mixed": "지금",
    },
    "future": {
        "en": "next period",
        "ko": "향후",
        "es": "próximo período",
        "ja": "今後の",
        "de": "künftig",
        "mixed": "future",
    },
    "historical": {
        "en": "from the past",
        "ko": "과거",
        "es": "del pasado",
        "ja": "過去の",
        "de": "aus der Vergangenheit",
        "mixed": "past",
    },
}

UNSUPPORTED_ACTIONS = (
    "create",
    "update",
    "delete",
    "cancel",
    "refund",
    "send",
    "share",
    "export",
    "translate",
    "summarize",
    "compare",
    "merge",
    "restart",
    "execute",
    "forecast",
)

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "draft a haiku about rain",
        "write a detective scene",
        "explain why leaves change color",
        "explain how gravity works",
        "work out 81 divided by 9",
        "solve 15 plus 28",
        "tell a riddle",
        "make a friendly greeting",
        "compose a jazz melody",
        "write a limerick",
        "calculate the cube root of 27",
        "explain natural selection",
    ),
    "ko": (
        "비에 대한 하이쿠 써줘",
        "탐정 장면을 써줘",
        "잎 색이 변하는 이유 설명해줘",
        "중력이 작동하는 원리 설명해줘",
        "81 나누기 9 계산해줘",
        "15 더하기 28 풀어줘",
        "수수께끼 하나 내줘",
        "친근한 인사말 해줘",
        "재즈 멜로디 작곡해줘",
        "리머릭 시 써줘",
        "27의 세제곱근 계산해줘",
        "자연선택을 설명해줘",
    ),
    "es": (
        "escribe un haiku sobre la lluvia",
        "escribe una escena detectivesca",
        "explica por qué cambian de color las hojas",
        "explica cómo funciona la gravedad",
        "calcula 81 dividido entre 9",
        "resuelve 15 más 28",
        "dime una adivinanza",
        "haz un saludo amistoso",
        "compón una melodía de jazz",
        "escribe un limerick",
        "calcula la raíz cúbica de 27",
        "explica la selección natural",
    ),
    "ja": (
        "雨について俳句を書いて",
        "探偵の場面を書いて",
        "葉の色が変わる理由を説明して",
        "重力の仕組みを説明して",
        "81割る9を計算して",
        "15足す28を解いて",
        "なぞなぞを言って",
        "親しみやすい挨拶をして",
        "ジャズのメロディーを作曲して",
        "リメリックを書いて",
        "27の立方根を計算して",
        "自然選択を説明して",
    ),
    "de": (
        "schreibe ein haiku über regen",
        "schreibe eine detektivszene",
        "erkläre warum blätter ihre farbe ändern",
        "erkläre wie gravitation funktioniert",
        "berechne 81 geteilt durch 9",
        "löse 15 plus 28",
        "stell mir ein rätsel",
        "formuliere eine freundliche begrüßung",
        "komponiere eine jazzmelodie",
        "schreibe einen limerick",
        "berechne die kubikwurzel aus 27",
        "erkläre natürliche selektion",
    ),
    "mixed": (
        "rain에 대한 haiku 써줘",
        "detective scene 써줘",
        "leaves 색이 변하는 이유 explain해줘",
        "gravity 작동 원리 explain해줘",
        "81 divided by 9 계산해줘",
        "15 plus 28 풀어줘",
        "riddle 하나 내줘",
        "friendly greeting 해줘",
        "jazz melody 작곡해줘",
        "limerick 써줘",
        "27 cube root 계산해줘",
        "natural selection 설명해줘",
    ),
}


def _bytes(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _obj(spec: RouteCaseSpec, language: str) -> str:
    obj = spec.objects[language]
    if spec.temporal_scope:
        temporal = TEMPORAL_WORDS[spec.temporal_scope][language]
        return f"{temporal} {obj}"
    return obj


def _supported(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        route_slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _obj(spec, language)
            for index, template in enumerate(ACTION_SURFACES[spec.action][language], start=1):
                rows.append({
                    "id": f"{prefix}-supported-{route_slug}-{language}-{index}",
                    "query": template.format(obj=obj),
                    "expected": spec.route_id,
                    "category": "supported",
                    "language": language,
                })
    return rows


def _by_tool(specs: tuple[RouteCaseSpec, ...]) -> dict[str, list[RouteCaseSpec]]:
    result: dict[str, list[RouteCaseSpec]] = {}
    for spec in specs:
        tool = spec.route_id.split(".", 1)[0]
        result.setdefault(tool, []).append(spec)
    return result


def _near(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_by_tool(specs).items()):
        supported_actions = {spec.action for spec in tool_specs}
        unsupported = [
            action for action in UNSUPPORTED_ACTIONS
            if action not in supported_actions
        ][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for action_index, action in enumerate(unsupported, start=1):
                template = ACTION_SURFACES[action][language][1]
                rows.append({
                    "id": f"{prefix}-near-{tool}-{language}-{action_index}",
                    "query": template.format(obj=obj),
                    "expected": None,
                    "category": "near_domain_unsupported_operation",
                    "language": language,
                    "unsupported_action": action,
                    "unsupported_family": f"{tool}.{action}",
                })
    return rows


def _ood(prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{prefix}-ood-{language}-{index}",
            "query": query,
            "expected": None,
            "category": "out_of_domain",
            "language": language,
        }
        for language in LANGUAGES
        for index, query in enumerate(OOD[language], start=1)
    ]


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v5b-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5b-confirm"
    else:
        raise ValueError("unknown role")

    contracts = compile_registry_contracts(registry)
    expected_routes = {spec.route_id for spec in specs}
    if set(contracts) != expected_routes:
        raise ValueError(
            f"route fixture mismatch missing={sorted(expected_routes-set(contracts))} "
            f"extra={sorted(set(contracts)-expected_routes)}"
        )

    rows = [*_supported(specs, prefix), *_near(specs, prefix), *_ood(prefix)]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate case IDs")

    supported = [row for row in rows if row["expected"] is not None]
    near = [row for row in rows if row["category"] == "near_domain_unsupported_operation"]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    manifest = {
        "role": role,
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "route_count": len(contracts),
        "tool_count": len(registry.tools()),
        "endpoint_counts": sorted(len(tool.endpoints) for tool in registry.tools()),
        "languages": list(LANGUAGES),
        "adapters": sorted({contract.adapter or "native" for contract in contracts.values()}),
        "corpus_sha256": hashlib.sha256(_bytes(rows)).hexdigest(),
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    freeze: dict[str, Any] = {}
    for role in ("development", "confirmation"):
        rows, manifest = build(role)
        (args.out_dir / f"{role}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (args.out_dir / f"{role}-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        freeze[role] = manifest

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
