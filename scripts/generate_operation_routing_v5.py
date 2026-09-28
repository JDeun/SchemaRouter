"""Generate disjoint 0.12 development and confirmation corpora for experiment #347."""

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

from benchmarks.operation_routing_v5_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.query_first_typed_frame import (  # noqa: E402
    compile_registry_contracts,
)

_SURFACE_ACTIONS: dict[str, dict[str, tuple[str, str]]] = {
    "read": {
        "en": ("show me {obj}", "get {obj}"),
        "ko": ("{obj}를 보여줘", "{obj}를 가져와줘"),
        "es": ("muestra {obj}", "obtén {obj}"),
        "ja": ("{obj}を表示して", "{obj}を取得して"),
        "de": ("zeige {obj}", "hole {obj}"),
        "mixed": ("{obj} 보여줘", "get {obj}"),
    },
    "retrieve": {
        "en": ("retrieve {obj}", "show me {obj}"),
        "ko": ("{obj}를 불러와줘", "{obj}를 보여줘"),
        "es": ("recupera {obj}", "muestra {obj}"),
        "ja": ("{obj}を取得して", "{obj}を表示して"),
        "de": ("hole {obj}", "zeige {obj}"),
        "mixed": ("retrieve {obj}", "{obj} 보여줘"),
    },
    "search": {
        "en": ("search for {obj}", "find {obj}"),
        "ko": ("{obj}를 검색해줘", "{obj}를 찾아줘"),
        "es": ("busca {obj}", "encuentra {obj}"),
        "ja": ("{obj}を検索して", "{obj}を探して"),
        "de": ("suche nach {obj}", "finde {obj}"),
        "mixed": ("search {obj}", "{obj} 찾아줘"),
    },
    "list": {
        "en": ("list {obj}", "show all {obj}"),
        "ko": ("{obj} 목록을 보여줘", "{obj}를 모두 보여줘"),
        "es": ("lista {obj}", "muestra todos los {obj}"),
        "ja": ("{obj}を一覧表示して", "{obj}を全部表示して"),
        "de": ("liste {obj} auf", "zeige alle {obj}"),
        "mixed": ("list {obj}", "{obj} 전부 보여줘"),
    },
    "create": {
        "en": ("create {obj}", "add a new {obj}"),
        "ko": ("{obj}를 만들어줘", "새 {obj}를 추가해줘"),
        "es": ("crea {obj}", "añade un nuevo {obj}"),
        "ja": ("{obj}を作成して", "新しい{obj}を追加して"),
        "de": ("erstelle {obj}", "füge ein neues {obj} hinzu"),
        "mixed": ("create {obj}", "새 {obj} add해줘"),
    },
    "update": {
        "en": ("update {obj}", "change {obj}"),
        "ko": ("{obj}를 수정해줘", "{obj}를 변경해줘"),
        "es": ("actualiza {obj}", "cambia {obj}"),
        "ja": ("{obj}を更新して", "{obj}を変更して"),
        "de": ("aktualisiere {obj}", "ändere {obj}"),
        "mixed": ("update {obj}", "{obj} 변경해줘"),
    },
    "delete": {
        "en": ("delete {obj}", "remove {obj}"),
        "ko": ("{obj}를 삭제해줘", "{obj}를 제거해줘"),
        "es": ("elimina {obj}", "borra {obj}"),
        "ja": ("{obj}を削除して", "{obj}を消して"),
        "de": ("lösche {obj}", "entferne {obj}"),
        "mixed": ("delete {obj}", "{obj} 삭제해줘"),
    },
    "cancel": {
        "en": ("cancel {obj}", "abort {obj}"),
        "ko": ("{obj}를 취소해줘", "{obj}를 철회해줘"),
        "es": ("cancela {obj}", "revoca {obj}"),
        "ja": ("{obj}をキャンセルして", "{obj}を取り消して"),
        "de": ("storniere {obj}", "brich {obj} ab"),
        "mixed": ("cancel {obj}", "{obj} 취소해줘"),
    },
    "refund": {
        "en": ("refund {obj}", "reimburse {obj}"),
        "ko": ("{obj}를 환불해줘", "{obj} 금액을 돌려줘"),
        "es": ("reembolsa {obj}", "haz un reembolso de {obj}"),
        "ja": ("{obj}を返金して", "{obj}の払い戻しをして"),
        "de": ("erstatte {obj}", "zahle {obj} zurück"),
        "mixed": ("refund {obj}", "{obj} 환불해줘"),
    },
    "send": {
        "en": ("send {obj}", "dispatch {obj}"),
        "ko": ("{obj}를 보내줘", "{obj}를 전송해줘"),
        "es": ("envía {obj}", "despacha {obj}"),
        "ja": ("{obj}を送って", "{obj}を送信して"),
        "de": ("sende {obj}", "verschicke {obj}"),
        "mixed": ("send {obj}", "{obj} 보내줘"),
    },
    "share": {
        "en": ("share {obj}", "share access to {obj}"),
        "ko": ("{obj}를 공유해줘", "{obj} 접근권한을 공유해줘"),
        "es": ("comparte {obj}", "comparte el acceso a {obj}"),
        "ja": ("{obj}を共有して", "{obj}へのアクセスを共有して"),
        "de": ("teile {obj}", "teile den zugriff auf {obj}"),
        "mixed": ("share {obj}", "{obj} 공유해줘"),
    },
    "export": {
        "en": ("export {obj}", "download {obj}"),
        "ko": ("{obj}를 내보내줘", "{obj}를 다운로드해줘"),
        "es": ("exporta {obj}", "descarga {obj}"),
        "ja": ("{obj}をエクスポートして", "{obj}をダウンロードして"),
        "de": ("exportiere {obj}", "lade {obj} herunter"),
        "mixed": ("export {obj}", "{obj} 다운로드해줘"),
    },
    "translate": {
        "en": ("translate {obj}", "translate {obj} into Korean"),
        "ko": ("{obj}를 번역해줘", "{obj}를 영어로 번역해줘"),
        "es": ("traduce {obj}", "traduce {obj} al coreano"),
        "ja": ("{obj}を翻訳して", "{obj}を韓国語に翻訳して"),
        "de": ("übersetze {obj}", "übersetze {obj} ins Koreanische"),
        "mixed": ("translate {obj}", "{obj} 한국어로 번역해줘"),
    },
    "summarize": {
        "en": ("summarize {obj}", "give me a summary of {obj}"),
        "ko": ("{obj}를 요약해줘", "{obj}의 요약을 만들어줘"),
        "es": ("resume {obj}", "dame un resumen de {obj}"),
        "ja": ("{obj}を要約して", "{obj}の要約を作って"),
        "de": ("fasse {obj} zusammen", "gib mir eine zusammenfassung von {obj}"),
        "mixed": ("summarize {obj}", "{obj} 요약해줘"),
    },
    "compare": {
        "en": ("compare {obj}", "contrast {obj}"),
        "ko": ("{obj}를 비교해줘", "{obj}의 차이를 비교해줘"),
        "es": ("compara {obj}", "contrasta {obj}"),
        "ja": ("{obj}を比較して", "{obj}の違いを比較して"),
        "de": ("vergleiche {obj}", "stelle {obj} gegenüber"),
        "mixed": ("compare {obj}", "{obj} 비교해줘"),
    },
    "merge": {
        "en": ("merge {obj}", "combine {obj}"),
        "ko": ("{obj}를 병합해줘", "{obj}를 합쳐줘"),
        "es": ("fusiona {obj}", "combina {obj}"),
        "ja": ("{obj}を統合して", "{obj}を結合して"),
        "de": ("führe {obj} zusammen", "kombiniere {obj}"),
        "mixed": ("merge {obj}", "{obj} 합쳐줘"),
    },
    "restart": {
        "en": ("restart {obj}", "reboot {obj}"),
        "ko": ("{obj}를 재시작해줘", "{obj}를 재부팅해줘"),
        "es": ("reinicia {obj}", "vuelve a iniciar {obj}"),
        "ja": ("{obj}を再起動して", "{obj}をリスタートして"),
        "de": ("starte {obj} neu", "reboote {obj}"),
        "mixed": ("restart {obj}", "{obj} 재부팅해줘"),
    },
    "execute": {
        "en": ("execute {obj}", "run {obj}"),
        "ko": ("{obj}를 실행해줘", "{obj}를 돌려줘"),
        "es": ("ejecuta {obj}", "corre {obj}"),
        "ja": ("{obj}を実行して", "{obj}を走らせて"),
        "de": ("führe {obj} aus", "starte {obj}"),
        "mixed": ("execute {obj}", "{obj} 실행해줘"),
    },
    "forecast": {
        "en": ("forecast {obj}", "predict {obj}"),
        "ko": ("{obj}를 예측해줘", "{obj}를 전망해줘"),
        "es": ("pronostica {obj}", "predice {obj}"),
        "ja": ("{obj}を予測して", "{obj}を見通して"),
        "de": ("prognostiziere {obj}", "sage {obj} voraus"),
        "mixed": ("forecast {obj}", "{obj} 예측해줘"),
    },
}

