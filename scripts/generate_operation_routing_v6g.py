# ruff: noqa: E501
"""Generate V6G calibration/DEV/confirmation together before model scoring."""

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

from benchmarks.conformal_e5_membership import build_e0_documents  # noqa: E402
from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    CALIBRATION_ROUTE_SPECS,
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    calibration_registry,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402
from scripts.generate_operation_routing_v6e import (  # noqa: E402
    ALL_TOOL_LEAVES,
    EVAL_ACTIONS,
    TEMPORAL,
    WRAPPERS,
)

QUERY_PREFIX = {
    "en": "Decide whether this registered catalog can handle: ",
    "ko": "등록된 카탈로그가 이 요청을 처리할 수 있는지 판단해줘: ",
    "es": "Decide si el catálogo registrado puede manejar: ",
    "ja": "登録済みカタログでこの依頼を処理できるか判断して: ",
    "de": "Entscheide, ob der registrierte Katalog dies bearbeiten kann: ",
    "mixed": "registered catalog가 이 request를 handle 가능한지 판단해줘: ",
}

CALIBRATION_OOD = {
    "en": (
        "explain why the moon has phases",
        "write a short birthday limerick",
        "what is the capital of Peru",
        "calculate 73 times 16",
        "describe how thunderstorms form",
        "suggest a neo-soul chord progression",
        "tell a short story about a telescope",
        "why does copper turn green",
        "compute 518 minus 237",
        "explain how kidneys filter blood",
        "write a polite meeting invitation",
        "name three Baroque painters",
    ),
    "ko": (
        "달의 위상이 생기는 이유 설명해줘",
        "생일용 짧은 리머릭 써줘",
        "페루의 수도가 어디야",
        "73 곱하기 16 계산해줘",
        "뇌우가 형성되는 과정 설명해줘",
        "네오소울 코드 진행 추천해줘",
        "망원경에 대한 짧은 이야기 해줘",
        "구리가 초록색으로 변하는 이유가 뭐야",
        "518 빼기 237 계산해줘",
        "신장이 혈액을 거르는 방식 설명해줘",
        "정중한 회의 초대 문구 써줘",
        "바로크 화가 세 명 알려줘",
    ),
    "es": (
        "explica por qué la luna tiene fases",
        "escribe un limerick corto de cumpleaños",
        "cuál es la capital de Perú",
        "calcula 73 por 16",
        "describe cómo se forman las tormentas",
        "sugiere una progresión neo-soul",
        "cuenta una historia corta sobre un telescopio",
        "por qué el cobre se vuelve verde",
        "calcula 518 menos 237",
        "explica cómo filtran sangre los riñones",
        "escribe una invitación educada a una reunión",
        "nombra tres pintores barrocos",
    ),
    "ja": (
        "月の満ち欠けが起こる理由を説明して",
        "誕生日向けの短いリメリックを書いて",
        "ペルーの首都はどこ",
        "73掛ける16を計算して",
        "雷雨が形成される仕組みを説明して",
        "ネオソウルのコード進行を提案して",
        "望遠鏡について短い話をして",
        "銅が緑色になる理由は何",
        "518引く237を計算して",
        "腎臓が血液をろ過する仕組みを説明して",
        "丁寧な会議招待文を書いて",
        "バロック画家を三人挙げて",
    ),
    "de": (
        "erkläre warum der mond phasen hat",
        "schreibe einen kurzen geburtstagslimerick",
        "was ist die hauptstadt von Peru",
        "berechne 73 mal 16",
        "beschreibe wie gewitter entstehen",
        "schlage eine neo-soul-akkordfolge vor",
        "erzähle eine kurze geschichte über ein teleskop",
        "warum wird kupfer grün",
        "berechne 518 minus 237",
        "erkläre wie nieren blut filtern",
        "schreibe eine höfliche besprechungseinladung",
        "nenne drei barockmaler",
    ),
    "mixed": (
        "moon phases 이유 explain해줘",
        "birthday용 short limerick 써줘",
        "Peru capital이 어디야",
        "73 times 16 계산해줘",
        "thunderstorm 형성 과정 describe해줘",
        "neo-soul chord progression 추천해줘",
        "telescope에 대한 short story 해줘",
        "copper가 green 되는 이유가 뭐야",
        "518 minus 237 계산해줘",
        "kidney blood filtering 방식 explain해줘",
        "polite meeting invitation 써줘",
        "Baroque painters 세 명 알려줘",
    ),
}

