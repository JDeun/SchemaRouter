# ruff: noqa: E501
"""Generate identity-disjoint V6B corpora for experiment #395."""

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

from benchmarks.operation_routing_v6b_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402
from benchmarks.schema_hard_negative_ellipsoid import hard_negative_texts  # noqa: E402

ACTIONS: dict[str, dict[str, str]] = {
    "search": {
        "en": "locate entries that satisfy the criteria",
        "ko": "조건을 충족하는 항목을 찾아줘",
        "es": "localiza entradas que cumplan los criterios",
        "ja": "条件を満たす項目を見つけて",
        "de": "ermittle Einträge die die Kriterien erfüllen",
        "mixed": "조건을 충족하는 entries locate해줘",
    },
    "retrieve": {
        "en": "show the one record already identified",
        "ko": "이미 식별된 한 건을 보여줘",
        "es": "muestra el registro concreto ya identificado",
        "ja": "特定済みの一件を表示して",
        "de": "zeige den bereits identifizierten einzelnen Datensatz",
        "mixed": "이미 identified된 one record 보여줘",
    },
    "list": {
        "en": "enumerate the complete collection",
        "ko": "전체 컬렉션을 나열해줘",
        "es": "enumera la colección completa",
        "ja": "コレクション全体を列挙して",
        "de": "zähle die vollständige Sammlung auf",
        "mixed": "complete collection을 enumerate해줘",
    },
    "create": {
        "en": "make a new resource",
        "ko": "새 리소스를 하나 만들어줘",
        "es": "crea un recurso nuevo",
        "ja": "新しいリソースを一つ作って",
        "de": "lege eine neue Ressource an",
        "mixed": "new resource 하나 make해줘",
    },
    "update": {
        "en": "edit the stored details of the existing resource",
        "ko": "기존 리소스의 저장된 내용을 편집해줘",
        "es": "edita los datos guardados del recurso existente",
        "ja": "既存リソースの保存内容を編集して",
        "de": "bearbeite die gespeicherten Angaben der bestehenden Ressource",
        "mixed": "existing resource의 stored details 편집해줘",
    },
    "delete": {
        "en": "remove the existing resource permanently",
        "ko": "기존 리소스를 영구적으로 제거해줘",
        "es": "quita permanentemente el recurso existente",
        "ja": "既存リソースを永久に除去して",
        "de": "entferne die bestehende Ressource dauerhaft",
        "mixed": "existing resource를 permanently remove해줘",
    },
    "cancel": {
        "en": "terminate the active request",
        "ko": "진행 중인 요청을 종료해줘",
        "es": "finaliza la solicitud activa",
        "ja": "進行中の依頼を終了して",
        "de": "beende die aktive Anfrage",
        "mixed": "active request를 terminate해줘",
    },
    "refund": {
        "en": "return the payment associated with it",
        "ko": "연결된 결제 금액을 돌려줘",
        "es": "devuelve el pago asociado",
        "ja": "関連する支払いを返金して",
        "de": "zahle die zugehörige Zahlung zurück",
        "mixed": "associated payment를 return해줘",
    },
    "send": {
        "en": "deliver it to its destination",
        "ko": "목적지로 전달해줘",
        "es": "entrégalo en su destino",
        "ja": "宛先へ届けて",
        "de": "stelle es am Ziel zu",
        "mixed": "destination으로 deliver해줘",
    },
    "share": {
        "en": "grant another user access to it",
        "ko": "다른 사용자에게 접근 권한을 줘",
        "es": "concede acceso a otro usuario",
        "ja": "別のユーザーにアクセス権を与えて",
        "de": "gewähre einem anderen Nutzer Zugriff darauf",
        "mixed": "another user에게 access grant해줘",
    },
    "export": {
        "en": "produce a downloadable external file",
        "ko": "다운로드 가능한 외부 파일로 만들어줘",
        "es": "genera un archivo externo descargable",
        "ja": "ダウンロード可能な外部ファイルにして",
        "de": "erzeuge eine herunterladbare externe Datei",
        "mixed": "downloadable external file로 만들어줘",
    },
    "translate": {
        "en": "render the content in a different human language",
        "ko": "내용을 다른 사람 언어로 옮겨줘",
        "es": "pasa el contenido a otra lengua humana",
        "ja": "内容を別の人間言語に置き換えて",
        "de": "übertrage den Inhalt in eine andere menschliche Sprache",
        "mixed": "content를 different human language로 옮겨줘",
    },
    "summarize": {
        "en": "condense it to the essential points",
        "ko": "핵심 포인트만 압축해서 정리해줘",
        "es": "condénsalo a los puntos esenciales",
        "ja": "要点だけに圧縮して",
        "de": "verdichte es auf die wesentlichen Punkte",
        "mixed": "essential points만 condense해줘",
    },
    "compare": {
        "en": "contrast the items side by side",
        "ko": "항목들을 나란히 대조해줘",
        "es": "contrasta los elementos lado a lado",
        "ja": "項目を並べて対照して",
        "de": "stelle die Elemente direkt gegenüber",
        "mixed": "items를 side by side contrast해줘",
    },
    "merge": {
        "en": "combine them into one artifact",
        "ko": "하나의 결과물로 결합해줘",
        "es": "combínalos en un solo artefacto",
        "ja": "一つの成果物に結合して",
        "de": "verbinde sie zu einem einzigen Artefakt",
        "mixed": "one artifact로 combine해줘",
    },
    "restart": {
        "en": "stop it and start it again",
        "ko": "멈췄다가 다시 시작해줘",
        "es": "deténlo y vuelve a iniciarlo",
        "ja": "停止してからもう一度開始して",
        "de": "halte es an und starte es erneut",
        "mixed": "stop했다가 again start해줘",
    },
    "execute": {
        "en": "launch the registered operation",
        "ko": "등록된 작업을 구동해줘",
        "es": "lanza la operación registrada",
        "ja": "登録済みの操作を起動して",
        "de": "starte die registrierte Operation",
        "mixed": "registered operation을 launch해줘",
    },
    "forecast": {
        "en": "estimate its state in a future period",
        "ko": "향후 시점의 상태를 추정해줘",
        "es": "estima su estado en un periodo futuro",
        "ja": "将来期間の状態を見積もって",
        "de": "schätze den Zustand in einem zukünftigen Zeitraum",
        "mixed": "future period의 state를 estimate해줘",
    },
}

