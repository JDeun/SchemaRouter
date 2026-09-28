# ruff: noqa: E501
"""Generate identity-disjoint V6D corpora for experiment #399."""

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

from benchmarks.operation_routing_v6d_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import ACTION_PHRASES, compile_registry_contracts  # noqa: E402
from benchmarks.schema_hard_negative_ellipsoid import hard_negative_texts  # noqa: E402

ALL_TOOL_LEAVES = tuple(ACTION_PHRASES)

OOD_PREFIX = {
    "en": "briefly, ",
    "ko": "간단히 ",
    "es": "brevemente, ",
    "ja": "簡潔に",
    "de": "kurz: ",
    "mixed": "briefly ",
}

EVAL_ACTIONS: dict[str, dict[str, str]] = {
    "search": {"en":"look up entries satisfying the requested constraints","ko":"요청 조건을 만족하는 항목을 찾아봐","es":"consulta entradas que cumplan las restricciones solicitadas","ja":"指定条件を満たす項目を探して","de":"suche Einträge die die angeforderten Bedingungen erfüllen","mixed":"requested 조건을 만족하는 entries 찾아봐"},
    "retrieve": {"en":"bring back the specific existing record","ko":"특정된 기존 기록 한 건을 가져와","es":"trae el registro existente específico","ja":"特定された既存レコードを一件持ってきて","de":"hole den konkret bestimmten vorhandenen Datensatz","mixed":"specific existing record 한 건 가져와"},
    "list": {"en":"show the full set of existing records","ko":"기존 기록 전체 집합을 보여줘","es":"muestra el conjunto completo de registros existentes","ja":"既存レコードの全体を表示して","de":"zeige die vollständige Menge vorhandener Datensätze","mixed":"existing records 전체 set 보여줘"},
    "create": {"en":"add a completely new resource","ko":"완전히 새 리소스를 추가해","es":"añade un recurso completamente nuevo","ja":"まったく新しいリソースを追加して","de":"füge eine vollständig neue Ressource hinzu","mixed":"completely new resource 추가해"},
    "update": {"en":"revise the stored attributes of the existing resource","ko":"기존 리소스의 저장 속성을 고쳐","es":"revisa los atributos guardados del recurso existente","ja":"既存リソースの保存属性を修正して","de":"überarbeite die gespeicherten Attribute der vorhandenen Ressource","mixed":"existing resource stored attributes 고쳐"},
    "delete": {"en":"erase the existing resource for good","ko":"기존 리소스를 완전히 지워","es":"borra definitivamente el recurso existente","ja":"既存リソースを完全に消去して","de":"lösche die vorhandene Ressource endgültig","mixed":"existing resource 완전히 erase해"},
    "cancel": {"en":"end the active request before completion","ko":"진행 중 요청을 완료 전에 끝내","es":"termina la solicitud activa antes de completarla","ja":"進行中の依頼を完了前に終了して","de":"beende die aktive Anfrage vor ihrem Abschluss","mixed":"active request를 completion 전에 끝내"},
    "refund": {"en":"return the money tied to the completed payment","ko":"완료된 결제에 연결된 금액을 돌려줘","es":"devuelve el dinero asociado al pago completado","ja":"完了した支払いに紐づく金額を返して","de":"erstatte das Geld der abgeschlossenen Zahlung","mixed":"completed payment의 money 돌려줘"},
    "send": {"en":"transmit it to the intended destination","ko":"의도된 목적지로 전송해","es":"transmítelo al destino previsto","ja":"指定された宛先へ送って","de":"übermittle es an das vorgesehene Ziel","mixed":"intended destination으로 transmit해"},
    "share": {"en":"give another user access to the existing item","ko":"다른 사용자에게 기존 항목 접근권을 줘","es":"da a otro usuario acceso al elemento existente","ja":"別ユーザーに既存項目へのアクセスを与えて","de":"gib einem anderen Nutzer Zugriff auf das vorhandene Element","mixed":"another user에게 existing item access 줘"},
    "export": {"en":"write the existing data out as a downloadable file","ko":"기존 데이터를 다운로드 파일로 내보내","es":"escribe los datos existentes como archivo descargable","ja":"既存データをダウンロード可能なファイルに出力して","de":"gib die vorhandenen Daten als herunterladbare Datei aus","mixed":"existing data를 downloadable file로 내보내"},
    "translate": {"en":"convert the content into a different human language","ko":"콘텐츠를 다른 사람 언어로 바꿔","es":"convierte el contenido a otro idioma humano","ja":"内容を別の人間言語に変換して","de":"übertrage den Inhalt in eine andere menschliche Sprache","mixed":"content를 different human language로 바꿔"},
    "summarize": {"en":"reduce the content to its essential points","ko":"콘텐츠를 핵심 요점만 남겨 정리해","es":"reduce el contenido a sus puntos esenciales","ja":"内容を重要な要点だけにまとめて","de":"reduziere den Inhalt auf die wesentlichen Punkte","mixed":"content를 essential points만 남겨 정리해"},
    "compare": {"en":"set the items against each other and identify differences","ko":"항목들을 서로 대조해서 차이를 찾아","es":"contrasta los elementos e identifica diferencias","ja":"項目同士を対照して違いを特定して","de":"stelle die Elemente gegenüber und bestimme Unterschiede","mixed":"items 서로 contrast해서 differences 찾아"},
    "merge": {"en":"join the resources into a single combined result","ko":"리소스들을 하나의 결합 결과로 합쳐","es":"une los recursos en un único resultado combinado","ja":"複数リソースを一つの統合結果にまとめて","de":"führe die Ressourcen zu einem gemeinsamen Ergebnis zusammen","mixed":"resources를 single combined result로 합쳐"},
    "restart": {"en":"cycle the running service off and on again","ko":"실행 중 서비스를 껐다가 다시 켜","es":"detén el servicio en ejecución y vuelve a iniciarlo","ja":"稼働中サービスを停止して再起動して","de":"stoppe den laufenden Dienst und starte ihn erneut","mixed":"running service를 off했다가 다시 on해"},
    "execute": {"en":"start the registered operation now","ko":"등록된 작업을 지금 시작해","es":"inicia ahora la operación registrada","ja":"登録済み操作を今開始して","de":"starte die registrierte Operation jetzt","mixed":"registered operation 지금 start해"},
    "forecast": {"en":"project the value or state into a future interval","ko":"값이나 상태를 미래 구간으로 예측해","es":"proyecta el valor o estado a un intervalo futuro","ja":"値や状態を将来区間へ予測して","de":"projiziere Wert oder Zustand in ein zukünftiges Intervall","mixed":"value/state를 future interval로 예측해"},
}

