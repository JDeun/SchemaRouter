# ruff: noqa: E501
"""Generate disjoint V6A corpora for schema-derived ADB experiment #384."""

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

from benchmarks.operation_routing_v6a_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("hunt through {obj} for matches", "see which {obj} fit the request"),
        "ko": ("{obj} 중 맞는 것 찾아봐", "요청에 맞는 {obj} 골라 찾아줘"),
        "es": ("revisa {obj} para hallar coincidencias", "averigua qué {obj} encajan"),
        "ja": ("{obj}から一致するものを探して", "条件に合う{obj}を見つけて"),
        "de": ("durchsuche {obj} nach Treffern", "finde heraus welche {obj} passen"),
        "mixed": ("{obj} 중 matching한 것 찾아줘", "which {obj} fit인지 찾아줘"),
    },
    "retrieve": {
        "en": ("pull up {obj}", "open the details for {obj}"),
        "ko": ("{obj} 불러와줘", "{obj} 상세 열어줘"),
        "es": ("abre {obj}", "muestra los detalles de {obj}"),
        "ja": ("{obj}を呼び出して", "{obj}の詳細を開いて"),
        "de": ("ruf {obj} auf", "öffne die Details von {obj}"),
        "mixed": ("{obj} pull up해줘", "{obj} details 열어줘"),
    },
    "list": {
        "en": ("show everything in {obj}", "give me the full roster of {obj}"),
        "ko": ("{obj} 전부 보여줘", "{obj} 전체 목록 줘"),
        "es": ("muestra todo en {obj}", "dame la lista completa de {obj}"),
        "ja": ("{obj}を全部見せて", "{obj}の全一覧を出して"),
        "de": ("zeige alles in {obj}", "gib mir die vollständige Liste der {obj}"),
        "mixed": ("{obj} 전부 show해줘", "full roster of {obj} 줘"),
    },
    "create": {
        "en": ("set up {obj} from scratch", "add a fresh {obj}"),
        "ko": ("{obj} 새로 만들어줘", "새 {obj} 추가해줘"),
        "es": ("crea {obj} desde cero", "añade un {obj} nuevo"),
        "ja": ("{obj}を新しく作って", "新しい{obj}を追加して"),
        "de": ("richte {obj} neu ein", "füge ein neues {obj} hinzu"),
        "mixed": ("{obj} from scratch 만들어줘", "fresh {obj} add해줘"),
    },
    "update": {
        "en": ("revise {obj}", "change what is stored for {obj}"),
        "ko": ("{obj} 고쳐줘", "{obj} 저장 내용 바꿔줘"),
        "es": ("modifica {obj}", "cambia lo guardado de {obj}"),
        "ja": ("{obj}を修正して", "{obj}の保存内容を変えて"),
        "de": ("überarbeite {obj}", "ändere die gespeicherten Angaben von {obj}"),
        "mixed": ("{obj} revise해줘", "{obj} stored 내용 바꿔줘"),
    },
    "delete": {
        "en": ("wipe {obj} out", "get rid of {obj} for good"),
        "ko": ("{obj} 지워버려", "{obj} 완전히 없애줘"),
        "es": ("borra {obj}", "elimina {obj} para siempre"),
        "ja": ("{obj}を消して", "{obj}を完全になくして"),
        "de": ("lösche {obj}", "entferne {obj} endgültig"),
        "mixed": ("{obj} wipe out해줘", "{obj} for good 없애줘"),
    },
    "cancel": {
        "en": ("call off {obj}", "stop {obj} while it is active"),
        "ko": ("{obj} 취소해줘", "진행 중인 {obj} 멈춰줘"),
        "es": ("anula {obj}", "detén {obj} mientras está activo"),
        "ja": ("{obj}を取り消して", "進行中の{obj}を止めて"),
        "de": ("storniere {obj}", "stoppe {obj} solange es aktiv ist"),
        "mixed": ("{obj} call off해줘", "active {obj} 멈춰줘"),
    },
    "refund": {
        "en": ("give the payment back for {obj}", "return the money tied to {obj}"),
        "ko": ("{obj} 결제금 돌려줘", "{obj} 돈 반환해줘"),
        "es": ("devuelve el pago de {obj}", "devuelve el dinero de {obj}"),
        "ja": ("{obj}の支払いを返して", "{obj}のお金を戻して"),
        "de": ("erstatte die Zahlung für {obj}", "gib das Geld für {obj} zurück"),
        "mixed": ("{obj} payment 돌려줘", "{obj} money return해줘"),
    },
    "send": {
        "en": ("forward {obj} onward", "get {obj} delivered"),
        "ko": ("{obj} 전달해줘", "{obj} 보내줘"),
        "es": ("reenvía {obj}", "haz que se entregue {obj}"),
        "ja": ("{obj}を転送して", "{obj}を届けて"),
        "de": ("leite {obj} weiter", "lass {obj} zustellen"),
        "mixed": ("{obj} forward해줘", "{obj} delivered되게 해줘"),
    },
    "share": {
        "en": ("let another user access {obj}", "open {obj} up to someone else"),
        "ko": ("다른 사용자도 {obj} 보게 해줘", "{obj} 접근권 공유해줘"),
        "es": ("permite que otro usuario acceda a {obj}", "abre {obj} a otra persona"),
        "ja": ("別ユーザーにも{obj}を見せて", "{obj}へのアクセスを共有して"),
        "de": ("gib einem anderen Nutzer Zugriff auf {obj}", "öffne {obj} für jemand anderen"),
        "mixed": ("다른 user가 {obj} access하게 해줘", "{obj} access share해줘"),
    },
    "export": {
        "en": ("save {obj} out to a file", "download {obj} as a file"),
        "ko": ("{obj} 파일로 저장해줘", "{obj} 파일로 내려받아줘"),
        "es": ("guarda {obj} en un archivo", "descarga {obj} como archivo"),
        "ja": ("{obj}をファイルに保存して", "{obj}をファイルでダウンロードして"),
        "de": ("speichere {obj} in einer Datei", "lade {obj} als Datei herunter"),
        "mixed": ("{obj} file로 저장해줘", "download {obj} as file"),
    },
    "translate": {
        "en": ("put {obj} into another language", "rewrite {obj} in a different language"),
        "ko": ("{obj} 다른 언어로 바꿔줘", "{obj} 다른 언어로 옮겨줘"),
        "es": ("pasa {obj} a otro idioma", "reescribe {obj} en otro idioma"),
        "ja": ("{obj}を別の言語にして", "{obj}を違う言語に書き換えて"),
        "de": ("übertrage {obj} in eine andere Sprache", "schreibe {obj} in einer anderen Sprache um"),
        "mixed": ("{obj} 다른 language로 바꿔줘", "rewrite {obj} in another language"),
    },
    "summarize": {
        "en": ("boil {obj} down", "give only the essentials of {obj}"),
        "ko": ("{obj} 핵심만 줄여줘", "{obj} 중요한 것만 정리해줘"),
        "es": ("reduce {obj} a lo esencial", "dame solo lo importante de {obj}"),
        "ja": ("{obj}を要点だけにして", "{obj}の重要点だけまとめて"),
        "de": ("kürze {obj} auf das Wesentliche", "gib nur die wichtigsten Punkte von {obj}"),
        "mixed": ("{obj} 핵심만 boil down해줘", "essentials of {obj}만 줘"),
    },
    "compare": {
        "en": ("tell me how {obj} differ", "line {obj} up against each other"),
        "ko": ("{obj} 차이 알려줘", "{obj} 서로 비교해줘"),
        "es": ("dime en qué difieren {obj}", "compara {obj} entre sí"),
        "ja": ("{obj}の違いを教えて", "{obj}を互いに比べて"),
        "de": ("sage mir wie sich {obj} unterscheiden", "vergleiche {obj} miteinander"),
        "mixed": ("{obj} differences 알려줘", "{obj} 서로 compare해줘"),
    },
    "merge": {
        "en": ("roll {obj} into one", "join {obj} together"),
        "ko": ("{obj} 하나로 합쳐줘", "{obj} 서로 붙여줘"),
        "es": ("combina {obj} en uno", "une {obj}"),
        "ja": ("{obj}を一つにまとめて", "{obj}を結合して"),
        "de": ("führe {obj} zu einem zusammen", "verbinde {obj}"),
        "mixed": ("{obj} one으로 합쳐줘", "join {obj} together"),
    },
    "restart": {
        "en": ("cycle {obj}", "bring {obj} back up"),
        "ko": ("{obj} 껐다 켜줘", "{obj} 다시 올려줘"),
        "es": ("reinicia {obj}", "vuelve a levantar {obj}"),
        "ja": ("{obj}を再起動して", "{obj}をもう一度立ち上げて"),
        "de": ("starte {obj} neu", "fahre {obj} wieder hoch"),
        "mixed": ("{obj} cycle해줘", "{obj} 다시 up해줘"),
    },
    "execute": {
        "en": ("fire off {obj}", "kick off {obj}"),
        "ko": ("{obj} 돌려줘", "{obj} 시작해줘"),
        "es": ("lanza {obj}", "pon en marcha {obj}"),
        "ja": ("{obj}を走らせて", "{obj}を開始して"),
        "de": ("stoße {obj} an", "starte {obj}"),
        "mixed": ("{obj} fire off해줘", "{obj} kick off해줘"),
    },
    "forecast": {
        "en": ("tell me what {obj} will look like later", "project where {obj} is headed"),
        "ko": ("앞으로 {obj} 어떻게 될지 알려줘", "{obj} 향후 추세 전망해줘"),
        "es": ("dime cómo será {obj} más adelante", "proyecta hacia dónde va {obj}"),
        "ja": ("今後の{obj}がどうなるか教えて", "{obj}の先行きを予測して"),
        "de": ("sag mir wie {obj} später aussehen wird", "projiziere wohin sich {obj} entwickelt"),
        "mixed": ("later {obj} 어떻게 될지 알려줘", "where {obj} is headed 전망해줘"),
    },
}