WRAPPERS: dict[str, tuple[str, str]] = {
    "en": (
        "Regarding {obj}, please {action}.",
        "For {obj}, I need you to {action}.",
    ),
    "ko": (
        "{obj}에 대해 {action}.",
        "{obj} 건은 {action}.",
    ),
    "es": (
        "Con respecto a {obj}, {action}.",
        "Para {obj}, necesito que {action}.",
    ),
    "ja": (
        "{obj}について、{action}。",
        "{obj}は、{action}。",
    ),
    "de": (
        "Bezüglich {obj}: {action}.",
        "Für {obj} sollst du {action}.",
    ),
    "mixed": (
        "{obj} 기준으로 {action}.",
        "{obj} 건은 please {action}.",
    ),
}

TEMPORAL = {
    "current": {
        "en":"right now","ko":"지금 시점의","es":"justo ahora","ja":"今この時点の","de":"genau jetzt","mixed":"right now의",
    },
    "future": {
        "en":"in an upcoming period","ko":"다가오는 기간의","es":"en un periodo próximo","ja":"今後の期間の","de":"in einem kommenden Zeitraum","mixed":"upcoming period의",
    },
    "historical": {
        "en":"over prior intervals","ko":"과거 구간의","es":"durante intervalos anteriores","ja":"過去の期間の","de":"über frühere Intervalle","mixed":"prior intervals의",
    },
}

ALL_TOOL_LEAVES = tuple(ACTIONS)

