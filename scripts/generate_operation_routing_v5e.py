# ruff: noqa: E501
"""Generate disjoint 0.12-E corpora for capability-set membership experiment #363."""

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

from benchmarks.capability_set_membership_veto import compile_registry_contracts  # noqa: E402
from benchmarks.operation_routing_v5e_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("scan {obj} for matches", "locate matching {obj}"),
        "ko": ("{obj} 중에서 맞는 걸 검색해줘", "{obj} 조건에 맞는 항목 찾아줘"),
        "es": ("explora {obj} para encontrar coincidencias", "localiza {obj} que coincidan"),
        "ja": ("{obj}から一致するものを検索して", "条件に合う{obj}を見つけて"),
        "de": ("durchsuche {obj} nach Treffern", "finde passende {obj}"),
        "mixed": ("{obj} 중 matching 항목 찾아줘", "scan {obj} for matches"),
    },
    "retrieve": {
        "en": ("bring up {obj}", "fetch the stored details for {obj}"),
        "ko": ("{obj} 저장된 상세정보 불러줘", "{obj} 바로 열어줘"),
        "es": ("recupera {obj}", "obtén los datos guardados de {obj}"),
        "ja": ("{obj}を呼び出して", "{obj}の保存済み詳細を取得して"),
        "de": ("ruf {obj} auf", "hole die gespeicherten Details von {obj}"),
        "mixed": ("{obj} stored details 불러줘", "fetch {obj}"),
    },
    "list": {
        "en": ("enumerate every {obj}", "give me the complete collection of {obj}"),
        "ko": ("{obj} 전부 나열해줘", "{obj} 전체 모음 보여줘"),
        "es": ("enumera todos los {obj}", "dame la colección completa de {obj}"),
        "ja": ("{obj}を全部列挙して", "{obj}の全コレクションを見せて"),
        "de": ("zähle alle {obj} auf", "zeige mir die vollständige Sammlung von {obj}"),
        "mixed": ("all {obj} 나열해줘", "complete {obj} collection 보여줘"),
    },
    "create": {
        "en": ("open a new {obj}", "provision a fresh {obj}"),
        "ko": ("새 {obj} 개설해줘", "{obj} 새로 생성해줘"),
        "es": ("abre un nuevo {obj}", "aprovisiona un {obj} nuevo"),
        "ja": ("新しい{obj}を開設して", "{obj}を新規作成して"),
        "de": ("lege ein neues {obj} an", "stelle ein frisches {obj} bereit"),
        "mixed": ("new {obj} 개설해줘", "provision {obj}"),
    },
    "update": {
        "en": ("revise the saved {obj}", "alter the stored fields of {obj}"),
        "ko": ("저장된 {obj} 수정해줘", "{obj} 저장 필드 바꿔줘"),
        "es": ("revisa el {obj} guardado", "altera los campos almacenados de {obj}"),
        "ja": ("保存済みの{obj}を修正して", "{obj}の保存フィールドを変更して"),
        "de": ("überarbeite das gespeicherte {obj}", "ändere die gespeicherten Felder von {obj}"),
        "mixed": ("saved {obj} 수정해줘", "alter {obj} fields"),
    },
    "delete": {
        "en": ("expunge {obj}", "remove {obj} permanently from storage"),
        "ko": ("{obj} 완전 삭제해줘", "저장소에서 {obj} 영구 제거해줘"),
        "es": ("elimina por completo {obj}", "borra {obj} permanentemente del almacenamiento"),
        "ja": ("{obj}を完全に削除して", "保存領域から{obj}を永久に消して"),
        "de": ("entferne {obj} vollständig", "lösche {obj} dauerhaft aus dem Speicher"),
        "mixed": ("{obj} 완전 remove해줘", "delete {obj} permanently"),
    },
    "cancel": {
        "en": ("withdraw {obj}", "terminate the active {obj}"),
        "ko": ("{obj} 철회해줘", "진행 중인 {obj} 종료해줘"),
        "es": ("retira {obj}", "termina el {obj} activo"),
        "ja": ("{obj}を取り消して", "進行中の{obj}を終了して"),
        "de": ("ziehe {obj} zurück", "beende das aktive {obj}"),
        "mixed": ("{obj} 철회해줘", "terminate active {obj}"),
    },
    "refund": {
        "en": ("return the charge for {obj}", "pay back the amount for {obj}"),
        "ko": ("{obj} 결제금액 돌려줘", "{obj} 금액 환불해줘"),
        "es": ("devuelve el cargo de {obj}", "reembolsa el importe de {obj}"),
        "ja": ("{obj}の料金を返して", "{obj}の金額を払い戻して"),
        "de": ("erstatte die Gebühr für {obj}", "zahle den Betrag für {obj} zurück"),
        "mixed": ("{obj} charge 돌려줘", "pay back {obj}"),
    },
    "send": {
        "en": ("route {obj} to the recipient", "transmit {obj} to its destination"),
        "ko": ("{obj} 수신자에게 전달해줘", "{obj} 목적지로 전송해줘"),
        "es": ("dirige {obj} al destinatario", "transmite {obj} a su destino"),
        "ja": ("{obj}を受信者へ送って", "{obj}を宛先へ送信して"),
        "de": ("leite {obj} an den Empfänger", "übertrage {obj} an sein Ziel"),
        "mixed": ("{obj} recipient에게 보내줘", "transmit {obj}"),
    },
    "share": {
        "en": ("grant another user access to {obj}", "make {obj} accessible to another user"),
        "ko": ("다른 사용자에게 {obj} 접근권한 줘", "{obj} 다른 사용자도 접근하게 해줘"),
        "es": ("concede a otro usuario acceso a {obj}", "haz {obj} accesible para otro usuario"),
        "ja": ("別のユーザーに{obj}へのアクセス権を与えて", "{obj}を別ユーザーも利用できるようにして"),
        "de": ("gewähre einem anderen Nutzer Zugriff auf {obj}", "mache {obj} für einen anderen Nutzer zugänglich"),
        "mixed": ("another user에게 {obj} access 줘", "share access to {obj}"),
    },
    "export": {
        "en": ("emit {obj} as a file", "produce a downloadable file for {obj}"),
        "ko": ("{obj} 파일로 내보내줘", "{obj} 다운로드 가능한 파일로 만들어줘"),
        "es": ("emite {obj} como archivo", "genera un archivo descargable para {obj}"),
        "ja": ("{obj}をファイルとして出力して", "{obj}のダウンロード用ファイルを作って"),
        "de": ("gib {obj} als Datei aus", "erzeuge eine herunterladbare Datei für {obj}"),
        "mixed": ("{obj} file로 emit해줘", "make downloadable {obj} file"),
    },
    "translate": {
        "en": ("render {obj} in a different language", "convert the language used by {obj}"),
        "ko": ("{obj} 다른 언어로 바꿔줘", "{obj} 사용 언어 변환해줘"),
        "es": ("convierte {obj} a otro idioma", "cambia el idioma usado por {obj}"),
        "ja": ("{obj}を別の言語に変換して", "{obj}で使う言語を変えて"),
        "de": ("übertrage {obj} in eine andere Sprache", "ändere die verwendete Sprache von {obj}"),
        "mixed": ("{obj} different language로 바꿔줘", "translate {obj}"),
    },
    "summarize": {
        "en": ("compress {obj} to its essentials", "reduce {obj} to the main takeaways"),
        "ko": ("{obj} 핵심만 압축해줘", "{obj} 주요 내용만 남겨줘"),
        "es": ("comprime {obj} a lo esencial", "reduce {obj} a las ideas principales"),
        "ja": ("{obj}を要点だけに圧縮して", "{obj}を主要ポイントだけにして"),
        "de": ("verdichte {obj} auf das Wesentliche", "reduziere {obj} auf die Kernaussagen"),
        "mixed": ("{obj} essentials만 남겨줘", "summarize {obj}"),
    },
    "compare": {
        "en": ("contrast {obj}", "identify the differences across {obj}"),
        "ko": ("{obj} 서로 대조해줘", "{obj} 차이 찾아줘"),
        "es": ("contrasta {obj}", "identifica las diferencias entre {obj}"),
        "ja": ("{obj}を対比して", "{obj}の違いを見つけて"),
        "de": ("stelle {obj} gegenüber", "ermittle die Unterschiede zwischen {obj}"),
        "mixed": ("{obj} 서로 contrast해줘", "find differences in {obj}"),
    },
    "merge": {
        "en": ("consolidate {obj} into one item", "fuse {obj} into a single result"),
        "ko": ("{obj} 하나로 통합해줘", "{obj} 단일 결과로 합쳐줘"),
        "es": ("consolida {obj} en un elemento", "fusiona {obj} en un único resultado"),
        "ja": ("{obj}を一つに統合して", "{obj}を単一の結果にまとめて"),
        "de": ("konsolidiere {obj} zu einem Element", "verschmelze {obj} zu einem Ergebnis"),
        "mixed": ("{obj} 하나로 consolidate해줘", "merge {obj}"),
    },
    "restart": {
        "en": ("recycle {obj}", "stop and start {obj} again"),
        "ko": ("{obj} 다시 기동해줘", "{obj} 껐다가 다시 켜줘"),
        "es": ("recicla {obj}", "detén y vuelve a iniciar {obj}"),
        "ja": ("{obj}を再起動して", "{obj}を停止してもう一度起動して"),
        "de": ("starte {obj} zyklisch neu", "stoppe {obj} und starte es erneut"),
        "mixed": ("{obj} 다시 기동해줘", "recycle {obj}"),
    },
    "execute": {
        "en": ("invoke {obj}", "trigger execution of {obj}"),
        "ko": ("{obj} 호출해서 실행해줘", "{obj} 실행 트리거해줘"),
        "es": ("invoca {obj}", "activa la ejecución de {obj}"),
        "ja": ("{obj}を呼び出して実行して", "{obj}の実行をトリガーして"),
        "de": ("rufe {obj} auf", "löse die Ausführung von {obj} aus"),
        "mixed": ("{obj} invoke해서 실행해줘", "trigger {obj}"),
    },
    "forecast": {
        "en": ("project the later {obj}", "estimate what {obj} will become"),
        "ko": ("나중의 {obj} 전망해줘", "{obj} 앞으로 값 추정해줘"),
        "es": ("proyecta el {obj} posterior", "estima en qué se convertirá {obj}"),
        "ja": ("今後の{obj}を予測して", "{obj}がどうなるか見積もって"),
        "de": ("projiziere das spätere {obj}", "schätze wie sich {obj} entwickeln wird"),
        "mixed": ("later {obj} 전망해줘", "forecast {obj}"),
    },
}

