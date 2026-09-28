# ruff: noqa: E501
"""Generate disjoint 0.12-G corpora for set-conditioned entailment experiment #374."""

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

from benchmarks.operation_routing_v5g_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.set_conditioned_entailment import (  # noqa: E402
    compile_registry_contracts,
)

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("scan {obj} for matching entries", "find {obj} that satisfy the criteria"),
        "ko": ("{obj}에서 조건에 맞는 항목 찾아줘", "기준에 맞는 {obj} 검색해줘"),
        "es": ("revisa {obj} para hallar coincidencias", "encuentra {obj} que cumplan los criterios"),
        "ja": ("{obj}から条件に合う項目を探して", "基準に合う{obj}を検索して"),
        "de": ("durchsuche {obj} nach passenden Einträgen", "finde {obj}, die den Kriterien entsprechen"),
        "mixed": ("{obj}에서 matching entries 찾아줘", "criteria 만족하는 {obj} search해줘"),
    },
    "retrieve": {
        "en": ("bring up {obj}", "load the saved record for {obj}"),
        "ko": ("{obj} 불러와줘", "{obj} 저장된 기록 열어줘"),
        "es": ("abre {obj}", "carga el registro guardado de {obj}"),
        "ja": ("{obj}を呼び出して", "{obj}の保存済み記録を開いて"),
        "de": ("ruf {obj} auf", "lade den gespeicherten Datensatz für {obj}"),
        "mixed": ("{obj} 불러와줘", "saved record for {obj} load해줘"),
    },
    "list": {
        "en": ("enumerate the available {obj}", "show the entire set of {obj}"),
        "ko": ("사용 가능한 {obj} 전부 나열해줘", "{obj} 전체 집합 보여줘"),
        "es": ("enumera los {obj} disponibles", "muestra el conjunto completo de {obj}"),
        "ja": ("利用可能な{obj}を列挙して", "{obj}の全体を見せて"),
        "de": ("liste die verfügbaren {obj} auf", "zeige die gesamte Menge der {obj}"),
        "mixed": ("available {obj} 전부 enumerate해줘", "{obj} entire set 보여줘"),
    },
    "create": {
        "en": ("open a new {obj}", "set up a brand-new {obj}"),
        "ko": ("새 {obj} 열어줘", "완전히 새 {obj} 만들어줘"),
        "es": ("abre un nuevo {obj}", "crea un {obj} completamente nuevo"),
        "ja": ("新しい{obj}を作って", "まったく新しい{obj}を登録して"),
        "de": ("lege ein neues {obj} an", "richte ein ganz neues {obj} ein"),
        "mixed": ("new {obj} 열어줘", "brand-new {obj} 만들어줘"),
    },
    "update": {
        "en": ("revise the stored {obj}", "change the existing details of {obj}"),
        "ko": ("저장된 {obj} 수정해줘", "기존 {obj} 세부정보 바꿔줘"),
        "es": ("revisa el {obj} guardado", "cambia los detalles existentes de {obj}"),
        "ja": ("保存済みの{obj}を修正して", "既存の{obj}の詳細を変更して"),
        "de": ("überarbeite das gespeicherte {obj}", "ändere die vorhandenen Details von {obj}"),
        "mixed": ("stored {obj} 수정해줘", "existing details of {obj} 바꿔줘"),
    },
    "delete": {
        "en": ("erase {obj} from storage", "remove {obj} permanently"),
        "ko": ("{obj} 저장소에서 지워줘", "{obj} 영구적으로 제거해줘"),
        "es": ("borra {obj} del almacenamiento", "elimina {obj} permanentemente"),
        "ja": ("{obj}を保存領域から消して", "{obj}を永久に削除して"),
        "de": ("lösche {obj} aus dem Speicher", "entferne {obj} dauerhaft"),
        "mixed": ("{obj} storage에서 지워줘", "remove {obj} permanently"),
    },
    "cancel": {
        "en": ("withdraw the active {obj}", "stop {obj} before completion"),
        "ko": ("진행 중인 {obj} 철회해줘", "{obj} 완료 전에 중단해줘"),
        "es": ("retira el {obj} activo", "detén {obj} antes de completarlo"),
        "ja": ("進行中の{obj}を取り下げて", "{obj}を完了前に止めて"),
        "de": ("ziehe das aktive {obj} zurück", "stoppe {obj} vor dem Abschluss"),
        "mixed": ("active {obj} 철회해줘", "stop {obj} before completion"),
    },
    "refund": {
        "en": ("pay back the amount for {obj}", "return the payment associated with {obj}"),
        "ko": ("{obj} 금액 돌려줘", "{obj} 관련 결제 환불해줘"),
        "es": ("devuelve el importe de {obj}", "reembolsa el pago asociado a {obj}"),
        "ja": ("{obj}の金額を返して", "{obj}に関連する支払いを返金して"),
        "de": ("zahle den Betrag für {obj} zurück", "erstatte die mit {obj} verbundene Zahlung"),
        "mixed": ("{obj} amount 돌려줘", "payment for {obj} refund해줘"),
    },
    "send": {
        "en": ("transmit {obj} to the target", "deliver {obj}"),
        "ko": ("{obj} 대상에게 전송해줘", "{obj} 전달해줘"),
        "es": ("transmite {obj} al destino", "entrega {obj}"),
        "ja": ("{obj}を宛先へ送信して", "{obj}を届けて"),
        "de": ("übertrage {obj} an das Ziel", "stelle {obj} zu"),
        "mixed": ("{obj} target에 transmit해줘", "deliver {obj}"),
    },
    "share": {
        "en": ("grant someone access to {obj}", "share access rights for {obj}"),
        "ko": ("누군가에게 {obj} 접근권 줘", "{obj} 접근 권한 공유해줘"),
        "es": ("concede a alguien acceso a {obj}", "comparte los permisos de acceso de {obj}"),
        "ja": ("誰かに{obj}へのアクセスを与えて", "{obj}のアクセス権を共有して"),
        "de": ("gewähre jemandem Zugriff auf {obj}", "teile die Zugriffsrechte für {obj}"),
        "mixed": ("someone에게 {obj} access 줘", "share access rights for {obj}"),
    },
    "export": {
        "en": ("produce a file export of {obj}", "save {obj} to an external file"),
        "ko": ("{obj} 파일 내보내기 만들어줘", "{obj} 외부 파일로 저장해줘"),
        "es": ("genera una exportación de archivo de {obj}", "guarda {obj} en un archivo externo"),
        "ja": ("{obj}のファイル書き出しを作って", "{obj}を外部ファイルに保存して"),
        "de": ("erzeuge einen Dateiexport von {obj}", "speichere {obj} in einer externen Datei"),
        "mixed": ("{obj} file export 만들어줘", "save {obj} to external file"),
    },
    "translate": {
        "en": ("convert {obj} into a different language", "translate the language of {obj}"),
        "ko": ("{obj} 다른 언어로 변환해줘", "{obj} 언어 번역해줘"),
        "es": ("convierte {obj} a otro idioma", "traduce el idioma de {obj}"),
        "ja": ("{obj}を別の言語に変換して", "{obj}の言語を翻訳して"),
        "de": ("überführe {obj} in eine andere Sprache", "übersetze die Sprache von {obj}"),
        "mixed": ("{obj} different language로 변환해줘", "translate language of {obj}"),
    },
    "summarize": {
        "en": ("reduce {obj} to its key points", "give me a compact summary of {obj}"),
        "ko": ("{obj} 핵심만 남겨줘", "{obj} 짧게 요약해줘"),
        "es": ("reduce {obj} a sus puntos clave", "dame un resumen compacto de {obj}"),
        "ja": ("{obj}を要点だけにして", "{obj}を簡潔に要約して"),
        "de": ("reduziere {obj} auf die Kernpunkte", "gib mir eine kompakte Zusammenfassung von {obj}"),
        "mixed": ("{obj} key points만 남겨줘", "compact summary of {obj} 만들어줘"),
    },
    "compare": {
        "en": ("contrast {obj}", "show how {obj} differ"),
        "ko": ("{obj} 대조해줘", "{obj} 어떻게 다른지 보여줘"),
        "es": ("contrasta {obj}", "muestra en qué difieren {obj}"),
        "ja": ("{obj}を対比して", "{obj}がどう違うか見せて"),
        "de": ("stelle {obj} gegenüber", "zeige wie sich {obj} unterscheiden"),
        "mixed": ("contrast {obj}", "{obj} 어떻게 differ하는지 보여줘"),
    },
    "merge": {
        "en": ("consolidate {obj} into one", "join {obj} as a single result"),
        "ko": ("{obj} 하나로 통합해줘", "{obj} 단일 결과로 합쳐줘"),
        "es": ("consolida {obj} en uno", "une {obj} en un solo resultado"),
        "ja": ("{obj}を一つに統合して", "{obj}を単一の結果にまとめて"),
        "de": ("konsolidiere {obj} zu einem", "führe {obj} zu einem Ergebnis zusammen"),
        "mixed": ("{obj} 하나로 consolidate해줘", "join {obj} as one result"),
    },
    "restart": {
        "en": ("cycle {obj} and start it again", "restart {obj}"),
        "ko": ("{obj} 껐다 다시 시작해줘", "{obj} 재시작해줘"),
        "es": ("reinicia el ciclo de {obj}", "vuelve a iniciar {obj}"),
        "ja": ("{obj}を一度止めて再起動して", "{obj}を再始動して"),
        "de": ("starte {obj} nach einem Zyklus neu", "starte {obj} erneut"),
        "mixed": ("{obj} cycle하고 다시 start해줘", "restart {obj}"),
    },
    "execute": {
        "en": ("invoke the registered {obj}", "trigger {obj} now"),
        "ko": ("등록된 {obj} 호출해줘", "{obj} 지금 트리거해줘"),
        "es": ("invoca el {obj} registrado", "activa {obj} ahora"),
        "ja": ("登録済みの{obj}を呼び出して", "{obj}を今起動して"),
        "de": ("rufe das registrierte {obj} auf", "löse {obj} jetzt aus"),
        "mixed": ("registered {obj} invoke해줘", "trigger {obj} now"),
    },
    "forecast": {
        "en": ("predict the later {obj}", "estimate what {obj} will become"),
        "ko": ("나중 {obj} 예측해줘", "{obj} 앞으로 어떻게 될지 추정해줘"),
        "es": ("predice el {obj} posterior", "estima en qué se convertirá {obj}"),
        "ja": ("将来の{obj}を予測して", "{obj}が今後どうなるか見積もって"),
        "de": ("sage die späteren {obj} voraus", "schätze wie sich {obj} entwickeln wird"),
        "mixed": ("later {obj} predict해줘", "estimate future {obj}"),
    },
}

