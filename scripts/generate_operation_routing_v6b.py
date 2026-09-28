# ruff: noqa: E501
"""Generate identity-disjoint V6B corpora for hard-negative boundary experiment #393."""

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
from benchmarks.schema_hard_negative_adb import (  # noqa: E402
    LEAF_ORDER,
    hard_negative_texts,
)

EVAL_VERBS: dict[str, dict[str, str]] = {
    "search": {
        "en": "look up matches for",
        "ko": "조건에 맞는 걸 찾아줘",
        "es": "encuentra coincidencias para",
        "ja": "該当するものを探して",
        "de": "nach Treffern durchsuchen",
        "mixed": "matching 항목 찾아줘",
    },
    "retrieve": {
        "en": "open the saved",
        "ko": "저장된 항목을 열어줘",
        "es": "abre el guardado",
        "ja": "保存済みを開いて",
        "de": "gespeichertes öffnen",
        "mixed": "saved 항목 열어줘",
    },
    "list": {
        "en": "show every available",
        "ko": "사용 가능한 걸 전부 보여줘",
        "es": "muestra todos los disponibles",
        "ja": "利用可能なものを全部見せて",
        "de": "alle verfügbaren anzeigen",
        "mixed": "available 항목 전부 보여줘",
    },
    "create": {
        "en": "set up a new",
        "ko": "새 항목을 마련해줘",
        "es": "configura uno nuevo de",
        "ja": "新しいものを用意して",
        "de": "neu anlegen",
        "mixed": "new 항목 setup해줘",
    },
    "update": {
        "en": "change the stored",
        "ko": "저장된 내용을 바꿔줘",
        "es": "cambia el guardado",
        "ja": "保存内容を変更して",
        "de": "gespeichertes ändern",
        "mixed": "stored 내용 바꿔줘",
    },
    "delete": {
        "en": "remove for good",
        "ko": "완전히 없애줘",
        "es": "quita definitivamente",
        "ja": "完全に消して",
        "de": "endgültig entfernen",
        "mixed": "완전히 remove해줘",
    },
    "cancel": {
        "en": "call off",
        "ko": "진행을 취소해줘",
        "es": "anula",
        "ja": "取り消して",
        "de": "abbrechen",
        "mixed": "진행 cancel해줘",
    },
    "refund": {
        "en": "give the money back for",
        "ko": "지불한 돈을 돌려줘",
        "es": "devuelve el dinero de",
        "ja": "支払ったお金を返して",
        "de": "das Geld zurückgeben für",
        "mixed": "paid money 돌려줘",
    },
    "send": {
        "en": "forward",
        "ko": "전달해줘",
        "es": "reenvía",
        "ja": "転送して",
        "de": "weiterleiten",
        "mixed": "forward해줘",
    },
    "share": {
        "en": "let another user access",
        "ko": "다른 사용자도 접근하게 해줘",
        "es": "permite que otro usuario acceda a",
        "ja": "別ユーザーもアクセスできるようにして",
        "de": "einem anderen Nutzer Zugriff geben auf",
        "mixed": "다른 user도 access하게 해줘",
    },
    "export": {
        "en": "save as a file",
        "ko": "파일로 저장해줘",
        "es": "guarda como archivo",
        "ja": "ファイルとして保存して",
        "de": "als Datei speichern",
        "mixed": "file로 save해줘",
    },
    "translate": {
        "en": "put into another language",
        "ko": "다른 언어로 바꿔줘",
        "es": "pasa a otro idioma",
        "ja": "別の言語に変えて",
        "de": "in eine andere Sprache übertragen",
        "mixed": "다른 language로 바꿔줘",
    },
    "summarize": {
        "en": "give me the short version of",
        "ko": "짧게 핵심만 정리해줘",
        "es": "dame la versión corta de",
        "ja": "短く要点だけまとめて",
        "de": "kurz zusammenfassen",
        "mixed": "short version으로 정리해줘",
    },
    "compare": {
        "en": "tell me the differences between",
        "ko": "차이를 알려줘",
        "es": "dime las diferencias entre",
        "ja": "違いを教えて",
        "de": "die Unterschiede nennen zwischen",
        "mixed": "differences 알려줘",
    },
    "merge": {
        "en": "join together",
        "ko": "하나로 묶어줘",
        "es": "une",
        "ja": "一つにまとめて",
        "de": "zusammenfügen",
        "mixed": "하나로 join해줘",
    },
    "restart": {
        "en": "bring back up",
        "ko": "다시 올려줘",
        "es": "vuelve a levantar",
        "ja": "もう一度立ち上げて",
        "de": "wieder hochfahren",
        "mixed": "다시 up시켜줘",
    },
    "execute": {
        "en": "run now",
        "ko": "지금 돌려줘",
        "es": "pon en marcha ahora",
        "ja": "今走らせて",
        "de": "jetzt ausführen",
        "mixed": "지금 run해줘",
    },
    "forecast": {
        "en": "estimate what comes next for",
        "ko": "앞으로 어떻게 될지 추정해줘",
        "es": "estima lo que viene para",
        "ja": "今後どうなるか見積もって",
        "de": "die weitere Entwicklung schätzen für",
        "mixed": "앞으로 어떻게 될지 estimate해줘",
    },
}

