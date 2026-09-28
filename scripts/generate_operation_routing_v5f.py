# ruff: noqa: E501
"""Generate disjoint 0.12-F corpora for external zero-shot membership experiment #371."""

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

from benchmarks.external_zeroshot_membership import compile_registry_contracts  # noqa: E402
from benchmarks.operation_routing_v5f_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("look for {obj} matching some criteria", "search across {obj} for matches"),
        "ko": ("조건에 맞는 {obj} 찾아봐", "{obj} 중에서 맞는 것 검색해줘"),
        "es": ("busca {obj} que cumplan criterios", "revisa {obj} para encontrar coincidencias"),
        "ja": ("条件に合う{obj}を探して", "{obj}から一致するものを検索して"),
        "de": ("suche passende {obj} nach Kriterien", "durchsuche {obj} nach Treffern"),
        "mixed": ("criteria에 맞는 {obj} 찾아줘", "{obj}에서 matching item search해줘"),
    },
    "retrieve": {
        "en": ("open the existing {obj}", "show the stored details for {obj}"),
        "ko": ("기존 {obj} 열어줘", "{obj} 저장된 상세정보 보여줘"),
        "es": ("abre el {obj} existente", "muestra los detalles guardados de {obj}"),
        "ja": ("既存の{obj}を開いて", "{obj}の保存済み詳細を見せて"),
        "de": ("öffne das vorhandene {obj}", "zeige die gespeicherten Details von {obj}"),
        "mixed": ("existing {obj} 열어줘", "{obj} stored details 보여줘"),
    },
    "list": {
        "en": ("show the complete collection of {obj}", "enumerate every available {obj}"),
        "ko": ("{obj} 전체 컬렉션 보여줘", "사용 가능한 {obj} 모두 나열해줘"),
        "es": ("muestra la colección completa de {obj}", "enumera todos los {obj} disponibles"),
        "ja": ("{obj}の全コレクションを見せて", "利用可能な{obj}を全部列挙して"),
        "de": ("zeige die vollständige Sammlung der {obj}", "zähle alle verfügbaren {obj} auf"),
        "mixed": ("{obj} complete collection 보여줘", "available {obj} 전부 list해줘"),
    },
    "create": {
        "en": ("make a new {obj}", "register a fresh {obj}"),
        "ko": ("새 {obj} 만들어줘", "신규 {obj} 등록해줘"),
        "es": ("crea un {obj} nuevo", "registra un {obj} nuevo"),
        "ja": ("新しい{obj}を作って", "新規{obj}を登録して"),
        "de": ("lege ein neues {obj} an", "registriere ein frisches {obj}"),
        "mixed": ("new {obj} 만들어줘", "fresh {obj} register해줘"),
    },
    "update": {
        "en": ("change the stored fields of {obj}", "edit the existing {obj}"),
        "ko": ("{obj} 저장 필드 바꿔줘", "기존 {obj} 편집해줘"),
        "es": ("cambia los campos guardados de {obj}", "edita el {obj} existente"),
        "ja": ("{obj}の保存フィールドを変更して", "既存の{obj}を編集して"),
        "de": ("ändere die gespeicherten Felder von {obj}", "bearbeite das vorhandene {obj}"),
        "mixed": ("{obj} stored fields 바꿔줘", "existing {obj} edit해줘"),
    },
    "delete": {
        "en": ("remove {obj} permanently", "erase the stored {obj}"),
        "ko": ("{obj} 영구 제거해줘", "저장된 {obj} 지워줘"),
        "es": ("elimina {obj} permanentemente", "borra el {obj} guardado"),
        "ja": ("{obj}を永久に削除して", "保存済みの{obj}を消して"),
        "de": ("entferne {obj} dauerhaft", "lösche das gespeicherte {obj}"),
        "mixed": ("{obj} permanently remove해줘", "stored {obj} 지워줘"),
    },
    "cancel": {
        "en": ("stop the active {obj}", "call off {obj}"),
        "ko": ("진행 중인 {obj} 멈춰줘", "{obj} 취소해줘"),
        "es": ("detén el {obj} activo", "anula {obj}"),
        "ja": ("進行中の{obj}を止めて", "{obj}を取り消して"),
        "de": ("stoppe das aktive {obj}", "storniere {obj}"),
        "mixed": ("active {obj} 멈춰줘", "cancel {obj}"),
    },
    "refund": {
        "en": ("return the money paid for {obj}", "issue a reimbursement for {obj}"),
        "ko": ("{obj}에 낸 돈 돌려줘", "{obj} 환급 처리해줘"),
        "es": ("devuelve el dinero pagado por {obj}", "tramita un reembolso de {obj}"),
        "ja": ("{obj}に支払ったお金を返して", "{obj}を払い戻して"),
        "de": ("zahle das Geld für {obj} zurück", "erstatte {obj}"),
        "mixed": ("{obj} paid money 돌려줘", "reimburse {obj}"),
    },
    "send": {
        "en": ("deliver {obj} to the destination", "forward {obj}"),
        "ko": ("{obj} 목적지에 전달해줘", "{obj} 전달해줘"),
        "es": ("entrega {obj} al destino", "reenvía {obj}"),
        "ja": ("{obj}を宛先へ届けて", "{obj}を転送して"),
        "de": ("liefere {obj} an das Ziel", "leite {obj} weiter"),
        "mixed": ("{obj} destination에 전달해줘", "forward {obj}"),
    },
    "share": {
        "en": ("give another user access to {obj}", "make {obj} accessible to someone else"),
        "ko": ("다른 사용자에게 {obj} 접근권 줘", "{obj}를 다른 사람과 공유해줘"),
        "es": ("da acceso a {obj} a otro usuario", "haz {obj} accesible a otra persona"),
        "ja": ("別ユーザーに{obj}へのアクセスを与えて", "{obj}を他の人と共有して"),
        "de": ("gib einem anderen Nutzer Zugriff auf {obj}", "mache {obj} für jemand anderen zugänglich"),
        "mixed": ("다른 user에게 {obj} access 줘", "{obj} 다른 사람과 share해줘"),
    },
    "export": {
        "en": ("save {obj} out as a file", "download an external file for {obj}"),
        "ko": ("{obj} 파일로 내보내줘", "{obj} 외부 파일로 내려받아줘"),
        "es": ("guarda {obj} como archivo", "descarga un archivo externo de {obj}"),
        "ja": ("{obj}をファイルとして出力して", "{obj}の外部ファイルをダウンロードして"),
        "de": ("speichere {obj} als Datei", "lade eine externe Datei für {obj} herunter"),
        "mixed": ("{obj} file로 내보내줘", "download external file for {obj}"),
    },
    "translate": {
        "en": ("render {obj} in another language", "change the language of {obj}"),
        "ko": ("{obj} 다른 언어로 옮겨줘", "{obj} 언어 바꿔줘"),
        "es": ("pasa {obj} a otro idioma", "cambia el idioma de {obj}"),
        "ja": ("{obj}を別の言語にして", "{obj}の言語を変えて"),
        "de": ("übertrage {obj} in eine andere Sprache", "ändere die Sprache von {obj}"),
        "mixed": ("{obj} 다른 language로 옮겨줘", "change language of {obj}"),
    },
    "summarize": {
        "en": ("condense {obj} to the main points", "make a short summary of {obj}"),
        "ko": ("{obj} 핵심만 줄여줘", "{obj} 짧은 요약 만들어줘"),
        "es": ("condensa {obj} a los puntos principales", "haz un resumen corto de {obj}"),
        "ja": ("{obj}を要点だけに縮めて", "{obj}の短い要約を作って"),
        "de": ("verdichte {obj} auf die Kernaussagen", "erstelle eine kurze Zusammenfassung von {obj}"),
        "mixed": ("{obj} main points만 줄여줘", "short summary of {obj} 만들어줘"),
    },
    "compare": {
        "en": ("identify the differences between {obj}", "put {obj} side by side"),
        "ko": ("{obj} 차이점 찾아줘", "{obj} 나란히 비교해줘"),
        "es": ("identifica las diferencias entre {obj}", "pon {obj} lado a lado"),
        "ja": ("{obj}の違いを見つけて", "{obj}を並べて比べて"),
        "de": ("finde die Unterschiede zwischen {obj}", "stelle {obj} gegenüber"),
        "mixed": ("{obj} differences 찾아줘", "compare {obj} side by side"),
    },
    "merge": {
        "en": ("join {obj} into one result", "combine {obj} together"),
        "ko": ("{obj} 하나의 결과로 합쳐줘", "{obj} 결합해줘"),
        "es": ("une {obj} en un solo resultado", "combina {obj}"),
        "ja": ("{obj}を一つの結果にまとめて", "{obj}を結合して"),
        "de": ("führe {obj} zu einem Ergebnis zusammen", "kombiniere {obj}"),
        "mixed": ("{obj} one result로 합쳐줘", "combine {obj}"),
    },
    "restart": {
        "en": ("bring {obj} back up from a restart", "reboot {obj}"),
        "ko": ("{obj} 재시작해서 다시 올려줘", "{obj} 재부팅해줘"),
        "es": ("reinicia {obj} y vuelve a levantarlo", "reinicia {obj}"),
        "ja": ("{obj}を再起動して戻して", "{obj}をリブートして"),
        "de": ("starte {obj} neu und fahre es wieder hoch", "reboote {obj}"),
        "mixed": ("{obj} restart해서 다시 올려줘", "reboot {obj}"),
    },
    "execute": {
        "en": ("launch the registered {obj}", "run {obj} now"),
        "ko": ("등록된 {obj} 시작해줘", "{obj} 지금 실행해줘"),
        "es": ("lanza el {obj} registrado", "ejecuta {obj} ahora"),
        "ja": ("登録済みの{obj}を起動して", "{obj}を今実行して"),
        "de": ("starte das registrierte {obj}", "führe {obj} jetzt aus"),
        "mixed": ("registered {obj} launch해줘", "run {obj} now"),
    },
    "forecast": {
        "en": ("estimate future {obj}", "project what {obj} will be later"),
        "ko": ("향후 {obj} 추정해줘", "앞으로 {obj} 어떻게 될지 전망해줘"),
        "es": ("estima {obj} futuro", "proyecta cómo será {obj} más adelante"),
        "ja": ("将来の{obj}を見積もって", "今後の{obj}を予測して"),
        "de": ("schätze zukünftige {obj}", "projiziere wie {obj} später sein wird"),
        "mixed": ("future {obj} estimate해줘", "project later {obj}"),
    },
}

