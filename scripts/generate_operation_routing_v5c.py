# ruff: noqa: E501
"""Generate disjoint 0.12-C corpora for factorized resource-action experiment #355."""

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

from benchmarks.factorized_resource_action import compile_registry_contracts  # noqa: E402
from benchmarks.operation_routing_v5c_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)

ACTION_SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "read": {
        "en": ("bring up {obj}", "look up {obj}"),
        "ko": ("{obj} 조회해줘", "{obj} 찾아봐줘"),
        "es": ("recupera {obj}", "busca {obj}"),
        "ja": ("{obj}を取得して", "{obj}を検索して"),
        "de": ("rufe {obj} auf", "suche {obj}"),
        "mixed": ("{obj} lookup해줘", "{obj} 찾아줘"),
    },
    "create": {
        "en": ("set up a new {obj}", "add {obj} as a new item"),
        "ko": ("새 {obj} 만들어줘", "{obj} 새 항목으로 추가해줘"),
        "es": ("configura un nuevo {obj}", "añade {obj} como elemento nuevo"),
        "ja": ("新しい{obj}を設定して", "{obj}を新規項目として追加して"),
        "de": ("richte ein neues {obj} ein", "füge {obj} als neues Element hinzu"),
        "mixed": ("new {obj} 만들어줘", "{obj} 새 item으로 add해줘"),
    },
    "update": {
        "en": ("edit {obj}", "revise the stored details for {obj}"),
        "ko": ("{obj} 수정해줘", "{obj} 저장 정보 고쳐줘"),
        "es": ("edita {obj}", "revisa los datos guardados de {obj}"),
        "ja": ("{obj}を編集して", "{obj}の保存情報を修正して"),
        "de": ("bearbeite {obj}", "überarbeite die gespeicherten Angaben für {obj}"),
        "mixed": ("{obj} edit해줘", "{obj} 저장 details 고쳐줘"),
    },
    "delete": {
        "en": ("remove {obj} for good", "wipe {obj}"),
        "ko": ("{obj} 완전히 삭제해줘", "{obj} 지워버려"),
        "es": ("elimina {obj} definitivamente", "borra {obj}"),
        "ja": ("{obj}を完全に削除して", "{obj}を消去して"),
        "de": ("entferne {obj} endgültig", "lösche {obj}"),
        "mixed": ("{obj} 완전히 delete해줘", "wipe {obj}"),
    },
    "cancel": {
        "en": ("terminate {obj}", "withdraw {obj}"),
        "ko": ("{obj} 종료해줘", "{obj} 철회해줘"),
        "es": ("termina {obj}", "retira {obj}"),
        "ja": ("{obj}を終了して", "{obj}を取り下げて"),
        "de": ("beende {obj}", "ziehe {obj} zurück"),
        "mixed": ("{obj} 종료해줘", "withdraw {obj}"),
    },
    "refund": {
        "en": ("pay back {obj}", "reverse the payment for {obj}"),
        "ko": ("{obj} 금액 돌려줘", "{obj} 결제 되돌려줘"),
        "es": ("devuelve el importe de {obj}", "revierte el pago de {obj}"),
        "ja": ("{obj}の金額を返して", "{obj}の支払いを戻して"),
        "de": ("zahle den Betrag für {obj} zurück", "mache die Zahlung für {obj} rückgängig"),
        "mixed": ("{obj} 금액 pay back해줘", "reverse payment for {obj}"),
    },
    "send": {
        "en": ("transmit {obj}", "pass {obj} along"),
        "ko": ("{obj} 보내줘", "{obj} 전달해줘"),
        "es": ("transmite {obj}", "pasa {obj}"),
        "ja": ("{obj}を送信して", "{obj}を転送して"),
        "de": ("übermittle {obj}", "leite {obj} weiter"),
        "mixed": ("{obj} transmit해줘", "{obj} 전달해줘"),
    },
    "share": {
        "en": ("grant access to {obj}", "let another user see {obj}"),
        "ko": ("{obj} 접근 권한 줘", "다른 사용자가 {obj} 보게 해줘"),
        "es": ("concede acceso a {obj}", "permite que otro usuario vea {obj}"),
        "ja": ("{obj}へのアクセス権を与えて", "別のユーザーが{obj}を見られるようにして"),
        "de": ("gewähre Zugriff auf {obj}", "lass einen anderen Nutzer {obj} sehen"),
        "mixed": ("{obj} access 권한 줘", "another user에게 {obj} 공유해줘"),
    },
    "export": {
        "en": ("produce a file from {obj}", "save {obj} outside the system"),
        "ko": ("{obj} 파일로 뽑아줘", "{obj} 외부 파일로 저장해줘"),
        "es": ("genera un archivo de {obj}", "guarda {obj} fuera del sistema"),
        "ja": ("{obj}からファイルを作って", "{obj}を外部ファイルに保存して"),
        "de": ("erzeuge eine Datei aus {obj}", "speichere {obj} außerhalb des Systems"),
        "mixed": ("{obj} file로 뽑아줘", "save {obj} outside system"),
    },
    "translate": {
        "en": ("put {obj} into another language", "change {obj} to Korean"),
        "ko": ("{obj} 다른 언어로 바꿔줘", "{obj} 한국어로 옮겨줘"),
        "es": ("pon {obj} en otro idioma", "pasa {obj} al coreano"),
        "ja": ("{obj}を別の言語に変えて", "{obj}を韓国語にして"),
        "de": ("übertrage {obj} in eine andere Sprache", "übertrage {obj} ins Koreanische"),
        "mixed": ("{obj} another language로 바꿔줘", "{obj} Korean으로 옮겨줘"),
    },
    "summarize": {
        "en": ("boil {obj} down to the key points", "shorten {obj} to its essentials"),
        "ko": ("{obj} 핵심만 추려줘", "{obj} 중요한 내용만 짧게 정리해줘"),
        "es": ("reduce {obj} a los puntos clave", "acorta {obj} a lo esencial"),
        "ja": ("{obj}の要点だけにまとめて", "{obj}を重要点だけに短くして"),
        "de": ("reduziere {obj} auf die Kernpunkte", "kürze {obj} auf das Wesentliche"),
        "mixed": ("{obj} key points만 추려줘", "shorten {obj} to essentials"),
    },
    "compare": {
        "en": ("contrast {obj}", "show how {obj} differ"),
        "ko": ("{obj} 대조해줘", "{obj} 뭐가 다른지 보여줘"),
        "es": ("contrasta {obj}", "muestra en qué se diferencian {obj}"),
        "ja": ("{obj}を対比して", "{obj}の違いを見せて"),
        "de": ("stelle {obj} gegenüber", "zeige wie sich {obj} unterscheiden"),
        "mixed": ("{obj} contrast해줘", "{obj} differences 보여줘"),
    },
    "merge": {
        "en": ("fold {obj} into one", "unify {obj}"),
        "ko": ("{obj} 하나로 묶어줘", "{obj} 통합해줘"),
        "es": ("integra {obj} en uno", "unifica {obj}"),
        "ja": ("{obj}を一つにまとめて", "{obj}を統合して"),
        "de": ("führe {obj} zu einem zusammen", "vereinheitliche {obj}"),
        "mixed": ("{obj} 하나로 combine해줘", "unify {obj}"),
    },
    "restart": {
        "en": ("relaunch {obj}", "start {obj} over"),
        "ko": ("{obj} 다시 띄워줘", "{obj} 처음부터 다시 시작해줘"),
        "es": ("vuelve a lanzar {obj}", "inicia {obj} de nuevo"),
        "ja": ("{obj}を再び起動して", "{obj}を最初からやり直して"),
        "de": ("starte {obj} erneut", "beginne {obj} neu"),
        "mixed": ("{obj} 다시 launch해줘", "start {obj} over"),
    },
    "execute": {
        "en": ("kick off {obj}", "invoke {obj}"),
        "ko": ("{obj} 가동해줘", "{obj} 호출해줘"),
        "es": ("pon en marcha {obj}", "invoca {obj}"),
        "ja": ("{obj}を開始して", "{obj}を呼び出して"),
        "de": ("stoße {obj} an", "rufe {obj} auf"),
        "mixed": ("{obj} kick off해줘", "invoke {obj}"),
    },
    "forecast": {
        "en": ("project what will happen to {obj}", "estimate the next value of {obj}"),
        "ko": ("{obj} 앞으로 어떻게 될지 전망해줘", "{obj} 다음 값 추정해줘"),
        "es": ("proyecta qué pasará con {obj}", "estima el próximo valor de {obj}"),
        "ja": ("{obj}が今後どうなるか予測して", "{obj}の次の値を見積もって"),
        "de": ("projiziere die künftige Entwicklung von {obj}", "schätze den nächsten Wert von {obj}"),
        "mixed": ("{obj} future 어떻게 될지 project해줘", "next value of {obj} 추정해줘"),
    },
}