TEMPORAL = {
    "current": {"en":"at this moment","ko":"현재 시점의","es":"en este momento","ja":"現時点の","de":"im Moment","mixed":"현재 moment의"},
    "future": {"en":"later on","ko":"앞으로의","es":"más adelante","ja":"今後の","de":"später","mixed":"later"},
    "historical": {"en":"from earlier periods","ko":"이전 기간의","es":"de períodos anteriores","ja":"以前の期間の","de":"aus früheren Zeiträumen","mixed":"earlier period의"},
}

ALL_TOOL_LEAVES = tuple(SURFACES)

OOD = {
    "en": (
        "write a poem about fog","invent a space adventure","explain why metal expands when heated",
        "explain photosynthesis","calculate 225 divided by 15","solve 61 plus 18",
        "tell me a tongue twister","give me a cheerful greeting","compose a short bass line","write a tiny legend",
        "calculate the square root of 121","explain DNA replication",
    ),
    "ko": (
        "안개에 대한 시 써줘","우주 모험 이야기를 지어줘","금속이 가열되면 팽창하는 이유 설명해줘",
        "광합성 설명해줘","225 나누기 15 계산해줘","61 더하기 18 풀어줘",
        "잰말놀이 하나 해줘","밝게 인사해줘","짧은 베이스라인 작곡해줘","작은 전설 써줘",
        "121의 제곱근 계산해줘","DNA 복제를 설명해줘",
    ),
    "es": (
        "escribe un poema sobre la niebla","inventa una aventura espacial","explica por qué el metal se expande al calentarse",
        "explica la fotosíntesis","calcula 225 dividido entre 15","resuelve 61 más 18",
        "dime un trabalenguas","dame un saludo alegre","compón una línea corta de bajo","escribe una pequeña leyenda",
        "calcula la raíz cuadrada de 121","explica la replicación del ADN",
    ),
    "ja": (
        "霧について詩を書いて","宇宙冒険の物語を作って","金属が加熱で膨張する理由を説明して",
        "光合成を説明して","225割る15を計算して","61足す18を解いて",
        "早口言葉を言って","明るく挨拶して","短いベースラインを作曲して","小さな伝説を書いて",
        "121の平方根を計算して","DNA複製を説明して",
    ),
    "de": (
        "schreibe ein gedicht über nebel","erfinde ein weltraumabenteuer","erkläre warum sich metall beim erhitzen ausdehnt",
        "erkläre photosynthese","berechne 225 geteilt durch 15","löse 61 plus 18",
        "sag einen zungenbrecher","begrüße mich fröhlich","komponiere eine kurze basslinie","schreibe eine kleine legende",
        "berechne die quadratwurzel aus 121","erkläre DNA-replikation",
    ),
    "mixed": (
        "fog에 대한 poem 써줘","space adventure 지어줘","metal이 heated될 때 expand하는 이유 explain해줘",
        "photosynthesis 설명해줘","225 divided by 15 계산해줘","61 plus 18 풀어줘",
        "tongue twister 하나 해줘","cheerful greeting 해줘","short bass line 작곡해줘","tiny legend 써줘",
        "121 square root 계산해줘","DNA replication 설명해줘",
    ),
}


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _object(spec: RouteCaseSpec, language: str) -> str:
    obj = spec.objects[language]
    if spec.temporal_scope:
        return f"{TEMPORAL[spec.temporal_scope][language]} {obj}"
    return obj