DEV_OOD = {
    "en": (
        "explain why tides change during the day",
        "write a short poem about rain",
        "what is the capital of Chile",
        "calculate 87 times 12",
        "describe how volcanoes erupt",
        "suggest a gospel piano progression",
        "tell a short story about a train station",
        "why does silver tarnish",
        "compute 604 minus 289",
        "explain how lungs exchange oxygen",
        "write a concise apology note",
        "name three Cubist painters",
    ),
    "ko": (
        "하루 동안 조수가 변하는 이유 설명해줘",
        "비에 대한 짧은 시 써줘",
        "칠레의 수도가 어디야",
        "87 곱하기 12 계산해줘",
        "화산이 분출하는 과정 설명해줘",
        "가스펠 피아노 진행 추천해줘",
        "기차역에 대한 짧은 이야기 해줘",
        "은이 변색되는 이유가 뭐야",
        "604 빼기 289 계산해줘",
        "폐가 산소를 교환하는 방식 설명해줘",
        "간단한 사과 문구 써줘",
        "입체파 화가 세 명 알려줘",
    ),
    "es": (
        "explica por qué cambian las mareas durante el día",
        "escribe un poema corto sobre la lluvia",
        "cuál es la capital de Chile",
        "calcula 87 por 12",
        "describe cómo erupcionan los volcanes",
        "sugiere una progresión de piano góspel",
        "cuenta una historia corta sobre una estación de tren",
        "por qué se empaña la plata",
        "calcula 604 menos 289",
        "explica cómo intercambian oxígeno los pulmones",
        "escribe una nota breve de disculpa",
        "nombra tres pintores cubistas",
    ),
    "ja": (
        "一日の中で潮の満ち引きが変わる理由を説明して",
        "雨について短い詩を書いて",
        "チリの首都はどこ",
        "87掛ける12を計算して",
        "火山が噴火する仕組みを説明して",
        "ゴスペルピアノの進行を提案して",
        "駅について短い話をして",
        "銀が変色する理由は何",
        "604引く289を計算して",
        "肺が酸素交換する仕組みを説明して",
        "簡潔なお詫び文を書いて",
        "キュビスム画家を三人挙げて",
    ),
    "de": (
        "erkläre warum sich gezeiten im tagesverlauf ändern",
        "schreibe ein kurzes gedicht über regen",
        "was ist die hauptstadt von Chile",
        "berechne 87 mal 12",
        "beschreibe wie vulkane ausbrechen",
        "schlage eine gospel-klavierfolge vor",
        "erzähle eine kurze geschichte über einen bahnhof",
        "warum läuft silber an",
        "berechne 604 minus 289",
        "erkläre wie lungen sauerstoff austauschen",
        "schreibe eine knappe entschuldigung",
        "nenne drei kubistische maler",
    ),
    "mixed": (
        "tides change 이유 explain해줘",
        "rain에 대한 short poem 써줘",
        "Chile capital이 어디야",
        "87 times 12 계산해줘",
        "volcano eruption 과정 describe해줘",
        "gospel piano progression 추천해줘",
        "train station에 대한 short story 해줘",
        "silver tarnish 이유가 뭐야",
        "604 minus 289 계산해줘",
        "lung oxygen exchange 방식 explain해줘",
        "concise apology note 써줘",
        "Cubist painters 세 명 알려줘",
    ),
}