TEMPORAL: dict[str, dict[str, str]] = {
    "current": {"en":"at the moment","ko":"현재","es":"en este momento","ja":"現在の","de":"im Moment","mixed":"현재"},
    "future": {"en":"in the future","ko":"앞으로","es":"en el futuro","ja":"将来の","de":"in Zukunft","mixed":"future"},
    "historical": {"en":"historically","ko":"이전","es":"históricamente","ja":"過去の","de":"historisch","mixed":"historical"},
}

UNSUPPORTED = (
    "create","update","delete","cancel","refund","send","share","export",
    "translate","summarize","compare","merge","restart","execute","forecast",
)

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "write a sonnet about fog","invent a bedtime story","explain why ice floats",
        "explain how eclipses happen","calculate 144 divided by 12","solve 23 plus 41",
        "tell me a pun","say hello in a cheerful way","compose a blues riff","write a short fairy tale",
        "calculate the square of 17","explain plate tectonics",
    ),
    "ko": (
        "안개에 대한 소네트 써줘","잠자리 동화 하나 만들어줘","얼음이 뜨는 이유 설명해줘",
        "일식이 생기는 원리 설명해줘","144 나누기 12 계산해줘","23 더하기 41 풀어줘",
        "말장난 하나 해줘","밝게 인사해줘","블루스 리프 작곡해줘","짧은 동화 써줘",
        "17의 제곱 계산해줘","판 구조론 설명해줘",
    ),
    "es": (
        "escribe un soneto sobre la niebla","inventa un cuento para dormir","explica por qué flota el hielo",
        "explica cómo ocurren los eclipses","calcula 144 dividido entre 12","resuelve 23 más 41",
        "dime un juego de palabras","saluda de forma alegre","compón un riff de blues","escribe un cuento de hadas corto",
        "calcula el cuadrado de 17","explica la tectónica de placas",
    ),
    "ja": (
        "霧についてソネットを書いて","寝る前の物語を作って","氷が浮く理由を説明して",
        "日食が起こる仕組みを説明して","144割る12を計算して","23足す41を解いて",
        "駄洒落を言って","明るく挨拶して","ブルースのリフを作曲して","短い童話を書いて",
        "17の二乗を計算して","プレートテクトニクスを説明して",
    ),
    "de": (
        "schreibe ein sonett über nebel","erfinde eine gute-nacht-geschichte","erkläre warum eis schwimmt",
        "erkläre wie sonnenfinsternisse entstehen","berechne 144 geteilt durch 12","löse 23 plus 41",
        "erzähl ein wortspiel","begrüße mich fröhlich","komponiere ein blues-riff","schreibe ein kurzes märchen",
        "berechne das quadrat von 17","erkläre plattentektonik",
    ),
    "mixed": (
        "fog에 대한 sonnet 써줘","bedtime story 만들어줘","ice가 뜨는 이유 explain해줘",
        "eclipse 원리 explain해줘","144 divided by 12 계산해줘","23 plus 41 풀어줘",
        "pun 하나 해줘","cheerful하게 hello 해줘","blues riff 작곡해줘","short fairy tale 써줘",
        "17 square 계산해줘","plate tectonics 설명해줘",
    ),
}


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _object(spec: RouteCaseSpec, language: str) -> str:
    value = spec.objects[language]
    if spec.temporal_scope:
        return f"{TEMPORAL[spec.temporal_scope][language]} {value}"
    return value