_TEMPORAL_SURFACE: dict[str, dict[str, str]] = {
    "current": {
        "en": "current",
        "ko": "현재",
        "es": "actual",
        "ja": "現在の",
        "de": "aktuell",
        "mixed": "현재",
    },
    "future": {
        "en": "future",
        "ko": "앞으로의",
        "es": "futuro",
        "ja": "将来の",
        "de": "zukünftig",
        "mixed": "future",
    },
    "historical": {
        "en": "historical",
        "ko": "과거",
        "es": "histórico",
        "ja": "過去の",
        "de": "historisch",
        "mixed": "historical",
    },
}

_WRAPPERS: dict[str, tuple[str, str]] = {
    "en": ("{core}", "please {core}"),
    "ko": ("{core}", "부탁인데 {core}"),
    "es": ("{core}", "por favor, {core}"),
    "ja": ("{core}", "お願い、{core}"),
    "de": ("{core}", "bitte {core}"),
    "mixed": ("{core}", "please {core}"),
}

_UNSUPPORTED_POOL = (
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

_OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "write a poem about moonlight",
        "write a story about a lighthouse",
        "explain why the sky looks blue",
        "explain photosynthesis",
        "calculate the square root of 144",
        "compute 37 times 19",
        "tell me a joke",
        "tell me a joke about robots",
        "compose music in D minor",
        "write a poem about winter",
        "calculate 12 factorial",
        "explain quantum entanglement",
    ),
    "ko": (
        "달빛에 대한 시를 써줘",
        "등대에 대한 이야기를 써줘",
        "하늘이 파란 이유를 설명해줘",
        "광합성을 설명해줘",
        "144의 제곱근을 계산해줘",
        "37 곱하기 19를 계산해줘",
        "농담 하나 해줘",
        "로봇에 대한 농담을 해줘",
        "D단조로 작곡해줘",
        "겨울에 대한 시를 써줘",
        "12 팩토리얼을 계산해줘",
        "양자 얽힘을 설명해줘",
    ),
    "es": (
        "escribe un poema sobre la luna",
        "escribe una historia sobre un faro",
        "explica por qué el cielo es azul",
        "explica la fotosíntesis",
        "calcula la raíz cuadrada de 144",
        "calcula 37 por 19",
        "cuéntame un chiste",
        "cuéntame un chiste sobre robots",
        "compón música en re menor",
        "escribe un poema sobre el invierno",
        "calcula 12 factorial",
        "explica el entrelazamiento cuántico",
    ),
    "ja": (
        "月明かりについて詩を書いて",
        "灯台について物語を書いて",
        "空が青い理由を説明して",
        "光合成を説明して",
        "144の平方根を計算して",
        "37かける19を計算して",
        "冗談を言って",
        "ロボットについて冗談を言って",
        "ニ短調で作曲して",
        "冬について詩を書いて",
        "12の階乗を計算して",
        "量子もつれを説明して",
    ),
    "de": (
        "schreibe ein gedicht über mondlicht",
        "schreibe eine geschichte über einen leuchtturm",
        "erkläre warum der himmel blau ist",
        "erkläre photosynthese",
        "berechne die quadratwurzel von 144",
        "berechne 37 mal 19",
        "erzähl mir einen witz",
        "erzähl mir einen witz über roboter",
        "komponiere musik in d-moll",
        "schreibe ein gedicht über den winter",
        "berechne 12 fakultät",
        "erkläre quantenverschränkung",
    ),
    "mixed": (
        "moonlight에 대한 poem 써줘",
        "lighthouse에 대한 story 써줘",
        "sky가 blue인 이유를 explain해줘",
        "photosynthesis를 설명해줘",
        "144 square root를 계산해줘",
        "37 times 19 계산해줘",
        "robot joke 하나 해줘",
        "tell me a joke about 로봇",
        "D minor로 작곡해줘",
        "winter에 대한 poem 써줘",
        "12 factorial 계산해줘",
        "quantum entanglement를 explain해줘",
    ),
}