OOD = {
    "en": (
        "describe how eclipses happen","draft a limerick about rain","what is the capital of Peru",
        "multiply 37 by 19","explain the water cycle","suggest a jazz chord progression",
        "tell a short myth about the moon","what causes ocean tides","solve 144 minus 57",
        "explain how vaccines train immunity","write a friendly birthday wish","name three Renaissance painters",
    ),
    "ko": (
        "일식이 생기는 원리 설명해줘","비에 대한 리머릭 써줘","페루의 수도가 어디야",
        "37 곱하기 19 계산해줘","물의 순환을 설명해줘","재즈 코드 진행 추천해줘",
        "달에 대한 짧은 신화 이야기해줘","바닷물의 조수 원인이 뭐야","144 빼기 57 계산해줘",
        "백신이 면역을 훈련하는 방식 설명해줘","친근한 생일 축하문 써줘","르네상스 화가 세 명 알려줘",
    ),
    "es": (
        "describe cómo ocurren los eclipses","escribe un limerick sobre la lluvia","cuál es la capital de Perú",
        "multiplica 37 por 19","explica el ciclo del agua","sugiere una progresión de acordes de jazz",
        "cuenta un mito corto sobre la luna","qué causa las mareas oceánicas","resuelve 144 menos 57",
        "explica cómo las vacunas entrenan la inmunidad","escribe un deseo amistoso de cumpleaños","nombra tres pintores del Renacimiento",
    ),
    "ja": (
        "日食が起こる仕組みを説明して","雨についてリメリックを書いて","ペルーの首都はどこ",
        "37掛ける19を計算して","水循環を説明して","ジャズのコード進行を提案して",
        "月について短い神話を話して","海の潮汐の原因は何","144引く57を計算して",
        "ワクチンが免疫を訓練する仕組みを説明して","親しみやすい誕生日メッセージを書いて","ルネサンスの画家を三人挙げて",
    ),
    "de": (
        "beschreibe wie sonnenfinsternisse entstehen","schreibe einen limerick über regen","was ist die hauptstadt von Peru",
        "multipliziere 37 mit 19","erkläre den wasserkreislauf","schlage eine jazz-akkordfolge vor",
        "erzähle einen kurzen mythos über den mond","wodurch entstehen gezeiten","rechne 144 minus 57",
        "erkläre wie impfstoffe das immunsystem trainieren","schreibe einen freundlichen geburtstagswunsch","nenne drei maler der renaissance",
    ),
    "mixed": (
        "eclipse가 생기는 원리 describe해줘","rain에 대한 limerick 써줘","Peru capital이 어디야",
        "37 multiply 19 계산해줘","water cycle 설명해줘","jazz chord progression 추천해줘",
        "moon에 대한 short myth 말해줘","ocean tides cause가 뭐야","144 minus 57 계산해줘",
        "vaccines가 immunity를 train하는 방식 설명해줘","friendly birthday wish 써줘","Renaissance painters 세 명 알려줘",
    ),
}