WRAPPERS: dict[str, tuple[str, str]] = {
    "en": ("For {obj}, could you {action}?", "Take {obj} and {action}."),
    "ko": ("{obj} 건으로 {action}.", "{obj}를 대상으로 {action}."),
    "es": ("Para {obj}, ¿puedes {action}?", "Toma {obj} y {action}."),
    "ja": ("{obj}を対象に、{action}。", "{obj}について{action}。"),
    "de": ("Für {obj}: {action}.", "Nimm {obj} und {action}."),
    "mixed": ("{obj} 대상으로 please {action}.", "{obj} 기준으로 {action}."),
}

TEMPORAL = {
    "current": {"en":"at the present moment","ko":"현재 시점의","es":"en el momento actual","ja":"現在時点の","de":"zum aktuellen Zeitpunkt","mixed":"present moment의"},
    "future": {"en":"for a later interval","ko":"이후 구간의","es":"para un intervalo posterior","ja":"後の期間の","de":"für ein späteres Intervall","mixed":"later interval의"},
    "historical": {"en":"across earlier intervals","ko":"이전 구간들의","es":"a lo largo de intervalos anteriores","ja":"以前の期間にわたる","de":"über frühere Intervalle hinweg","mixed":"earlier intervals의"},
}

OOD = {
    "en": ("explain why comets have tails","write a short toast for a wedding","what is the capital of Kenya","calculate 58 times 14","describe how coral reefs form","suggest a funk bass progression","tell a short story about a lighthouse","why does metal rust","compute 311 minus 126","explain how memory works in the brain","write a polite thank-you note","name three Impressionist painters"),
    "ko": ("혜성에 꼬리가 생기는 이유 설명해줘","결혼식용 짧은 건배사 써줘","케냐의 수도가 어디야","58 곱하기 14 계산해줘","산호초가 형성되는 과정 설명해줘","펑크 베이스 진행 추천해줘","등대에 대한 짧은 이야기 해줘","금속이 녹스는 이유가 뭐야","311 빼기 126 계산해줘","뇌에서 기억이 작동하는 방식 설명해줘","정중한 감사 문구 써줘","인상주의 화가 세 명 알려줘"),
    "es": ("explica por qué los cometas tienen cola","escribe un brindis corto para una boda","cuál es la capital de Kenia","calcula 58 por 14","describe cómo se forman los arrecifes de coral","sugiere una progresión de bajo funk","cuenta una historia corta sobre un faro","por qué se oxida el metal","calcula 311 menos 126","explica cómo funciona la memoria en el cerebro","escribe una nota educada de agradecimiento","nombra tres pintores impresionistas"),
    "ja": ("彗星に尾ができる理由を説明して","結婚式用の短い乾杯文を書いて","ケニアの首都はどこ","58掛ける14を計算して","サンゴ礁ができる仕組みを説明して","ファンクのベース進行を提案して","灯台について短い話をして","金属が錆びる理由は何","311引く126を計算して","脳で記憶が働く仕組みを説明して","丁寧なお礼文を書いて","印象派の画家を三人挙げて"),
    "de": ("erkläre warum kometen schweife haben","schreibe einen kurzen hochzeitstoast","was ist die hauptstadt von Kenia","berechne 58 mal 14","beschreibe wie korallenriffe entstehen","schlage eine funk-bassfolge vor","erzähle eine kurze geschichte über einen leuchtturm","warum rostet metall","berechne 311 minus 126","erkläre wie erinnerung im gehirn funktioniert","schreibe eine höfliche dankesnotiz","nenne drei impressionistische maler"),
    "mixed": ("comet tail이 생기는 이유 explain해줘","wedding용 short toast 써줘","Kenya capital이 어디야","58 times 14 계산해줘","coral reef 형성 과정 describe해줘","funk bass progression 추천해줘","lighthouse에 대한 short story 해줘","metal rust 이유가 뭐야","311 minus 126 계산해줘","brain memory 작동 방식 explain해줘","polite thank-you note 써줘","Impressionist painters 세 명 알려줘"),
}

