# ruff: noqa: E501
"""Generate disjoint V5H corpora for pairwise NLI membership experiment #378."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v5h_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.pairwise_nli_membership import compile_registry_contracts  # noqa: E402

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("hunt through {obj} for matches", "locate {obj} that fit the criteria"),
        "ko": ("{obj}에서 맞는 항목 찾아줘", "조건에 부합하는 {obj} 찾아봐"),
        "es": ("busca coincidencias entre {obj}", "localiza {obj} que cumplan los criterios"),
        "ja": ("{obj}から一致するものを探して", "条件に合う{obj}を見つけて"),
        "de": ("durchsuche {obj} nach Treffern", "finde {obj}, die zu den Kriterien passen"),
        "mixed": ("{obj}에서 matches 찾아줘", "criteria 맞는 {obj} locate해줘"),
    },
    "retrieve": {
        "en": ("fetch the saved {obj}", "bring me the existing details for {obj}"),
        "ko": ("저장된 {obj} 가져와줘", "{obj} 기존 상세정보 불러줘"),
        "es": ("recupera el {obj} guardado", "tráeme los detalles existentes de {obj}"),
        "ja": ("保存済みの{obj}を取得して", "{obj}の既存詳細を出して"),
        "de": ("hole das gespeicherte {obj}", "ruf die vorhandenen Details von {obj} ab"),
        "mixed": ("saved {obj} 가져와줘", "existing details for {obj} 불러줘"),
    },
    "list": {
        "en": ("give me every available {obj}", "show the inventory of {obj}"),
        "ko": ("사용 가능한 {obj} 전부 보여줘", "{obj} 전체 목록 보여줘"),
        "es": ("dame todos los {obj} disponibles", "muestra el inventario de {obj}"),
        "ja": ("利用可能な{obj}を全部見せて", "{obj}の一覧を出して"),
        "de": ("zeige mir alle verfügbaren {obj}", "zeige die Liste der {obj}"),
        "mixed": ("available {obj} 전부 보여줘", "{obj} inventory 보여줘"),
    },
    "create": {
        "en": ("start a new {obj}", "register a completely new {obj}"),
        "ko": ("새 {obj} 시작해줘", "신규 {obj} 등록해줘"),
        "es": ("inicia un nuevo {obj}", "registra un {obj} completamente nuevo"),
        "ja": ("新しい{obj}を作って", "新規の{obj}を登録して"),
        "de": ("lege ein neues {obj} an", "registriere ein vollständig neues {obj}"),
        "mixed": ("new {obj} 시작해줘", "신규 {obj} register해줘"),
    },
    "update": {
        "en": ("amend the existing {obj}", "change the stored information for {obj}"),
        "ko": ("기존 {obj} 고쳐줘", "{obj} 저장 정보 변경해줘"),
        "es": ("modifica el {obj} existente", "cambia la información guardada de {obj}"),
        "ja": ("既存の{obj}を修正して", "{obj}の保存情報を変更して"),
        "de": ("ändere das vorhandene {obj}", "ändere die gespeicherten Angaben für {obj}"),
        "mixed": ("existing {obj} 고쳐줘", "{obj} stored info 변경해줘"),
    },
    "delete": {
        "en": ("destroy the stored {obj}", "remove {obj} for good"),
        "ko": ("저장된 {obj} 삭제해줘", "{obj} 완전히 없애줘"),
        "es": ("borra el {obj} guardado", "elimina {obj} definitivamente"),
        "ja": ("保存済みの{obj}を削除して", "{obj}を完全に消して"),
        "de": ("lösche das gespeicherte {obj}", "entferne {obj} endgültig"),
        "mixed": ("stored {obj} 삭제해줘", "{obj} for good remove해줘"),
    },
    "cancel": {
        "en": ("revoke the active {obj}", "halt {obj} before it finishes"),
        "ko": ("진행 중인 {obj} 취소해줘", "{obj} 끝나기 전에 멈춰줘"),
        "es": ("revoca el {obj} activo", "detén {obj} antes de que termine"),
        "ja": ("進行中の{obj}を取り消して", "{obj}を完了前に止めて"),
        "de": ("widerrufe das aktive {obj}", "stoppe {obj} vor dem Ende"),
        "mixed": ("active {obj} revoke해줘", "{obj} 끝나기 전에 stop해줘"),
    },
    "refund": {
        "en": ("reimburse the payment for {obj}", "send the money back for {obj}"),
        "ko": ("{obj} 결제 환급해줘", "{obj} 돈 다시 돌려줘"),
        "es": ("reembolsa el pago de {obj}", "devuelve el dinero de {obj}"),
        "ja": ("{obj}の支払いを返金して", "{obj}のお金を戻して"),
        "de": ("erstatte die Zahlung für {obj}", "zahle das Geld für {obj} zurück"),
        "mixed": ("{obj} payment reimburse해줘", "{obj} money 다시 돌려줘"),
    },
    "send": {
        "en": ("ship {obj} to the destination", "forward {obj} to its target"),
        "ko": ("{obj} 목적지로 보내줘", "{obj} 대상에게 전달해줘"),
        "es": ("envía {obj} al destino", "reenvía {obj} a su objetivo"),
        "ja": ("{obj}を宛先へ送って", "{obj}を対象へ転送して"),
        "de": ("sende {obj} an das Ziel", "leite {obj} an sein Ziel weiter"),
        "mixed": ("{obj} destination으로 보내줘", "{obj} target에 forward해줘"),
    },
    "share": {
        "en": ("let another user access {obj}", "grant shared access to {obj}"),
        "ko": ("다른 사용자가 {obj} 보게 공유해줘", "{obj} 공유 접근권 줘"),
        "es": ("permite a otro usuario acceder a {obj}", "concede acceso compartido a {obj}"),
        "ja": ("別のユーザーが{obj}にアクセスできるようにして", "{obj}への共有アクセスを与えて"),
        "de": ("erlaube einem anderen Nutzer den Zugriff auf {obj}", "gewähre gemeinsamen Zugriff auf {obj}"),
        "mixed": ("다른 user가 {obj} access하게 해줘", "shared access to {obj} 줘"),
    },
    "export": {
        "en": ("write {obj} out to a file", "produce a downloadable file for {obj}"),
        "ko": ("{obj} 파일로 출력해줘", "{obj} 다운로드 파일 만들어줘"),
        "es": ("guarda {obj} en un archivo", "genera un archivo descargable de {obj}"),
        "ja": ("{obj}をファイルに書き出して", "{obj}のダウンロード用ファイルを作って"),
        "de": ("schreibe {obj} in eine Datei", "erzeuge eine herunterladbare Datei für {obj}"),
        "mixed": ("{obj} file로 출력해줘", "downloadable file for {obj} 만들어줘"),
    },
    "translate": {
        "en": ("rewrite {obj} in another language", "convert the language used by {obj}"),
        "ko": ("{obj} 다른 언어로 옮겨줘", "{obj} 사용 언어 바꿔줘"),
        "es": ("reescribe {obj} en otro idioma", "cambia el idioma usado por {obj}"),
        "ja": ("{obj}を別の言語に書き換えて", "{obj}の言語を変えて"),
        "de": ("übertrage {obj} in eine andere Sprache", "ändere die Sprache von {obj}"),
        "mixed": ("{obj} 다른 language로 rewrite해줘", "{obj} language 바꿔줘"),
    },
    "summarize": {
        "en": ("compress {obj} into the essential points", "give a brief digest of {obj}"),
        "ko": ("{obj} 핵심만 압축해줘", "{obj} 짧게 정리해줘"),
        "es": ("condensa {obj} en los puntos esenciales", "dame un resumen breve de {obj}"),
        "ja": ("{obj}を要点だけに圧縮して", "{obj}を短くまとめて"),
        "de": ("verdichte {obj} auf die wesentlichen Punkte", "gib eine kurze Zusammenfassung von {obj}"),
        "mixed": ("{obj} essential points로 압축해줘", "brief digest of {obj} 만들어줘"),
    },
    "compare": {
        "en": ("analyze the differences among {obj}", "contrast {obj} with each other"),
        "ko": ("{obj} 차이 분석해줘", "{obj} 서로 대조해줘"),
        "es": ("analiza las diferencias entre {obj}", "contrasta {obj} entre sí"),
        "ja": ("{obj}の違いを分析して", "{obj}を互いに比較して"),
        "de": ("analysiere die Unterschiede zwischen {obj}", "vergleiche {obj} miteinander"),
        "mixed": ("{obj} differences 분석해줘", "{obj} 서로 contrast해줘"),
    },
    "merge": {
        "en": ("fuse {obj} into one output", "combine {obj} as a single item"),
        "ko": ("{obj} 하나의 출력으로 합쳐줘", "{obj} 단일 항목으로 결합해줘"),
        "es": ("fusiona {obj} en una salida", "combina {obj} como un solo elemento"),
        "ja": ("{obj}を一つの出力に統合して", "{obj}を単一項目として結合して"),
        "de": ("führe {obj} zu einer Ausgabe zusammen", "kombiniere {obj} als ein Element"),
        "mixed": ("{obj} one output으로 합쳐줘", "{obj} single item으로 combine해줘"),
    },
    "restart": {
        "en": ("recycle {obj}", "stop and start {obj} again"),
        "ko": ("{obj} 다시 구동해줘", "{obj} 멈췄다가 다시 시작해줘"),
        "es": ("reinicia {obj}", "detén y vuelve a iniciar {obj}"),
        "ja": ("{obj}を再稼働して", "{obj}を止めてもう一度起動して"),
        "de": ("starte {obj} neu", "stoppe und starte {obj} erneut"),
        "mixed": ("{obj} 다시 구동해줘", "stop and start {obj} again"),
    },
    "execute": {
        "en": ("run the registered {obj}", "invoke {obj} immediately"),
        "ko": ("등록된 {obj} 실행해줘", "{obj} 바로 호출해줘"),
        "es": ("ejecuta el {obj} registrado", "invoca {obj} inmediatamente"),
        "ja": ("登録済みの{obj}を実行して", "{obj}をすぐ呼び出して"),
        "de": ("führe das registrierte {obj} aus", "rufe {obj} sofort auf"),
        "mixed": ("registered {obj} 실행해줘", "{obj} immediately invoke해줘"),
    },
    "forecast": {
        "en": ("project the upcoming {obj}", "predict how {obj} will change"),
        "ko": ("향후 {obj} 전망해줘", "{obj} 어떻게 변할지 예측해줘"),
        "es": ("proyecta el próximo {obj}", "predice cómo cambiará {obj}"),
        "ja": ("今後の{obj}を予測して", "{obj}がどう変わるか予測して"),
        "de": ("prognostiziere die kommenden {obj}", "sage voraus wie sich {obj} ändern wird"),
        "mixed": ("upcoming {obj} 전망해줘", "{obj} change 예측해줘"),
    },
}

TEMPORAL = {
    "current": {"en":"now","ko":"현재","es":"ahora","ja":"現在の","de":"jetzt","mixed":"현재"},
    "future": {"en":"upcoming","ko":"향후","es":"próximo","ja":"今後の","de":"kommend","mixed":"future"},
    "historical": {"en":"previously observed","ko":"과거","es":"observado anteriormente","ja":"過去の","de":"früher beobachtet","mixed":"historical"},
}

ALL_TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en": (
        "write an ode about rain","invent a courtroom scene","explain why copper conducts electricity",
        "explain how clouds form","calculate 324 divided by 18","solve 64 plus 27",
        "tell a sarcastic joke","write a polite greeting","compose a short synth melody","write a tiny folktale",
        "calculate the square root of 529","explain ribosomes",
    ),
    "ko": (
        "비에 대한 송시 써줘","법정 장면 지어줘","구리가 전기를 전도하는 이유 설명해줘",
        "구름이 생기는 원리 설명해줘","324 나누기 18 계산해줘","64 더하기 27 풀어줘",
        "빈정대는 농담 해줘","정중한 인사말 써줘","짧은 신스 멜로디 작곡해줘","작은 민담 써줘",
        "529의 제곱근 계산해줘","리보솜을 설명해줘",
    ),
    "es": (
        "escribe una oda sobre la lluvia","inventa una escena de tribunal","explica por qué el cobre conduce electricidad",
        "explica cómo se forman las nubes","calcula 324 dividido entre 18","resuelve 64 más 27",
        "cuéntame un chiste sarcástico","escribe un saludo educado","compón una melodía corta de sintetizador","escribe un cuento popular pequeño",
        "calcula la raíz cuadrada de 529","explica los ribosomas",
    ),
    "ja": (
        "雨について頌歌を書いて","法廷の場面を作って","銅が電気を通す理由を説明して",
        "雲ができる仕組みを説明して","324割る18を計算して","64足す27を解いて",
        "皮肉な冗談を言って","丁寧な挨拶を書いて","短いシンセメロディーを作曲して","小さな昔話を書いて",
        "529の平方根を計算して","リボソームを説明して",
    ),
    "de": (
        "schreibe eine ode über regen","erfinde eine gerichtsszene","erkläre warum kupfer strom leitet",
        "erkläre wie wolken entstehen","berechne 324 geteilt durch 18","löse 64 plus 27",
        "erzähl einen sarkastischen witz","schreibe eine höfliche begrüßung","komponiere eine kurze synth-melodie","schreibe ein kleines volksmärchen",
        "berechne die quadratwurzel aus 529","erkläre ribosomen",
    ),
    "mixed": (
        "rain에 대한 ode 써줘","courtroom scene 지어줘","copper가 electricity 전도하는 이유 explain해줘",
        "clouds 생기는 원리 explain해줘","324 divided by 18 계산해줘","64 plus 27 풀어줘",
        "sarcastic joke 해줘","polite greeting 써줘","short synth melody 작곡해줘","tiny folktale 써줘",
        "529 square root 계산해줘","ribosomes 설명해줘",
    ),
}


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _object(spec: RouteCaseSpec, language: str) -> str:
    obj = spec.objects[language]
    if spec.temporal_scope:
        return f"{TEMPORAL[spec.temporal_scope][language]} {obj}"
    return obj


def _supported(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for index, template in enumerate(
                SURFACES[spec.leaf][language],
                start=1,
            ):
                rows.append(
                    {
                        "id": f"{prefix}-supported-{slug}-{language}-{index}",
                        "query": template.format(obj=obj),
                        "expected": spec.route_id,
                        "category": "supported",
                        "language": language,
                    }
                )
    return rows


def _by_tool(
    specs: tuple[RouteCaseSpec, ...],
) -> dict[str, list[RouteCaseSpec]]:
    result: dict[str, list[RouteCaseSpec]] = {}
    for spec in specs:
        result.setdefault(spec.route_id.split(".", 1)[0], []).append(spec)
    return result


def _near(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_by_tool(specs).items()):
        supported = {spec.leaf for spec in tool_specs}
        unsupported = [
            leaf
            for leaf in ALL_TOOL_LEAVES
            if leaf not in supported
        ][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, leaf in enumerate(unsupported, start=1):
                template = SURFACES[leaf][language][index % 2]
                rows.append(
                    {
                        "id": f"{prefix}-near-{tool}-{language}-{index}",
                        "query": template.format(obj=obj),
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "language": language,
                        "unsupported_action": leaf,
                        "unsupported_family": f"{tool}.{leaf}",
                    }
                )
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
        prefix = "v5h-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5h-confirm"
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(
            f"route fixture mismatch missing={sorted(expected-set(contracts))} "
            f"extra={sorted(set(contracts)-expected)}"
        )
    unknown = sorted(
        route
        for route, contract in contracts.items()
        if contract.leaf is None
    )
    if unknown:
        raise ValueError(
            f"evaluation endpoint leaves must be known before freeze: {unknown}"
        )

    rows = [*_supported(specs, prefix), *_near(specs, prefix), *_ood(prefix)]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate IDs")

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
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
        "adapters": sorted(
            {contract.adapter or "native" for contract in contracts.values()}
        ),
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