def _canonical_bytes(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _surface_object(spec: RouteCaseSpec, language: str) -> str:
    obj = spec.object_terms[language]
    detail = spec.detail_terms[language] if spec.detail_terms else ""
    if detail:
        obj = f"{obj} {detail}"
    if spec.temporal_scope is not None:
        temporal = _TEMPORAL_SURFACE[spec.temporal_scope][language]
        if language == "ja":
            obj = f"{temporal}{obj}"
        else:
            obj = f"{temporal} {obj}"
    return obj


def _supported_rows(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        phrases = _SURFACE_ACTIONS[spec.surface_action]
        safe_route = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _surface_object(spec, language)
            for phrase_index, template in enumerate(phrases[language], start=1):
                core = template.format(obj=obj)
                for wrap_index, wrapper in enumerate(_WRAPPERS[language], start=1):
                    rows.append(
                        {
                            "id": (
                                f"{prefix}-supported-{safe_route}-{language}-"
                                f"{phrase_index}-{wrap_index}"
                            ),
                            "query": wrapper.format(core=core),
                            "expected": spec.route_id,
                            "category": "supported",
                            "language": language,
                        }
                    )
    return rows


def _tool_specs(specs: tuple[RouteCaseSpec, ...]) -> dict[str, list[RouteCaseSpec]]:
    result: dict[str, list[RouteCaseSpec]] = {}
    for spec in specs:
        tool, _, _ = spec.route_id.partition(".")
        result.setdefault(tool, []).append(spec)
    return result


def _normalized_supported_action(surface_action: str) -> str:
    return "read" if surface_action in {"read", "retrieve", "search", "list"} else surface_action


def _near_rows(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_tool_specs(specs).items()):
        supported_actions = {
            _normalized_supported_action(spec.surface_action)
            for spec in tool_specs
        }
        unsupported_actions = [
            action
            for action in _UNSUPPORTED_POOL
            if action not in supported_actions
        ][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            # Use the same domain/resource identity while changing only the requested operation.
            obj = anchor.object_terms[language]
            for action_index, action in enumerate(unsupported_actions, start=1):
                for phrase_index, template in enumerate(
                    _SURFACE_ACTIONS[action][language],
                    start=1,
                ):
                    query = template.format(obj=obj)
                    rows.append(
                        {
                            "id": (
                                f"{prefix}-near-{tool}-{language}-"
                                f"{action_index}-{phrase_index}"
                            ),
                            "query": query,
                            "expected": None,
                            "category": "near_domain_unsupported_operation",
                            "language": language,
                            "unsupported_action": action,
                            "unsupported_family": f"{tool}.{action}",
                        }
                    )
    return rows


def _ood_rows(prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for language in LANGUAGES:
        for index, query in enumerate(_OOD[language], start=1):
            rows.append(
                {
                    "id": f"{prefix}-ood-{language}-{index}",
                    "query": query,
                    "expected": None,
                    "category": "out_of_domain",
                    "language": language,
                }
            )
    return rows


def build_rows(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v5-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5-confirm"
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected_routes = {spec.route_id for spec in specs}
    if expected_routes != set(contracts):
        missing = sorted(expected_routes - set(contracts))
        extra = sorted(set(contracts) - expected_routes)
        raise ValueError(f"route fixture mismatch: missing={missing}, extra={extra}")

    rows = [
        *_supported_rows(specs, prefix),
        *_near_rows(specs, prefix),
        *_ood_rows(prefix),
    ]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate generated case IDs")

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    adapters = sorted(
        {
            contract.adapter or "native"
            for contract in contracts.values()
        }
    )
    endpoint_counts = sorted(
        len(tool.endpoints)
        for tool in registry.tools()
    )
    manifest = {
        "role": role,
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "route_count": len(contracts),
        "tool_count": len(registry.tools()),
        "endpoint_counts": endpoint_counts,
        "languages": list(LANGUAGES),
        "adapters": adapters,
        "corpus_sha256": hashlib.sha256(_canonical_bytes(rows)).hexdigest(),
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    combined: dict[str, Any] = {}
    for role in ("development", "confirmation"):
        rows, manifest = build_rows(role)
        (args.out_dir / f"{role}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (args.out_dir / f"{role}-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        combined[role] = manifest

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(combined, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