EVAL_WRAPPERS: dict[str, tuple[str, str]] = {
    "en": ("Could you {verb} {resource}?", "I need you to {verb} {resource}."),
    "ko": ("{resource} {verb}", "부탁인데 {resource} {verb}"),
    "es": ("¿Puedes {verb} {resource}?", "Necesito que {verb} {resource}."),
    "ja": ("{resource}について{verb}", "お願い、{resource}を{verb}"),
    "de": ("Kannst du {resource} {verb}?", "Bitte {resource} {verb}."),
    "mixed": ("{resource} {verb}", "please {resource} {verb}"),
}

TEMPORAL: dict[str, dict[str, str]] = {
    "current": {
        "en": "at this moment",
        "ko": "지금 시점의",
        "es": "en este momento",
        "ja": "現時点の",
        "de": "im Moment",
        "mixed": "지금 moment의",
    },
    "future": {
        "en": "for the next period",
        "ko": "다음 기간의",
        "es": "para el próximo período",
        "ja": "次の期間の",
        "de": "für den nächsten Zeitraum",
        "mixed": "next 기간의",
    },
    "historical": {
        "en": "from earlier observations",
        "ko": "이전 관측의",
        "es": "de observaciones anteriores",
        "ja": "以前の観測の",
        "de": "aus früheren Beobachtungen",
        "mixed": "earlier 관측의",
    },
}