CONFIRM_OOD = {
    "en": ("explain why leaves change color","write a short rhyme about stars","what is the capital of Ghana","calculate 64 times 17","describe how glaciers move","suggest a soul chord progression","tell a short story about a bridge","why does bread rise","compute 425 minus 179","explain how muscles contract","write a concise welcome note","name three Romantic composers"),
    "ko": ("잎 색이 변하는 이유 설명해줘","별에 대한 짧은 운문 써줘","가나의 수도가 어디야","64 곱하기 17 계산해줘","빙하가 움직이는 방식 설명해줘","소울 코드 진행 추천해줘","다리에 대한 짧은 이야기 해줘","빵이 부푸는 이유가 뭐야","425 빼기 179 계산해줘","근육이 수축하는 방식 설명해줘","간단한 환영 문구 써줘","낭만주의 작곡가 세 명 알려줘"),
    "es": ("explica por qué las hojas cambian de color","escribe una rima corta sobre las estrellas","cuál es la capital de Ghana","calcula 64 por 17","describe cómo se mueven los glaciares","sugiere una progresión de acordes soul","cuenta una historia corta sobre un puente","por qué sube el pan","calcula 425 menos 179","explica cómo se contraen los músculos","escribe una nota de bienvenida concisa","nombra tres compositores románticos"),
    "ja": ("葉の色が変わる理由を説明して","星について短い韻文を書いて","ガーナの首都はどこ","64掛ける17を計算して","氷河が動く仕組みを説明して","ソウルのコード進行を提案して","橋について短い話をして","パンが膨らむ理由は何","425引く179を計算して","筋肉が収縮する仕組みを説明して","簡潔な歓迎文を書いて","ロマン派の作曲家を三人挙げて"),
    "de": ("erkläre warum blätter ihre farbe ändern","schreibe einen kurzen reim über sterne","was ist die hauptstadt von Ghana","berechne 64 mal 17","beschreibe wie gletscher sich bewegen","schlage eine soul-akkordfolge vor","erzähle eine kurze geschichte über eine brücke","warum geht brot auf","berechne 425 minus 179","erkläre wie muskeln sich zusammenziehen","schreibe eine knappe willkommensnotiz","nenne drei romantische komponisten"),
    "mixed": ("leaves color change 이유 explain해줘","stars에 대한 short rhyme 써줘","Ghana capital이 어디야","64 times 17 계산해줘","glacier movement describe해줘","soul chord progression 추천해줘","bridge에 대한 short story 해줘","bread rise 이유가 뭐야","425 minus 179 계산해줘","muscle contraction 방식 explain해줘","concise welcome note 써줘","Romantic composers 세 명 알려줘"),
}


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _object(spec: RouteCaseSpec, language: str) -> str:
    obj = spec.objects[language]
    if spec.temporal_scope:
        return f"{TEMPORAL[spec.temporal_scope][language]} {obj}"
    return obj


