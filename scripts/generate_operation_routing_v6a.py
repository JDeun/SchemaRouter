# ruff: noqa: E501
"""Generate disjoint 0.13-A corpora for schema-derived ADB experiment #383."""

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
from benchmarks.schema_derived_adb import (  # noqa: E402
    ADB_MIN_VIEWS,
    compile_registry_contracts,
    schema_positive_views,
)

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("scan {obj} for matching entries", "look through {obj} using criteria"),
        "ko": ("조건으로 {obj} 훑어서 찾아줘", "{obj}에서 조건에 맞는 항목 찾아줘"),
        "es": ("revisa {obj} para hallar coincidencias", "busca en {obj} usando criterios"),
        "ja": ("条件で{obj}を調べて一致するものを探して", "{obj}を条件検索して"),
        "de": ("durchsuche {obj} nach passenden Einträgen", "suche in {obj} anhand von Kriterien"),
        "mixed": ("criteria로 {obj} scan해서 찾아줘", "{obj}에서 matching entries 찾아줘"),
    },
    "retrieve": {
        "en": ("bring up {obj}", "load the stored record for {obj}"),
        "ko": ("{obj} 불러와줘", "{obj} 저장 기록 열어줘"),
        "es": ("abre {obj}", "carga el registro guardado de {obj}"),
        "ja": ("{obj}を呼び出して", "{obj}の保存記録を開いて"),
        "de": ("ruf {obj} auf", "lade den gespeicherten Datensatz für {obj}"),
        "mixed": ("{obj} 불러와줘", "load stored record for {obj}"),
    },
    "list": {
        "en": ("enumerate the available {obj}", "show every {obj} in the collection"),
        "ko": ("사용 가능한 {obj} 전부 나열해줘", "컬렉션의 {obj} 모두 보여줘"),
        "es": ("enumera los {obj} disponibles", "muestra todos los {obj} de la colección"),
        "ja": ("利用可能な{obj}を列挙して", "コレクション内の{obj}を全部見せて"),
        "de": ("liste die verfügbaren {obj} auf", "zeige alle {obj} in der Sammlung"),
        "mixed": ("available {obj} 전부 나열해줘", "collection의 {obj} 모두 보여줘"),
    },
    "create": {
        "en": ("open a new {obj}", "set up a fresh {obj}"),
        "ko": ("새 {obj} 열어줘", "신규 {obj} 만들어줘"),
        "es": ("abre un nuevo {obj}", "configura un {obj} nuevo"),
        "ja": ("新しい{obj}を作って", "新規{obj}を設定して"),
        "de": ("lege ein neues {obj} an", "richte ein frisches {obj} ein"),
        "mixed": ("new {obj} 열어줘", "fresh {obj} 만들어줘"),
    },
    "update": {
        "en": ("revise the stored details of {obj}", "modify {obj} without replacing it"),
        "ko": ("{obj} 저장 정보 고쳐줘", "{obj} 유지하면서 수정해줘"),
        "es": ("revisa los datos guardados de {obj}", "modifica {obj} sin reemplazarlo"),
        "ja": ("{obj}の保存情報を修正して", "{obj}を残したまま変更して"),
        "de": ("überarbeite die gespeicherten Angaben von {obj}", "ändere {obj} ohne es zu ersetzen"),
        "mixed": ("{obj} stored details 고쳐줘", "{obj} 유지하면서 modify해줘"),
    },
    "delete": {
        "en": ("erase {obj} from storage", "remove {obj} permanently"),
        "ko": ("{obj} 저장소에서 지워줘", "{obj} 영구 제거해줘"),
        "es": ("borra {obj} del almacenamiento", "elimina {obj} permanentemente"),
        "ja": ("{obj}を保存領域から消して", "{obj}を永久に削除して"),
        "de": ("lösche {obj} aus dem Speicher", "entferne {obj} dauerhaft"),
        "mixed": ("{obj} storage에서 지워줘", "{obj} permanently remove해줘"),
    },
    "cancel": {
        "en": ("stop the ongoing {obj}", "withdraw the active {obj}"),
        "ko": ("진행 중인 {obj} 멈춰줘", "활성 {obj} 철회해줘"),
        "es": ("detén el {obj} en curso", "retira el {obj} activo"),
        "ja": ("進行中の{obj}を止めて", "有効な{obj}を取り消して"),
        "de": ("stoppe das laufende {obj}", "ziehe das aktive {obj} zurück"),
        "mixed": ("ongoing {obj} 멈춰줘", "active {obj} withdraw해줘"),
    },
    "refund": {
        "en": ("return the payment for {obj}", "send the money back for {obj}"),
        "ko": ("{obj} 결제금 돌려줘", "{obj} 돈 환불해줘"),
        "es": ("devuelve el pago de {obj}", "reembolsa el dinero de {obj}"),
        "ja": ("{obj}の支払いを返して", "{obj}のお金を払い戻して"),
        "de": ("erstatte die Zahlung für {obj}", "zahle das Geld für {obj} zurück"),
        "mixed": ("{obj} payment 돌려줘", "{obj} money refund해줘"),
    },
    "send": {
        "en": ("route {obj} to its destination", "deliver {obj} onward"),
        "ko": ("{obj} 목적지로 보내줘", "{obj} 전달해줘"),
        "es": ("envía {obj} a su destino", "entrega {obj}"),
        "ja": ("{obj}を宛先へ送って", "{obj}を届けて"),
        "de": ("sende {obj} an sein Ziel", "stelle {obj} zu"),
        "mixed": ("{obj} destination으로 보내줘", "deliver {obj}"),
    },
    "share": {
        "en": ("grant someone access to {obj}", "let another user access {obj}"),
        "ko": ("다른 사람에게 {obj} 접근권 줘", "다른 사용자가 {obj} 볼 수 있게 해줘"),
        "es": ("concede acceso a {obj}", "permite a otro usuario acceder a {obj}"),
        "ja": ("他の人に{obj}へのアクセスを与えて", "別ユーザーが{obj}にアクセスできるようにして"),
        "de": ("gewähre jemandem Zugriff auf {obj}", "erlaube einem anderen Nutzer Zugriff auf {obj}"),
        "mixed": ("다른 user에게 {obj} access 줘", "another user가 {obj} access하게 해줘"),
    },
    "export": {
        "en": ("write {obj} out to a file", "produce a downloadable file for {obj}"),
        "ko": ("{obj} 파일로 써내줘", "{obj} 다운로드 파일 만들어줘"),
        "es": ("guarda {obj} en un archivo", "genera un archivo descargable de {obj}"),
        "ja": ("{obj}をファイルに書き出して", "{obj}のダウンロード可能なファイルを作って"),
        "de": ("schreibe {obj} in eine Datei", "erstelle eine herunterladbare Datei für {obj}"),
        "mixed": ("{obj} file로 써내줘", "downloadable file for {obj} 만들어줘"),
    },
    "translate": {
        "en": ("convert the language of {obj}", "render {obj} in a different language"),
        "ko": ("{obj} 언어 바꿔줘", "{obj} 다른 언어로 옮겨줘"),
        "es": ("cambia el idioma de {obj}", "pasa {obj} a otro idioma"),
        "ja": ("{obj}の言語を変えて", "{obj}を別の言語にして"),
        "de": ("ändere die Sprache von {obj}", "übertrage {obj} in eine andere Sprache"),
        "mixed": ("{obj} language 바꿔줘", "{obj} different language로 옮겨줘"),
    },
    "summarize": {
        "en": ("reduce {obj} to its key points", "give a compact summary of {obj}"),
        "ko": ("{obj} 핵심만 줄여줘", "{obj} 간단히 요약해줘"),
        "es": ("reduce {obj} a sus puntos clave", "da un resumen compacto de {obj}"),
        "ja": ("{obj}を要点だけにまとめて", "{obj}を簡潔に要約して"),
        "de": ("reduziere {obj} auf die Kernaussagen", "gib eine kompakte Zusammenfassung von {obj}"),
        "mixed": ("{obj} key points만 줄여줘", "compact summary of {obj} 줘"),
    },
    "compare": {
        "en": ("contrast {obj}", "show how {obj} differ"),
        "ko": ("{obj} 대조해줘", "{obj} 어떻게 다른지 보여줘"),
        "es": ("contrasta {obj}", "muestra en qué difieren {obj}"),
        "ja": ("{obj}を対比して", "{obj}がどう違うか見せて"),
        "de": ("stelle {obj} gegenüber", "zeige wie sich {obj} unterscheiden"),
        "mixed": ("{obj} contrast해줘", "{obj} 어떻게 differ하는지 보여줘"),
    },
    "merge": {
        "en": ("fold {obj} into one result", "combine {obj} as a single item"),
        "ko": ("{obj} 하나의 결과로 합쳐줘", "{obj} 하나로 결합해줘"),
        "es": ("integra {obj} en un solo resultado", "combina {obj} en un único elemento"),
        "ja": ("{obj}を一つの結果にまとめて", "{obj}を一つの項目に結合して"),
        "de": ("führe {obj} zu einem Ergebnis zusammen", "kombiniere {obj} zu einem Element"),
        "mixed": ("{obj} one result로 합쳐줘", "{obj} single item으로 combine해줘"),
    },
    "restart": {
        "en": ("cycle {obj} and bring it back", "restart {obj} from its current state"),
        "ko": ("{obj} 껐다 다시 올려줘", "{obj} 현재 상태에서 재시작해줘"),
        "es": ("reinicia {obj} y vuelve a levantarlo", "reinicia {obj} desde su estado actual"),
        "ja": ("{obj}を再起動して戻して", "{obj}を現在の状態から再始動して"),
        "de": ("starte {obj} neu und bringe es zurück", "starte {obj} aus dem aktuellen Zustand neu"),
        "mixed": ("{obj} cycle해서 다시 올려줘", "{obj} current state에서 restart해줘"),
    },
    "execute": {
        "en": ("invoke the registered {obj}", "start the executable {obj}"),
        "ko": ("등록된 {obj} 호출해줘", "실행 가능한 {obj} 시작해줘"),
        "es": ("invoca el {obj} registrado", "inicia el {obj} ejecutable"),
        "ja": ("登録済みの{obj}を呼び出して", "実行可能な{obj}を開始して"),
        "de": ("rufe das registrierte {obj} auf", "starte das ausführbare {obj}"),
        "mixed": ("registered {obj} invoke해줘", "executable {obj} 시작해줘"),
    },
    "forecast": {
        "en": ("project future {obj}", "estimate what {obj} will become"),
        "ko": ("향후 {obj} 전망해줘", "앞으로 {obj} 어떻게 될지 추정해줘"),
        "es": ("proyecta {obj} futuro", "estima en qué se convertirá {obj}"),
        "ja": ("将来の{obj}を予測して", "{obj}が今後どうなるか見積もって"),
        "de": ("projiziere zukünftige {obj}", "schätze wie sich {obj} entwickeln wird"),
        "mixed": ("future {obj} project해줘", "{obj} 앞으로 어떻게 될지 estimate해줘"),
    },
}

