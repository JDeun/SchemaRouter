# ruff: noqa: E501
"""Generate disjoint 0.12-C corpora for hierarchical capability ontology experiment #354."""

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

from benchmarks.hierarchical_capability_ontology import (  # noqa: E402
    compile_registry_contracts,
)
from benchmarks.operation_routing_v5c_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("look through {obj}", "find matching {obj}"),
        "ko": ("{obj} 검색해서 찾아줘", "조건에 맞는 {obj} 찾아줘"),
        "es": ("busca entre {obj}", "encuentra {obj} que coincidan"),
        "ja": ("{obj}を検索して", "条件に合う{obj}を探して"),
        "de": ("durchsuche {obj}", "finde passende {obj}"),
        "mixed": ("{obj} search해서 찾아줘", "matching {obj} 찾아줘"),
    },
    "retrieve": {
        "en": ("open {obj}", "pull the details for {obj}"),
        "ko": ("{obj} 상세를 불러와줘", "{obj} 열어줘"),
        "es": ("abre {obj}", "obtén los detalles de {obj}"),
        "ja": ("{obj}を開いて", "{obj}の詳細を取得して"),
        "de": ("öffne {obj}", "ruf die Details von {obj} ab"),
        "mixed": ("{obj} details 불러와줘", "open {obj}"),
    },
    "list": {
        "en": ("show the full list of {obj}", "enumerate {obj}"),
        "ko": ("{obj} 전체 목록 보여줘", "{obj} 전부 나열해줘"),
        "es": ("muestra la lista completa de {obj}", "enumera {obj}"),
        "ja": ("{obj}の全一覧を見せて", "{obj}を列挙して"),
        "de": ("zeige die vollständige Liste der {obj}", "liste {obj} vollständig auf"),
        "mixed": ("{obj} full list 보여줘", "list all {obj}"),
    },
    "create": {
        "en": ("set up a new {obj}", "add a brand-new {obj}"),
        "ko": ("새 {obj} 만들어줘", "{obj} 새로 등록해줘"),
        "es": ("crea un nuevo {obj}", "registra un {obj} nuevo"),
        "ja": ("新しい{obj}を作って", "{obj}を新規登録して"),
        "de": ("lege ein neues {obj} an", "registriere ein neues {obj}"),
        "mixed": ("new {obj} 만들어줘", "create {obj}"),
    },
    "update": {
        "en": ("revise {obj}", "edit the stored details of {obj}"),
        "ko": ("{obj} 저장된 정보 수정해줘", "{obj} 내용 바꿔줘"),
        "es": ("revisa {obj}", "edita los datos guardados de {obj}"),
        "ja": ("{obj}を修正して", "{obj}の保存情報を編集して"),
        "de": ("überarbeite {obj}", "bearbeite die gespeicherten Angaben von {obj}"),
        "mixed": ("{obj} stored info 수정해줘", "update {obj}"),
    },
    "delete": {
        "en": ("wipe out {obj}", "remove {obj} for good"),
        "ko": ("{obj} 완전히 지워줘", "{obj} 영구 삭제해줘"),
        "es": ("borra por completo {obj}", "elimina definitivamente {obj}"),
        "ja": ("{obj}を完全に消して", "{obj}を永久削除して"),
        "de": ("entferne {obj} endgültig", "lösche {obj} dauerhaft"),
        "mixed": ("{obj} 완전히 delete해줘", "remove {obj} permanently"),
    },
    "cancel": {
        "en": ("call off {obj}", "stop the active {obj}"),
        "ko": ("{obj} 취소해줘", "진행 중인 {obj} 중단해줘"),
        "es": ("anula {obj}", "detén {obj} activo"),
        "ja": ("{obj}を取り消して", "進行中の{obj}を中止して"),
        "de": ("storniere {obj}", "brich das aktive {obj} ab"),
        "mixed": ("{obj} 취소해줘", "stop active {obj}"),
    },
    "refund": {
        "en": ("give the money back for {obj}", "reimburse {obj}"),
        "ko": ("{obj} 돈 돌려줘", "{obj} 환불 처리해줘"),
        "es": ("devuelve el dinero de {obj}", "reembolsa {obj}"),
        "ja": ("{obj}のお金を返して", "{obj}を返金して"),
        "de": ("zahle das Geld für {obj} zurück", "erstatte {obj}"),
        "mixed": ("{obj} money 돌려줘", "refund {obj}"),
    },
    "send": {
        "en": ("forward {obj} to its destination", "deliver {obj}"),
        "ko": ("{obj} 목적지로 전달해줘", "{obj} 보내줘"),
        "es": ("reenvía {obj} a su destino", "entrega {obj}"),
        "ja": ("{obj}を宛先へ転送して", "{obj}を送って"),
        "de": ("leite {obj} an sein Ziel weiter", "verschicke {obj}"),
        "mixed": ("{obj} destination으로 보내줘", "send {obj}"),
    },
    "share": {
        "en": ("give another user access to {obj}", "share access to {obj}"),
        "ko": ("다른 사용자에게 {obj} 접근권 줘", "{obj} 접근을 공유해줘"),
        "es": ("da acceso a {obj} a otro usuario", "comparte el acceso a {obj}"),
        "ja": ("別のユーザーに{obj}へのアクセスを与えて", "{obj}へのアクセスを共有して"),
        "de": ("gib einem anderen Nutzer Zugriff auf {obj}", "teile den Zugriff auf {obj}"),
        "mixed": ("다른 user에게 {obj} access 줘", "share {obj} access"),
    },
    "export": {
        "en": ("save {obj} as an external file", "download a file version of {obj}"),
        "ko": ("{obj} 외부 파일로 저장해줘", "{obj} 파일로 내려받아줘"),
        "es": ("guarda {obj} como archivo externo", "descarga una versión de archivo de {obj}"),
        "ja": ("{obj}を外部ファイルとして保存して", "{obj}のファイル版をダウンロードして"),
        "de": ("speichere {obj} als externe Datei", "lade eine Dateiversion von {obj} herunter"),
        "mixed": ("{obj} external file로 저장해줘", "download {obj} file"),
    },
    "translate": {
        "en": ("put {obj} into another language", "change the language of {obj}"),
        "ko": ("{obj} 다른 언어로 옮겨줘", "{obj} 언어를 바꿔줘"),
        "es": ("pasa {obj} a otro idioma", "cambia el idioma de {obj}"),
        "ja": ("{obj}を別の言語にして", "{obj}の言語を変えて"),
        "de": ("übertrage {obj} in eine andere Sprache", "ändere die Sprache von {obj}"),
        "mixed": ("{obj} 다른 language로 옮겨줘", "translate {obj}"),
    },
    "summarize": {
        "en": ("boil {obj} down to the key points", "make {obj} much shorter"),
        "ko": ("{obj} 핵심만 짧게 정리해줘", "{obj} 짧게 요약해줘"),
        "es": ("reduce {obj} a sus puntos clave", "haz {obj} mucho más corto"),
        "ja": ("{obj}を要点だけにまとめて", "{obj}を短く要約して"),
        "de": ("reduziere {obj} auf die Kernaussagen", "fasse {obj} stark verkürzt zusammen"),
        "mixed": ("{obj} 핵심만 summarize해줘", "make {obj} shorter"),
    },
    "compare": {
        "en": ("tell me how {obj} differ", "put {obj} side by side"),
        "ko": ("{obj} 차이점 알려줘", "{obj} 나란히 비교해줘"),
        "es": ("dime en qué difieren {obj}", "pon {obj} lado a lado"),
        "ja": ("{obj}の違いを教えて", "{obj}を並べて比較して"),
        "de": ("sage mir die Unterschiede zwischen {obj}", "stelle {obj} gegenüber"),
        "mixed": ("{obj} differences 알려줘", "compare {obj}"),
    },
    "merge": {
        "en": ("combine {obj} into one result", "join {obj} together"),
        "ko": ("{obj} 하나로 합쳐줘", "{obj} 병합해줘"),
        "es": ("combina {obj} en un resultado", "une {obj}"),
        "ja": ("{obj}を一つにまとめて", "{obj}を統合して"),
        "de": ("kombiniere {obj} zu einem Ergebnis", "führe {obj} zusammen"),
        "mixed": ("{obj} 하나로 merge해줘", "combine {obj}"),
    },
    "restart": {
        "en": ("bring {obj} back up", "cycle {obj}"),
        "ko": ("{obj} 다시 올려줘", "{obj} 재시작해줘"),
        "es": ("vuelve a levantar {obj}", "reinicia {obj}"),
        "ja": ("{obj}をもう一度立ち上げて", "{obj}を再起動して"),
        "de": ("fahre {obj} wieder hoch", "starte {obj} neu"),
        "mixed": ("{obj} 다시 start해줘", "restart {obj}"),
    },
    "execute": {
        "en": ("fire off {obj}", "launch {obj}"),
        "ko": ("{obj} 실행시켜줘", "{obj} 돌려줘"),
        "es": ("lanza {obj}", "ejecuta {obj}"),
        "ja": ("{obj}を実行して", "{obj}を起動して"),
        "de": ("stoße {obj} an", "führe {obj} aus"),
        "mixed": ("{obj} 실행해줘", "run {obj}"),
    },
    "forecast": {
        "en": ("project what {obj} will be later", "estimate the future {obj}"),
        "ko": ("앞으로 {obj} 어떻게 될지 예측해줘", "미래 {obj} 전망해줘"),
        "es": ("proyecta cómo será {obj} más adelante", "estima el futuro de {obj}"),
        "ja": ("今後の{obj}を予測して", "将来の{obj}を見積もって"),
        "de": ("projiziere wie sich {obj} entwickeln wird", "schätze die zukünftigen {obj}"),
        "mixed": ("future {obj} 예측해줘", "forecast {obj}"),
    },
}