def _query(leaf: str, language: str, obj: str, variant: int) -> str:
    return WRAPPERS[language][variant].format(obj=obj, action=EVAL_ACTIONS[leaf][language])


def _supported(specs: tuple[RouteCaseSpec, ...], prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for variant in range(2):
                rows.append({
                    "id": f"{prefix}-supported-{slug}-{language}-{variant + 1}",
                    "query": _query(spec.leaf, language, obj, variant),
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
            for index, leaf in enumerate(absent):
                rows.append({
                    "id": f"{prefix}-near-{tool}-{language}-{index + 1}",
                    "query": _query(leaf, language, obj, index % 2),
                    "expected": None,
                    "category": "near_domain_unsupported_operation",
                    "language": language,
                    "unsupported_action": leaf,
                    "unsupported_family": f"{tool}.{leaf}",
                })
    return rows


def _ood(prefix: str, bank: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{prefix}-ood-{language}-{index}",
            "query": f"{OOD_PREFIX[language]}{query}",
            "expected": None,
            "category": "out_of_domain",
            "language": language,
        }
        for language in LANGUAGES
        for index, query in enumerate(bank[language], start=1)
    ]


def _training_surfaces(registry: Any) -> set[str]:
    contracts = compile_registry_contracts(registry)
    by_tool: dict[str, list[Any]] = {}
    for contract in contracts.values():
        by_tool.setdefault(contract.tool_key, []).append(contract)

    surfaces: set[str] = set()
    for contracts_for_tool in by_tool.values():
        supported = {str(contract.leaf) for contract in contracts_for_tool if contract.leaf}
        for contract in contracts_for_tool:
            surfaces.update(contract.synthetic_positives)
            surfaces.update(hard_negative_texts(
                resource_anchor=contract.resource_anchor,
                supported_leaves=supported,
            ))
    return surfaces


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v6d-dev"
        ood_bank = OOD
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6d-confirm"
        ood_bank = CONFIRM_OOD
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(f"route fixture mismatch missing={sorted(expected-set(contracts))} extra={sorted(set(contracts)-expected)}")

    unknown = sorted(route for route, contract in contracts.items() if contract.leaf is None)
    if unknown:
        raise ValueError(f"evaluation endpoint leaves must be known before freeze: {unknown}")
    if any(len(contract.synthetic_positives) != 18 for contract in contracts.values()):
        raise ValueError("every V6D route must compile exactly 18 positive views")

    rows = [*_supported(specs, prefix), *_near(specs, prefix), *_ood(prefix, ood_bank)]
    supported = [row for row in rows if row["expected"] is not None]
    near = [row for row in rows if row["category"] == "near_domain_unsupported_operation"]
    ood = [row for row in rows if row["category"] == "out_of_domain"]

    if len(rows) != 552 or len(supported) != 228 or len(near) != 252 or len(ood) != 72:
        raise ValueError("V6D category counts drifted")

    training_surfaces = _training_surfaces(registry)
    collisions = sorted({str(row["query"]) for row in rows}.intersection(training_surfaces))
    if collisions:
        raise ValueError(f"evaluation wording collided with schema evidence: {collisions[:3]}")

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
        "density_evidence": "unchanged #384 positives + unchanged #395 tool-complement negatives; component structure fixed by registry",
        "evaluation_wording_bank": "V6D inherited EVAL_ACTIONS+WRAPPERS with new registry objects and OOD prefixes; exact-string disjoint from schema evidence and V6A-C queries",
        "corpus_sha256": hashlib.sha256(_canonical(rows)).hexdigest(),
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    freeze: dict[str, Any] = {}
    query_sets: dict[str, set[str]] = {}
    for role in ("development", "confirmation"):
        rows, manifest = build(role)
        query_sets[role] = {str(row["query"]) for row in rows}
        (args.out_dir / f"{role}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (args.out_dir / f"{role}-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        freeze[role] = manifest

    overlap = query_sets["development"].intersection(query_sets["confirmation"])
    if overlap:
        raise ValueError(f"DEV/confirmation query identities overlap: {sorted(overlap)[:3]}")

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