TEMPORAL = {
    "current": {"en":"right now","ko":"현재","es":"ahora","ja":"現在の","de":"aktuell","mixed":"현재"},
    "future": {"en":"in the next period","ko":"향후","es":"en el próximo período","ja":"今後の","de":"im nächsten Zeitraum","mixed":"future"},
    "historical": {"en":"from previous records","ko":"과거","es":"de registros previos","ja":"過去の","de":"aus früheren Datensätzen","mixed":"historical"},
}

ALL_TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en": (
        "write a short ode to spring","invent a scene about a lost astronaut","explain why metals conduct electricity",
        "explain how tides work","calculate 225 divided by 15","solve 58 plus 37",
        "tell a dry joke","greet me like an old friend","compose a short bass groove","write a miniature legend",
        "calculate the fifth root of 32","explain DNA replication",
    ),
    "ko": (
        "봄에 대한 짧은 송가 써줘","길 잃은 우주비행사 장면 지어줘","금속이 전기를 통하는 이유 설명해줘",
        "조수가 생기는 원리 설명해줘","225 나누기 15 계산해줘","58 더하기 37 풀어줘",
        "썰렁한 농담 하나 해줘","오랜 친구처럼 인사해줘","짧은 베이스 그루브 작곡해줘","작은 전설 써줘",
        "32의 다섯제곱근 계산해줘","DNA 복제를 설명해줘",
    ),
    "es": (
        "escribe una oda corta a la primavera","inventa una escena sobre un astronauta perdido","explica por qué los metales conducen electricidad",
        "explica cómo funcionan las mareas","calcula 225 dividido entre 15","resuelve 58 más 37",
        "cuéntame un chiste seco","salúdame como a un viejo amigo","compón un groove corto de bajo","escribe una leyenda diminuta",
        "calcula la quinta raíz de 32","explica la replicación del ADN",
    ),
    "ja": (
        "春について短い頌歌を書いて","迷子の宇宙飛行士の場面を作って","金属が電気を通す理由を説明して",
        "潮汐の仕組みを説明して","225割る15を計算して","58足す37を解いて",
        "寒い冗談を言って","古い友人のように挨拶して","短いベースグルーブを作曲して","小さな伝説を書いて",
        "32の5乗根を計算して","DNA複製を説明して",
    ),
    "de": (
        "schreibe eine kurze ode an den frühling","erfinde eine szene über einen verlorenen astronauten","erkläre warum metalle strom leiten",
        "erkläre wie gezeiten funktionieren","berechne 225 geteilt durch 15","löse 58 plus 37",
        "erzähl einen trockenen witz","begrüße mich wie einen alten freund","komponiere einen kurzen bass-groove","schreibe eine winzige legende",
        "berechne die fünfte wurzel aus 32","erkläre DNA-replikation",
    ),
    "mixed": (
        "spring에 대한 short ode 써줘","lost astronaut scene 지어줘","metals가 electricity 통하는 이유 explain해줘",
        "tides 작동 원리 explain해줘","225 divided by 15 계산해줘","58 plus 37 풀어줘",
        "dry joke 하나 해줘","old friend처럼 greet해줘","short bass groove 작곡해줘","miniature legend 써줘",
        "32 fifth root 계산해줘","DNA replication 설명해줘",
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
        unsupported = [
            leaf
            for leaf in ALL_TOOL_LEAVES
            if leaf not in supported
        ][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, leaf in enumerate(unsupported, start=1):
                template = SURFACES[leaf][language][(index + 1) % 2]
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


def _boundary_ready(registry: Any) -> tuple[int, int]:
    ready = 0
    total = 0
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            total += 1
            if len(schema_positive_views(tool, endpoint)) >= ADB_MIN_VIEWS:
                ready += 1
    return ready, total


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

    boundary_ready, route_total = _boundary_ready(registry)
    if boundary_ready != route_total:
        raise ValueError(
            f"all evaluation routes must have ADB-ready schema views: "
            f"{boundary_ready}/{route_total}"
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
        "endpoint_counts": sorted(
            len(tool.endpoints)
            for tool in registry.tools()
        ),
        "languages": list(LANGUAGES),
        "adapters": sorted(
            {contract.adapter or "native" for contract in contracts.values()}
        ),
        "adb_ready_routes": boundary_ready,
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