TEMPORAL: dict[str, dict[str, str]] = {
    "current": {"en":"present","ko":"현재","es":"actual","ja":"現在の","de":"aktuell","mixed":"current"},
    "future": {"en":"future","ko":"향후","es":"futuro","ja":"将来の","de":"zukünftig","mixed":"future"},
    "historical": {"en":"historical","ko":"과거","es":"histórico","ja":"過去の","de":"historisch","mixed":"historical"},
}

TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en": (
        "write a villanelle about winter","invent a space-adventure scene","explain why metal expands when heated",
        "explain how eclipses happen","calculate 225 divided by 15","solve 31 plus 47",
        "tell a clever one-line joke","give me a cheerful greeting","compose a funk bass line","write a tiny myth",
        "calculate the fifth root of 32","explain photosynthesis",
    ),
    "ko": (
        "겨울에 대한 빌라넬 써줘","우주 모험 장면 만들어줘","금속이 가열되면 팽창하는 이유 설명해줘",
        "일식과 월식 원리 설명해줘","225 나누기 15 계산해줘","31 더하기 47 풀어줘",
        "짧고 재치있는 농담 해줘","밝게 인사해줘","펑크 베이스라인 작곡해줘","아주 짧은 신화 써줘",
        "32의 다섯제곱근 계산해줘","광합성을 설명해줘",
    ),
    "es": (
        "escribe una villanela sobre el invierno","inventa una escena de aventura espacial","explica por qué el metal se expande al calentarse",
        "explica cómo ocurren los eclipses","calcula 225 dividido entre 15","resuelve 31 más 47",
        "dime un chiste breve e ingenioso","dame un saludo alegre","compón una línea de bajo funk","escribe un mito muy corto",
        "calcula la quinta raíz de 32","explica la fotosíntesis",
    ),
    "ja": (
        "冬についてヴィラネルを書いて","宇宙冒険の場面を作って","金属が熱で膨張する理由を説明して",
        "日食と月食の仕組みを説明して","225割る15を計算して","31足す47を解いて",
        "短くて気の利いた冗談を言って","明るく挨拶して","ファンクのベースラインを作曲して","とても短い神話を書いて",
        "32の5乗根を計算して","光合成を説明して",
    ),
    "de": (
        "schreibe eine villanelle über den winter","erfinde eine weltraum-abenteuerszene","erkläre warum metall sich beim erhitzen ausdehnt",
        "erkläre wie finsternisse entstehen","berechne 225 geteilt durch 15","löse 31 plus 47",
        "erzähle einen kurzen klugen witz","begrüße mich fröhlich","komponiere eine funk-basslinie","schreibe einen winzigen mythos",
        "berechne die fünfte wurzel aus 32","erkläre photosynthese",
    ),
    "mixed": (
        "winter에 대한 villanelle 써줘","space adventure scene 만들어줘","metal이 heat에서 팽창하는 이유 explain해줘",
        "eclipse 원리 explain해줘","225 divided by 15 계산해줘","31 plus 47 풀어줘",
        "clever one-line joke 해줘","cheerful greeting 해줘","funk bass line 작곡해줘","tiny myth 써줘",
        "32 fifth root 계산해줘","photosynthesis 설명해줘",
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
    if spec.temporal_scope is None:
        return obj
    return f"{TEMPORAL[spec.temporal_scope][language]} {obj}"


def _supported(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for index, template in enumerate(SURFACES[spec.leaf][language], start=1):
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
        tool = spec.route_id.split(".", 1)[0]
        result.setdefault(tool, []).append(spec)
    return result


def _near(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_by_tool(specs).items()):
        supported = {spec.leaf for spec in tool_specs}
        unsupported = [leaf for leaf in TOOL_LEAVES if leaf not in supported][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, leaf in enumerate(unsupported, start=1):
                template = SURFACES[leaf][language][(index + 1) % 2]
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
        prefix = "v5e-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5e-confirm"
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