OOD: dict[str, tuple[str, ...]] = {
    "en": (
        "write a villanelle about a river",
        "invent a scene on a distant planet",
        "explain why metal expands when heated",
        "explain how tides work",
        "calculate 225 divided by 15",
        "solve 58 plus 37",
        "tell me a dry joke",
        "give me a cheerful welcome",
        "compose a short bass groove",
        "write a miniature legend",
        "calculate the fifth root of 32",
        "explain DNA replication",
    ),
    "ko": (
        "강에 대한 빌라넬 시를 써줘",
        "먼 행성의 장면을 지어줘",
        "금속이 가열되면 팽창하는 이유를 설명해줘",
        "조수가 생기는 원리를 설명해줘",
        "225 나누기 15 계산해줘",
        "58 더하기 37 풀어줘",
        "썰렁한 농담 하나 해줘",
        "밝게 환영 인사해줘",
        "짧은 베이스 그루브 작곡해줘",
        "아주 짧은 전설을 써줘",
        "32의 5제곱근을 계산해줘",
        "DNA 복제를 설명해줘",
    ),
    "es": (
        "escribe una villanela sobre un río",
        "inventa una escena en un planeta lejano",
        "explica por qué el metal se expande al calentarse",
        "explica cómo funcionan las mareas",
        "calcula 225 dividido entre 15",
        "resuelve 58 más 37",
        "cuéntame un chiste seco",
        "dame una bienvenida alegre",
        "compón un groove corto de bajo",
        "escribe una leyenda diminuta",
        "calcula la quinta raíz de 32",
        "explica la replicación del ADN",
    ),
    "ja": (
        "川についてヴィラネルを書いて",
        "遠い惑星の場面を作って",
        "金属が加熱で膨張する理由を説明して",
        "潮汐の仕組みを説明して",
        "225割る15を計算して",
        "58足す37を解いて",
        "乾いた冗談を言って",
        "明るく歓迎して",
        "短いベースグルーブを作曲して",
        "小さな伝説を書いて",
        "32の5乗根を計算して",
        "DNA複製を説明して",
    ),
    "de": (
        "schreibe eine villanelle über einen fluss",
        "erfinde eine szene auf einem fernen planeten",
        "erkläre warum sich metall beim erhitzen ausdehnt",
        "erkläre wie gezeiten funktionieren",
        "berechne 225 geteilt durch 15",
        "löse 58 plus 37",
        "erzähl einen trockenen witz",
        "begrüße mich fröhlich",
        "komponiere einen kurzen bass-groove",
        "schreibe eine winzige legende",
        "berechne die fünfte wurzel aus 32",
        "erkläre DNA-replikation",
    ),
    "mixed": (
        "river에 대한 villanelle 써줘",
        "distant planet scene 지어줘",
        "metal이 heated되면 expand하는 이유 explain해줘",
        "tides 작동 원리 explain해줘",
        "225 divided by 15 계산해줘",
        "58 plus 37 풀어줘",
        "dry joke 하나 해줘",
        "cheerful welcome 해줘",
        "short bass groove 작곡해줘",
        "miniature legend 써줘",
        "32 fifth root 계산해줘",
        "DNA replication 설명해줘",
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
    resource = spec.objects[language]
    if spec.temporal_scope:
        return f"{TEMPORAL[spec.temporal_scope][language]} {resource}"
    return resource


def _supported(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            resource = _object(spec, language)
            verb = EVAL_VERBS[spec.leaf][language]
            for index, template in enumerate(
                EVAL_WRAPPERS[language],
                start=1,
            ):
                rows.append(
                    {
                        "id": (
                            f"{prefix}-supported-{slug}-"
                            f"{language}-{index}"
                        ),
                        "query": template.format(
                            verb=verb,
                            resource=resource,
                        ),
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
        result.setdefault(
            spec.route_id.split(".", 1)[0],
            [],
        ).append(spec)
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
            for leaf in LEAF_ORDER
            if leaf not in supported
        ][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            resource = anchor.objects[language]
            for index, leaf in enumerate(unsupported, start=1):
                verb = EVAL_VERBS[leaf][language]
                template = EVAL_WRAPPERS[language][index % 2]
                rows.append(
                    {
                        "id": (
                            f"{prefix}-near-{tool}-"
                            f"{language}-{index}"
                        ),
                        "query": template.format(
                            verb=verb,
                            resource=resource,
                        ),
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
        prefix = "v6b-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6b-confirm"
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(
            f"route fixture mismatch missing={sorted(expected-set(contracts))} "
            f"extra={sorted(set(contracts)-expected)}"
        )

    by_tool: dict[str, set[str]] = {}
    for contract in contracts.values():
        if contract.leaf is None:
            raise ValueError(
                f"evaluation route has unknown leaf: {contract.route_id}"
            )
        if len(contract.synthetic_positives) != 18:
            raise ValueError(
                f"evaluation route lacks 18 positive views: {contract.route_id}"
            )
        by_tool.setdefault(contract.tool_key, set()).add(contract.leaf)

    negative_counts: list[int] = []
    for contract in contracts.values():
        negatives = hard_negative_texts(
            contract,
            tool_supported_leaves=by_tool[contract.tool_key],
        )
        if not negatives:
            raise ValueError(
                f"evaluation route lacks hard negatives: {contract.route_id}"
            )
        negative_counts.append(len(negatives))

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
        "synthetic_positives_per_route": 18,
        "hard_negative_count_min": min(negative_counts),
        "hard_negative_count_max": max(negative_counts),
        "evaluation_wording_bank": (
            "V6B-only, distinct from positive and hard-negative banks"
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