TEMPORAL = {
    "current": {"en":"at present","ko":"현재","es":"actualmente","ja":"現在の","de":"gegenwärtig","mixed":"현재"},
    "future": {"en":"later","ko":"향후","es":"más adelante","ja":"将来の","de":"später","mixed":"future"},
    "historical": {"en":"from previous observations","ko":"과거","es":"de observaciones anteriores","ja":"過去の","de":"aus früheren Beobachtungen","mixed":"historical"},
}

ALL_TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en": (
        "write a villanelle about the sea","invent a fantasy dialogue","explain why glass is transparent",
        "explain how tides work","calculate 256 divided by 16","solve 52 plus 37",
        "tell a dry joke","give me a formal greeting","compose a short bass line","write a miniature legend",
        "calculate the square root of 361","explain messenger RNA",
    ),
    "ko": (
        "바다에 대한 빌라넬 써줘","판타지 대화 장면 지어줘","유리가 투명한 이유 설명해줘",
        "조수가 생기는 원리 설명해줘","256 나누기 16 계산해줘","52 더하기 37 풀어줘",
        "썰렁한 농담 해줘","격식 있게 인사해줘","짧은 베이스 라인 작곡해줘","작은 전설 써줘",
        "361의 제곱근 계산해줘","메신저 RNA를 설명해줘",
    ),
    "es": (
        "escribe una villanela sobre el mar","inventa un diálogo de fantasía","explica por qué el vidrio es transparente",
        "explica cómo funcionan las mareas","calcula 256 dividido entre 16","resuelve 52 más 37",
        "cuéntame un chiste seco","dame un saludo formal","compón una línea corta de bajo","escribe una leyenda pequeña",
        "calcula la raíz cuadrada de 361","explica el ARN mensajero",
    ),
    "ja": (
        "海についてヴィラネルを書いて","ファンタジーの会話を作って","ガラスが透明な理由を説明して",
        "潮の満ち引きの仕組みを説明して","256割る16を計算して","52足す37を解いて",
        "寒い冗談を言って","丁寧に挨拶して","短いベースラインを作曲して","小さな伝説を書いて",
        "361の平方根を計算して","メッセンジャーRNAを説明して",
    ),
    "de": (
        "schreibe eine villanelle über das meer","erfinde einen fantasy-dialog","erkläre warum glas transparent ist",
        "erkläre wie gezeiten funktionieren","berechne 256 geteilt durch 16","löse 52 plus 37",
        "erzähl einen trockenen witz","begrüße mich formell","komponiere eine kurze basslinie","schreibe eine kleine legende",
        "berechne die quadratwurzel aus 361","erkläre messenger-RNA",
    ),
    "mixed": (
        "sea에 대한 villanelle 써줘","fantasy dialogue 지어줘","glass가 transparent한 이유 explain해줘",
        "tides 작동 원리 explain해줘","256 divided by 16 계산해줘","52 plus 37 풀어줘",
        "dry joke 해줘","formal greeting 해줘","short bass line 작곡해줘","miniature legend 써줘",
        "361 square root 계산해줘","messenger RNA 설명해줘",
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
                        "id": (
                            f"{prefix}-supported-{slug}-{language}-{index}"
                        ),
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
                        "id": (
                            f"{prefix}-near-{tool}-{language}-{index}"
                        ),
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
        prefix = "v5g-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5g-confirm"
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