TEMPORAL: dict[str, dict[str, str]] = {
    "current": {"en":"right now","ko":"현재","es":"ahora","ja":"現在の","de":"aktuell","mixed":"현재"},
    "future": {"en":"in the future","ko":"향후","es":"en el futuro","ja":"将来の","de":"zukünftig","mixed":"future"},
    "historical": {"en":"from the past","ko":"과거","es":"del pasado","ja":"過去の","de":"historisch","mixed":"past"},
}

ALL_TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en": (
        "write a sonnet about the ocean","make up a bedtime story","explain why ice floats",
        "explain plate tectonics","calculate 144 divided by 12","solve 17 plus 26",
        "tell me a pun","say hello in a friendly way","compose a blues riff","write a short fable",
        "calculate the fourth root of 16","explain cellular respiration",
    ),
    "ko": (
        "바다에 대한 소네트 써줘","잠자리 이야기를 지어줘","얼음이 뜨는 이유 설명해줘",
        "판 구조론 설명해줘","144 나누기 12 계산해줘","17 더하기 26 풀어줘",
        "말장난 하나 해줘","친근하게 인사해줘","블루스 리프 작곡해줘","짧은 우화 써줘",
        "16의 네제곱근 계산해줘","세포 호흡을 설명해줘",
    ),
    "es": (
        "escribe un soneto sobre el océano","inventa un cuento para dormir","explica por qué flota el hielo",
        "explica la tectónica de placas","calcula 144 dividido entre 12","resuelve 17 más 26",
        "dime un juego de palabras","saluda de forma amistosa","compón un riff de blues","escribe una fábula corta",
        "calcula la cuarta raíz de 16","explica la respiración celular",
    ),
    "ja": (
        "海についてソネットを書いて","寝る前の物語を作って","氷が浮く理由を説明して",
        "プレートテクトニクスを説明して","144割る12を計算して","17足す26を解いて",
        "だじゃれを言って","親しみやすく挨拶して","ブルースのリフを作曲して","短い寓話を書いて",
        "16の4乗根を計算して","細胞呼吸を説明して",
    ),
    "de": (
        "schreibe ein sonett über den ozean","erfinde eine gute-nacht-geschichte","erkläre warum eis schwimmt",
        "erkläre plattentektonik","berechne 144 geteilt durch 12","löse 17 plus 26",
        "mach ein wortspiel","begrüße mich freundlich","komponiere ein blues-riff","schreibe eine kurze fabel",
        "berechne die vierte wurzel aus 16","erkläre zellatmung",
    ),
    "mixed": (
        "ocean에 대한 sonnet 써줘","bedtime story 지어줘","ice가 뜨는 이유 explain해줘",
        "plate tectonics 설명해줘","144 divided by 12 계산해줘","17 plus 26 풀어줘",
        "pun 하나 해줘","friendly하게 hello 해줘","blues riff 작곡해줘","short fable 써줘",
        "16 fourth root 계산해줘","cellular respiration 설명해줘",
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
        tool = spec.route_id.split(".", 1)[0]
        result.setdefault(tool, []).append(spec)
    return result


def _near(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_by_tool(specs).items()):
        supported = {spec.leaf for spec in tool_specs}
        unsupported = [leaf for leaf in ALL_TOOL_LEAVES if leaf not in supported][:6]
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
        raise ValueError("duplicate IDs")

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