TEMPORAL = {
    "current": {"en":"right now","ko":"현재","es":"ahora","ja":"現在の","de":"aktuell","mixed":"현재"},
    "future": {"en":"for the future","ko":"향후","es":"para el futuro","ja":"将来の","de":"zukünftig","mixed":"future"},
    "historical": {"en":"from earlier records","ko":"과거","es":"de registros anteriores","ja":"過去の","de":"aus früheren Aufzeichnungen","mixed":"historical"},
}

ALL_TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en": (
        "write a ballad about a mountain","invent a mystery scene","explain why salt dissolves in water",
        "explain how eclipses happen","calculate 196 divided by 14","solve 43 plus 29",
        "tell a one-line joke","give me a warm greeting","compose a short drum groove","write a tiny myth",
        "calculate the cube root of 64","explain protein synthesis",
    ),
    "ko": (
        "산에 대한 발라드 써줘","미스터리 장면 지어줘","소금이 물에 녹는 이유 설명해줘",
        "일식이 생기는 원리 설명해줘","196 나누기 14 계산해줘","43 더하기 29 풀어줘",
        "한 줄 농담 해줘","따뜻하게 인사해줘","짧은 드럼 그루브 작곡해줘","작은 신화 써줘",
        "64의 세제곱근 계산해줘","단백질 합성을 설명해줘",
    ),
    "es": (
        "escribe una balada sobre una montaña","inventa una escena de misterio","explica por qué la sal se disuelve en agua",
        "explica cómo ocurren los eclipses","calcula 196 dividido entre 14","resuelve 43 más 29",
        "cuéntame un chiste de una línea","dame un saludo cálido","compón un ritmo corto de batería","escribe un mito pequeño",
        "calcula la raíz cúbica de 64","explica la síntesis de proteínas",
    ),
    "ja": (
        "山についてバラードを書いて","ミステリーの場面を作って","塩が水に溶ける理由を説明して",
        "日食が起こる仕組みを説明して","196割る14を計算して","43足す29を解いて",
        "一行の冗談を言って","温かく挨拶して","短いドラムグルーブを作曲して","小さな神話を書いて",
        "64の立方根を計算して","タンパク質合成を説明して",
    ),
    "de": (
        "schreibe eine ballade über einen berg","erfinde eine mysterieszene","erkläre warum sich salz in wasser löst",
        "erkläre wie sonnenfinsternisse entstehen","berechne 196 geteilt durch 14","löse 43 plus 29",
        "erzähl einen einzeiligen witz","begrüße mich herzlich","komponiere einen kurzen drum-groove","schreibe einen kleinen mythos",
        "berechne die kubikwurzel aus 64","erkläre proteinsynthese",
    ),
    "mixed": (
        "mountain에 대한 ballad 써줘","mystery scene 지어줘","salt가 water에 녹는 이유 explain해줘",
        "eclipse 생기는 원리 explain해줘","196 divided by 14 계산해줘","43 plus 29 풀어줘",
        "one-line joke 해줘","warm greeting 해줘","short drum groove 작곡해줘","tiny myth 써줘",
        "64 cube root 계산해줘","protein synthesis 설명해줘",
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
        prefix = "v5f-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5f-confirm"
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
        "endpoint_counts": sorted(
            len(tool.endpoints)
            for tool in registry.tools()
        ),
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