CONFIRM_OOD = {
    "en": (
        "explain why seasons change",
        "write a short haiku about snow",
        "what is the capital of Ecuador",
        "calculate 92 times 13",
        "describe how caves form",
        "suggest a bossa nova chord progression",
        "tell a short story about a harbor",
        "why does iron become magnetic",
        "compute 703 minus 348",
        "explain how neurons send signals",
        "write a brief congratulation note",
        "name three Surrealist painters",
    ),
    "ko": (
        "계절이 바뀌는 이유 설명해줘",
        "눈에 대한 짧은 하이쿠 써줘",
        "에콰도르의 수도가 어디야",
        "92 곱하기 13 계산해줘",
        "동굴이 형성되는 과정 설명해줘",
        "보사노바 코드 진행 추천해줘",
        "항구에 대한 짧은 이야기 해줘",
        "철이 자성을 띠는 이유가 뭐야",
        "703 빼기 348 계산해줘",
        "뉴런이 신호를 보내는 방식 설명해줘",
        "짧은 축하 문구 써줘",
        "초현실주의 화가 세 명 알려줘",
    ),
    "es": (
        "explica por qué cambian las estaciones",
        "escribe un haiku corto sobre la nieve",
        "cuál es la capital de Ecuador",
        "calcula 92 por 13",
        "describe cómo se forman las cuevas",
        "sugiere una progresión de bossa nova",
        "cuenta una historia corta sobre un puerto",
        "por qué el hierro se vuelve magnético",
        "calcula 703 menos 348",
        "explica cómo envían señales las neuronas",
        "escribe una breve nota de felicitación",
        "nombra tres pintores surrealistas",
    ),
    "ja": (
        "季節が変わる理由を説明して",
        "雪について短い俳句を書いて",
        "エクアドルの首都はどこ",
        "92掛ける13を計算して",
        "洞窟が形成される仕組みを説明して",
        "ボサノバのコード進行を提案して",
        "港について短い話をして",
        "鉄が磁性を持つ理由は何",
        "703引く348を計算して",
        "ニューロンが信号を送る仕組みを説明して",
        "短いお祝い文を書いて",
        "シュルレアリスム画家を三人挙げて",
    ),
    "de": (
        "erkläre warum sich die jahreszeiten ändern",
        "schreibe ein kurzes haiku über schnee",
        "was ist die hauptstadt von Ecuador",
        "berechne 92 mal 13",
        "beschreibe wie höhlen entstehen",
        "schlage eine bossa-nova-akkordfolge vor",
        "erzähle eine kurze geschichte über einen hafen",
        "warum wird eisen magnetisch",
        "berechne 703 minus 348",
        "erkläre wie neuronen signale senden",
        "schreibe eine kurze glückwunschnotiz",
        "nenne drei surrealistische maler",
    ),
    "mixed": (
        "seasons change 이유 explain해줘",
        "snow에 대한 short haiku 써줘",
        "Ecuador capital이 어디야",
        "92 times 13 계산해줘",
        "cave formation 과정 describe해줘",
        "bossa nova chord progression 추천해줘",
        "harbor에 대한 short story 해줘",
        "iron magnetic 이유가 뭐야",
        "703 minus 348 계산해줘",
        "neuron signaling 방식 explain해줘",
        "brief congratulation note 써줘",
        "Surrealist painters 세 명 알려줘",
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
    body = WRAPPERS[language][variant].format(
        obj=obj,
        action=EVAL_ACTIONS[leaf][language],
    )
    return f"{QUERY_PREFIX[language]}{body}"


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


def _ood(
    prefix: str,
    bank: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{prefix}-ood-{language}-{index}",
            "query": f"{QUERY_PREFIX[language]}{query}",
            "expected": None,
            "category": "out_of_domain",
            "language": language,
        }
        for language in LANGUAGES
        for index, query in enumerate(bank[language], start=1)
    ]


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "calibration":
        registry = calibration_registry()
        specs = CALIBRATION_ROUTE_SPECS
        prefix = "v6g-cal"
        ood_bank = CALIBRATION_OOD
    elif role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v6g-dev"
        ood_bank = DEV_OOD
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6g-confirm"
        ood_bank = CONFIRM_OOD
    else:
        raise ValueError(
            "role must be calibration, development, or confirmation"
        )

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(
            "route fixture mismatch "
            f"missing={sorted(expected-set(contracts))} "
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

    rows = [
        *_supported(specs, prefix),
        *_near(specs, prefix),
        *_ood(prefix, ood_bank),
    ]
    supported = [row for row in rows if row["category"] == "supported"]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]

    if (
        len(rows) != 552
        or len(supported) != 228
        or len(near) != 252
        or len(ood) != 72
    ):
        raise ValueError("V6G category counts drifted")

    e0_texts = {document.text for document in build_e0_documents(registry)}
    collisions = sorted(
        {str(row["query"]) for row in rows}.intersection(e0_texts)
    )
    if collisions:
        raise ValueError(
            f"evaluation query collided with E0 document: {collisions[:3]}"
        )

    manifest = {
        "role": role,
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "unsupported_cases": len(near) + len(ood),
        "route_count": len(contracts),
        "tool_count": len(registry.tools()),
        "endpoint_counts": sorted(
            len(tool.endpoints) for tool in registry.tools()
        ),
        "languages": list(LANGUAGES),
        "adapters": sorted(
            {contract.adapter or "native" for contract in contracts.values()}
        ),
        "e0_document_count": len(e0_texts),
        "evaluation_wording_bank": (
            "V6G uses a new fixed catalog-membership request prefix, new "
            "registry identities and new OOD surfaces; exact-string "
            "disjointness against V6A-F and between all V6G surfaces is "
            "protocol-tested."
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
    query_sets: dict[str, set[str]] = {}
    for role in ("calibration", "development", "confirmation"):
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

    roles = tuple(query_sets)
    for index, left in enumerate(roles):
        for right in roles[index + 1 :]:
            overlap = query_sets[left].intersection(query_sets[right])
            if overlap:
                raise ValueError(
                    f"{left}/{right} query identities overlap: "
                    f"{sorted(overlap)[:3]}"
                )

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