CONFIRM_OOD = {
    "en": (
        "explain how auroras form","write a haiku about snow","what is the capital of Chile",
        "multiply 42 by 13","explain plate tectonics","suggest a blues turnaround",
        "tell a short fable about a fox","why do seasons change","solve 203 minus 88",
        "explain how antibodies recognize targets","write a brief congratulations note","name three Baroque composers",
    ),
    "ko": (
        "오로라가 생기는 원리 설명해줘","눈에 대한 하이쿠 써줘","칠레의 수도가 어디야",
        "42 곱하기 13 계산해줘","판 구조론 설명해줘","블루스 턴어라운드 추천해줘",
        "여우에 대한 짧은 우화 이야기해줘","계절이 바뀌는 이유가 뭐야","203 빼기 88 계산해줘",
        "항체가 표적을 인식하는 방식 설명해줘","짧은 축하 메시지 써줘","바로크 작곡가 세 명 알려줘",
    ),
    "es": (
        "explica cómo se forman las auroras","escribe un haiku sobre la nieve","cuál es la capital de Chile",
        "multiplica 42 por 13","explica la tectónica de placas","sugiere un turnaround de blues",
        "cuenta una fábula corta sobre un zorro","por qué cambian las estaciones","resuelve 203 menos 88",
        "explica cómo los anticuerpos reconocen objetivos","escribe una breve nota de felicitación","nombra tres compositores barrocos",
    ),
    "ja": (
        "オーロラができる仕組みを説明して","雪について俳句を書いて","チリの首都はどこ",
        "42掛ける13を計算して","プレートテクトニクスを説明して","ブルースのターンアラウンドを提案して",
        "キツネについて短い寓話を話して","季節が変わる理由は何","203引く88を計算して",
        "抗体が標的を認識する仕組みを説明して","短いお祝いメッセージを書いて","バロック作曲家を三人挙げて",
    ),
    "de": (
        "erkläre wie polarlichter entstehen","schreibe ein haiku über schnee","was ist die hauptstadt von Chile",
        "multipliziere 42 mit 13","erkläre plattentektonik","schlage einen blues-turnaround vor",
        "erzähle eine kurze fabel über einen fuchs","warum wechseln die jahreszeiten","rechne 203 minus 88",
        "erkläre wie antikörper ziele erkennen","schreibe eine kurze glückwunschnachricht","nenne drei barockkomponisten",
    ),
    "mixed": (
        "aurora가 생기는 원리 explain해줘","snow에 대한 haiku 써줘","Chile capital이 어디야",
        "42 multiply 13 계산해줘","plate tectonics 설명해줘","blues turnaround 추천해줘",
        "fox에 대한 short fable 말해줘","seasons change 이유가 뭐야","203 minus 88 계산해줘",
        "antibodies가 targets를 recognize하는 방식 설명해줘","brief congratulations note 써줘","Baroque composers 세 명 알려줘",
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


def _query(leaf: str, language: str, obj: str, variant: int) -> str:
    return WRAPPERS[language][variant].format(
        obj=obj,
        action=ACTIONS[leaf][language],
    )


def _supported(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for variant in range(2):
                rows.append(
                    {
                        "id": f"{prefix}-supported-{slug}-{language}-{variant + 1}",
                        "query": _query(spec.leaf, language, obj, variant),
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
        absent = [leaf for leaf in ALL_TOOL_LEAVES if leaf not in supported][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, leaf in enumerate(absent):
                rows.append(
                    {
                        "id": f"{prefix}-near-{tool}-{language}-{index + 1}",
                        "query": _query(leaf, language, obj, index % 2),
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "language": language,
                        "unsupported_action": leaf,
                        "unsupported_family": f"{tool}.{leaf}",
                    }
                )
    return rows


def _ood(prefix: str, bank: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{prefix}-ood-{language}-{index}",
            "query": query,
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
            surfaces.update(
                hard_negative_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported,
                )
            )
    return surfaces


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v6b-dev"
        ood_bank = OOD
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6b-confirm"
        ood_bank = CONFIRM_OOD
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
    if any(
        len(contract.synthetic_positives) != 18
        for contract in contracts.values()
    ):
        raise ValueError("every V6B route must compile exactly 18 positive views")

    rows = [*_supported(specs, prefix), *_near(specs, prefix), *_ood(prefix, ood_bank)]
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [
        row
        for row in rows
        if row["category"] == "out_of_domain"
    ]

    if len(rows) != 552 or len(supported) != 228 or len(near) != 252 or len(ood) != 72:
        raise ValueError("V6B category counts drifted")

    training_surfaces = _training_surfaces(registry)
    collisions = sorted(
        {str(row["query"]) for row in rows}.intersection(training_surfaces)
    )
    if collisions:
        raise ValueError(
            f"evaluation wording collided with training surfaces: {collisions[:3]}"
        )

    hard_negative_counts: dict[str, int] = {}
    by_tool: dict[str, list[Any]] = {}
    for contract in contracts.values():
        by_tool.setdefault(contract.tool_key, []).append(contract)
    for tool_contracts in by_tool.values():
        supported_leaves = {str(contract.leaf) for contract in tool_contracts}
        for contract in tool_contracts:
            hard_negative_counts[contract.route_id] = len(
                hard_negative_texts(
                    resource_anchor=contract.resource_anchor,
                    supported_leaves=supported_leaves,
                )
            )

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
            {
                contract.adapter or "native"
                for contract in contracts.values()
            }
        ),
        "synthetic_positives_per_route": 18,
        "hard_negative_counts": hard_negative_counts,
        "evaluation_wording_bank": (
            "V6B-only ACTIONS+WRAPPERS; exact-string disjoint from "
            "positive and complement-negative training surfaces"
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