def _supported(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for index, template in enumerate(ACTION_SURFACES[spec.action][language], start=1):
                rows.append({
                    "id": f"{prefix}-supported-{slug}-{language}-{index}",
                    "query": template.format(obj=obj),
                    "expected": spec.route_id,
                    "category": "supported",
                    "language": language,
                })
    return rows


def _by_tool(specs: tuple[RouteCaseSpec, ...]) -> dict[str, list[RouteCaseSpec]]:
    result: dict[str, list[RouteCaseSpec]] = {}
    for spec in specs:
        result.setdefault(spec.route_id.split(".", 1)[0], []).append(spec)
    return result


def _near(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_by_tool(specs).items()):
        supported_actions = {spec.action for spec in tool_specs}
        unsupported_actions = [action for action in UNSUPPORTED if action not in supported_actions][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, action in enumerate(unsupported_actions, start=1):
                # Use one phrasing family per unsupported action; no phrase tuning after scoring.
                query = ACTION_SURFACES[action][language][0].format(obj=obj)
                rows.append({
                    "id": f"{prefix}-near-{tool}-{language}-{index}",
                    "query": query,
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
        prefix = "v5c-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5c-confirm"
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(
            f"route fixture mismatch missing={sorted(expected-set(contracts))} "
            f"extra={sorted(set(contracts)-expected)}"
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
        "corpus_sha256": hashlib.sha256(_canonical(rows)).hexdigest(),
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
        (args.out_dir / f"{role}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.out_dir / f"{role}-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        freeze[role] = manifest

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