def _supported(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for index, template in enumerate(SURFACES[spec.leaf][language], start=1):
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
        supported = {spec.leaf for spec in tool_specs}
        absent = [leaf for leaf in ALL_TOOL_LEAVES if leaf not in supported][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, leaf in enumerate(absent, start=1):
                template = SURFACES[leaf][language][index % 2]
                rows.append({
                    "id": f"{prefix}-near-{tool}-{language}-{index}",
                    "query": template.format(obj=obj),
                    "expected": None,
                    "category": "near_domain_unsupported_operation",
                    "language": language,
                    "unsupported_action": leaf,
                    "unsupported_family": f"{tool}.{leaf}",
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
        prefix = "v6a-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6a-confirm"
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(
            f"route fixture mismatch missing={sorted(expected-set(contracts))} "
            f"extra={sorted(set(contracts)-expected)}"
        )
    unknown = sorted(route for route, contract in contracts.items() if contract.leaf is None)
    if unknown:
        raise ValueError(f"evaluation endpoint leaves must be known before freeze: {unknown}")
    if any(len(contract.synthetic_positives) != 18 for contract in contracts.values()):
        raise ValueError("every V6A route must compile exactly 18 synthetic positives")

    rows = [*_supported(specs, prefix), *_near(specs, prefix), *_ood(prefix)]
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
        "synthetic_positives_per_route": 18,
        "evaluation_wording_bank":"V6A-only, distinct from schema_adb_baseline.ACTION_PHRASES",
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
