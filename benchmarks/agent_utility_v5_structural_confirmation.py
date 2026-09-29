"""Independent confirmation catalog and tasks for structural retrieval v2.

This surface is generated only after the v2 candidate and its core implementation
were frozen. It reuses the canonical capability contract but not the DEV task text
or DEV auxiliary-tool identity pattern.
"""

from __future__ import annotations

from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    STRATA,
    TASKS_PER_CELL,
    _core_tools,
    _endpoint,
    _field,
    _parameter,
)
from schemarouter import InMemoryRegistry, ToolSpec

CONFIRMATION_CATALOG_SIZES = CATALOG_SIZES
CONFIRMATION_LANGUAGES = LANGUAGES
CONFIRMATION_STRATA = STRATA
CONFIRMATION_TASKS_PER_CELL = TASKS_PER_CELL

_ROUTE_TERMS = {
    "literature.search": "literature search",
    "literature.retrieve": "literature retrieval",
    "literature.summarize": "literature summarization",
    "patents.search": "patent search",
    "patents.retrieve": "patent retrieval",
    "datasets.search": "dataset search",
    "datasets.retrieve": "dataset retrieval",
    "samples.get": "sample record read",
    "samples.update": "sample record update",
    "samples.delete": "sample record deletion",
    "jobs.status": "job status check",
    "jobs.cancel": "job cancellation",
    "jobs.restart": "job restart",
    "messages.draft": "message drafting",
    "messages.send": "message sending",
    "assets.archive": "asset archiving",
    "assets.delete": "asset deletion",
    "assets.export": "asset export",
    "experiments.create": "experiment creation",
    "experiments.status": "experiment status check",
    "spectroscopy.raman_peak": "Raman peak position",
    "spectroscopy.absorbance": "optical absorbance",
    "thermal.conductivity": "thermal conductivity",
    "thermal.heat_capacity": "specific heat capacity",
    "mechanics.hardness": "Vickers hardness",
    "mechanics.elastic_modulus": "Young elastic modulus",
    "rheology.viscosity": "dynamic viscosity",
    "optics.refractive_index": "refractive index",
    "geometry.particle_diameter": "particle diameter",
    "electrochem.capacity": "specific discharge capacity",
}
_UNIT_BY_ROUTE = {
    "spectroscopy.raman_peak": "cm^-1",
    "spectroscopy.absorbance": "AU",
    "thermal.conductivity": "W/(m*K)",
    "thermal.heat_capacity": "J/(g*K)",
    "mechanics.hardness": "HV",
    "mechanics.elastic_modulus": "GPa",
    "rheology.viscosity": "mPa*s",
    "optics.refractive_index": "1",
    "geometry.particle_diameter": "nm",
    "electrochem.capacity": "mAh/g",
}

_CONFIRM_RESOURCES = (
    "literature",
    "patent",
    "dataset",
    "sample",
    "job",
    "message",
    "asset",
    "experiment",
    "raman",
    "absorbance",
    "conductivity",
    "heat_capacity",
    "hardness",
    "elasticity",
    "viscosity",
    "refraction",
    "particle_size",
    "capacity",
    "microscopy",
    "supplier",
    "shipment",
    "notebook",
    "workflow",
    "annotation",
    "invoice",
    "calendar",
    "spectrum",
    "composition",
    "batch",
    "recipe",
    "model",
    "checkpoint",
    "report",
    "citation",
    "organization",
    "workspace",
)
_CONFIRM_ACTIONS = (
    "search",
    "retrieve",
    "summarize",
    "read",
    "update",
    "delete",
    "status",
    "cancel",
    "restart",
    "draft",
    "send",
    "archive",
    "export",
    "estimate",
    "forecast",
    "compare",
)
_DISTRACTOR_PREFIXES = (
    "mirror",
    "legacy",
    "proxy",
    "reference",
    "shadow",
    "archive",
)


def _confirmation_distractor(index: int) -> ToolSpec:
    resource = _CONFIRM_RESOURCES[
        (index * 5 + 7) % len(_CONFIRM_RESOURCES)
    ]
    action = _CONFIRM_ACTIONS[
        (index * 11 + 3) % len(_CONFIRM_ACTIONS)
    ]
    prefix = _DISTRACTOR_PREFIXES[
        (index * 3 + 1) % len(_DISTRACTOR_PREFIXES)
    ]
    read_only = action in {
        "search",
        "retrieve",
        "summarize",
        "read",
        "status",
        "export",
        "estimate",
        "forecast",
        "compare",
    }
    return ToolSpec(
        name=f"{prefix}_{resource}_{index:03d}",
        description=(
            f"{prefix.title()} {resource} compatibility service. "
            "This is not the primary registered research capability."
        ),
        endpoints=[
            _endpoint(
                action,
                (
                    f"{action.title()} {resource} compatibility records "
                    f"through the {prefix} service."
                ),
                read_only=read_only,
                destructive=action == "delete",
                parameters=(
                    (
                        _parameter(
                            "record_id",
                            description="compatibility record identifier",
                        ),
                    )
                    if action not in {"search", "status"}
                    else ()
                ),
                fields=(
                    (
                        _field(
                            "payload",
                            f"compat.{prefix}.{resource}.payload",
                            description="compatibility payload",
                        ),
                    )
                    if read_only
                    else ()
                ),
            )
        ],
    )


def build_confirmation_registry(
    endpoint_count: int,
) -> InMemoryRegistry:
    if endpoint_count not in CONFIRMATION_CATALOG_SIZES:
        raise ValueError(
            f"unsupported confirmation catalog size: {endpoint_count}"
        )

    registry = InMemoryRegistry()
    core = _core_tools()
    registry.update_many(core)
    core_count = sum(
        len(tool.endpoints)
        for tool in core
    )
    if core_count != 30:
        raise RuntimeError(
            f"confirmation core endpoint count drifted: {core_count}"
        )

    for index in range(endpoint_count - core_count):
        registry.register(_confirmation_distractor(index))

    actual = sum(
        len(tool.endpoints)
        for tool in registry.tools()
    )
    if actual != endpoint_count:
        raise RuntimeError(
            "confirmation catalog endpoint count drifted: "
            f"expected={endpoint_count} actual={actual}"
        )
    return registry


def _entity(route: str, index: int) -> str:
    if route.startswith("literature."):
        prefix = "REFDOC"
    elif route.startswith("patents."):
        prefix = "REFPAT"
    elif route.startswith("datasets."):
        prefix = "REFDS"
    elif route.startswith("jobs."):
        prefix = "RUN"
    elif route.startswith("messages."):
        prefix = "NOTE"
    elif route.startswith("assets."):
        prefix = "OBJ"
    elif route.startswith("experiments."):
        prefix = "TRIAL"
    elif route.startswith("electrochem."):
        prefix = "CELL"
    else:
        prefix = "SPEC"
    return f"{prefix}-{index + 701}"


def _render(
    language: str,
    kind: str,
    *,
    term: str = "",
    entity: str = "",
    avoid: str = "",
    second: str = "",
    unit: str = "",
) -> str:
    templates: dict[str, dict[str, str]] = {
        "clear": {
            "en": (
                "For {entity}, use the registered capability for {term}."
            ),
            "ko": (
                "{entity}에 대해 등록된 기능으로 {term}을 처리해 주세요."
            ),
            "es": (
                "Para {entity}, usa la capacidad registrada para {term}."
            ),
            "ja": (
                "{entity}について、登録済み機能で {term} を実行してください。"
            ),
            "de": (
                "Führe für {entity} mit der registrierten Funktion "
                "{term} aus."
            ),
            "mixed": (
                "{entity} 기준으로 registered capability에서 "
                "{term} 처리해."
            ),
        },
        "sibling": {
            "en": (
                "For {entity}, choose {term}; explicitly avoid {avoid}."
            ),
            "ko": (
                "{entity}에서는 {term}을 선택하고 {avoid}은 명시적으로 "
                "제외해 주세요."
            ),
            "es": (
                "Para {entity}, elige {term} y evita explícitamente {avoid}."
            ),
            "ja": (
                "{entity}では {term} を選び、{avoid} は明示的に除外してください。"
            ),
            "de": (
                "Wähle für {entity} {term} und schließe {avoid} ausdrücklich aus."
            ),
            "mixed": (
                "{entity}에서는 {term} 선택, {avoid}은 explicitly 제외."
            ),
        },
        "adjacent": {
            "en": (
                "Return the measured {term} for {entity}; do not substitute "
                "a proxy, estimate, or forecast."
            ),
            "ko": (
                "{entity}의 측정된 {term}을 반환하고 proxy, estimate, "
                "forecast로 대체하지 마세요."
            ),
            "es": (
                "Devuelve {term} medido para {entity}; no uses proxy, "
                "estimación ni forecast."
            ),
            "ja": (
                "{entity}の測定済み {term} を返し、proxy、estimate、"
                "forecast で代用しないでください。"
            ),
            "de": (
                "Gib den gemessenen Wert {term} für {entity} zurück; "
                "kein Proxy, Estimate oder Forecast."
            ),
            "mixed": (
                "{entity}의 measured {term}만 반환해. proxy/estimate/"
                "forecast는 제외."
            ),
        },
        "multi": {
            "en": (
                "Use {term} on {entity}; from that result proceed with {second}."
            ),
            "ko": (
                "{entity}에 {term}을 수행하고, 그 결과를 이어서 {second}에 "
                "사용해 주세요."
            ),
            "es": (
                "Aplica {term} a {entity} y continúa con {second} usando "
                "ese resultado."
            ),
            "ja": (
                "{entity}に {term} を実行し、その結果から {second} に進んでください。"
            ),
            "de": (
                "Führe {term} für {entity} aus und fahre mit dem Ergebnis "
                "mit {second} fort."
            ),
            "mixed": (
                "{entity}에 {term} 실행 후 그 result로 {second}까지 진행."
            ),
        },
        "unit": {
            "en": (
                "Return {term} for {entity} and preserve the unit {unit}."
            ),
            "ko": (
                "{entity}의 {term}을 반환하고 단위 {unit}를 그대로 유지해 주세요."
            ),
            "es": (
                "Devuelve {term} para {entity} conservando la unidad {unit}."
            ),
            "ja": (
                "{entity}の {term} を返し、単位 {unit} を保持してください。"
            ),
            "de": (
                "Gib {term} für {entity} zurück und behalte die Einheit "
                "{unit} bei."
            ),
            "mixed": (
                "{entity}의 {term} 반환, unit은 {unit} 그대로 유지."
            ),
        },
        "read": {
            "en": (
                "Inspect {entity} with {term}; this request must not mutate it."
            ),
            "ko": (
                "{entity}를 {term}으로 조회하되 이 요청에서는 변경하지 마세요."
            ),
            "es": (
                "Inspecciona {entity} con {term}; esta solicitud no debe "
                "modificarlo."
            ),
            "ja": (
                "{entity}を {term} で確認し、この要求では変更しないでください。"
            ),
            "de": (
                "Prüfe {entity} mit {term}; diese Anfrage darf nichts ändern."
            ),
            "mixed": (
                "{entity}를 {term}으로 inspect만 해. mutation은 금지."
            ),
        },
        "write": {
            "en": (
                "Change {entity} using {term}; this is not a read-only request."
            ),
            "ko": (
                "{entity}를 {term}으로 변경해 주세요. read-only 요청이 아닙니다."
            ),
            "es": (
                "Modifica {entity} usando {term}; no es una solicitud "
                "de solo lectura."
            ),
            "ja": (
                "{entity}を {term} で変更してください。read-only 要求ではありません。"
            ),
            "de": (
                "Ändere {entity} mit {term}; dies ist keine reine Leseanfrage."
            ),
            "mixed": (
                "{entity}는 {term}으로 change해. read-only 아님."
            ),
        },
    }
    return templates[kind][language].format(
        term=term,
        entity=entity,
        avoid=avoid,
        second=second,
        unit=unit,
    )


_CLEAR_ROUTES = (
    "assets.export",
    "jobs.status",
    "datasets.retrieve",
    "patents.search",
    "literature.search",
    "mechanics.elastic_modulus",
    "thermal.conductivity",
    "rheology.viscosity",
    "spectroscopy.raman_peak",
    "electrochem.capacity",
    "optics.refractive_index",
    "geometry.particle_diameter",
    "thermal.heat_capacity",
    "mechanics.hardness",
    "spectroscopy.absorbance",
)
_SIBLING_PAIRS = (
    ("jobs.restart", "jobs.cancel"),
    ("samples.update", "samples.get"),
    ("assets.archive", "assets.delete"),
    ("messages.send", "messages.draft"),
    ("datasets.search", "datasets.retrieve"),
    ("patents.retrieve", "patents.search"),
    ("literature.summarize", "literature.retrieve"),
    ("experiments.status", "experiments.create"),
    ("jobs.status", "jobs.cancel"),
    ("literature.retrieve", "literature.search"),
)
_ADJACENT_ROUTES = (
    "electrochem.capacity",
    "geometry.particle_diameter",
    "optics.refractive_index",
    "rheology.viscosity",
    "mechanics.elastic_modulus",
    "mechanics.hardness",
    "thermal.heat_capacity",
    "thermal.conductivity",
    "spectroscopy.absorbance",
    "spectroscopy.raman_peak",
)
_MULTI_PAIRS = (
    ("assets.archive", "assets.export"),
    ("messages.draft", "messages.send"),
    ("samples.get", "samples.update"),
    ("datasets.search", "datasets.retrieve"),
    ("patents.search", "patents.retrieve"),
    ("literature.search", "literature.retrieve"),
    ("literature.retrieve", "literature.summarize"),
    ("experiments.create", "experiments.status"),
)
_READ_WRITE_PAIRS = (
    ("experiments.status", "experiments.create"),
    ("assets.export", "assets.archive"),
    ("jobs.status", "jobs.restart"),
    ("jobs.status", "jobs.cancel"),
    ("samples.get", "samples.update"),
)
_NEAR_UNSUPPORTED = (
    "coefficient of thermal expansion",
    "fracture energy",
    "surface zeta potential",
    "advancing contact angle",
    "carrier Hall mobility",
    "thermoelectric Seebeck coefficient",
    "dielectric loss factor",
    "arithmetic surface roughness",
    "BET adsorption area",
    "mesopore distribution",
    "XRD crystallite width",
    "XPS core-level binding energy",
    "NMR resonance shift",
    "fluorescence decay lifetime",
    "glass-transition temperature",
    "fusion enthalpy",
    "tensile yield stress",
    "Poisson coefficient",
    "creep relaxation modulus",
    "torsional shear modulus",
    "electrochemical impedance Nyquist trace",
    "high-rate cycling capability",
    "round-trip coulombic efficiency",
    "patent prosecution status",
    "patent citation network",
    "dataset provenance lineage",
    "sample autoclave sterilization",
    "job queue priority",
    "restore a permanently deleted asset",
    "recall an already delivered message",
)
_OOD_TOPICS = (
    "outline a blues guitar solo",
    "write a four-line autumn poem",
    "recommend a defensive chess opening",
    "plan a weekend mountain trip",
    "explain the ending of Hamlet",
    "suggest a vegetarian soup",
    "name a fantasy kingdom",
    "summarize a basketball game",
    "teach a basic piano arpeggio",
    "draft a retirement toast",
    "compare pour-over coffee brewers",
    "recommend a historical novel",
    "invent a card-game mechanic",
    "write a short animal bedtime tale",
    "explain leading lines in photography",
    "suggest a bodyweight mobility routine",
    "create a breathing exercise",
    "name a fictional moon base",
    "write a limerick about snow",
    "suggest a sculpture museum route",
    "explain an offside rule",
    "recommend a documentary genre",
    "draft a graduation greeting",
    "suggest a balcony herb layout",
    "invent a citrus mocktail",
    "create a vocabulary drill",
    "explain a jazz piano voicing",
    "suggest a hiking packing list",
    "write a compact mystery premise",
    "recommend a charcoal drawing subject",
)


def build_confirmation_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    unit_routes = tuple(_UNIT_BY_ROUTE)

    for stratum in CONFIRMATION_STRATA:
        for language_index, language in enumerate(
            CONFIRMATION_LANGUAGES
        ):
            for ordinal in range(CONFIRMATION_TASKS_PER_CELL):
                index = language_index * CONFIRMATION_TASKS_PER_CELL + ordinal
                shifted = (index * 7 + 3) % 30
                task_id = (
                    f"v5-confirm-{stratum}-{language}-{ordinal + 1:02d}"
                )
                required: tuple[str, ...]

                if stratum == "clear_single_tool":
                    route = _CLEAR_ROUTES[
                        shifted % len(_CLEAR_ROUTES)
                    ]
                    query = _render(
                        language,
                        "clear",
                        term=_ROUTE_TERMS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "sibling_operation_ambiguity":
                    route, avoid = _SIBLING_PAIRS[
                        shifted % len(_SIBLING_PAIRS)
                    ]
                    query = _render(
                        language,
                        "sibling",
                        term=_ROUTE_TERMS[route],
                        avoid=_ROUTE_TERMS[avoid],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "semantically_adjacent_distractors":
                    route = _ADJACENT_ROUTES[
                        shifted % len(_ADJACENT_ROUTES)
                    ]
                    query = _render(
                        language,
                        "adjacent",
                        term=_ROUTE_TERMS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "multi_step_first_hop":
                    first, second = _MULTI_PAIRS[
                        shifted % len(_MULTI_PAIRS)
                    ]
                    query = _render(
                        language,
                        "multi",
                        term=_ROUTE_TERMS[first],
                        second=_ROUTE_TERMS[second],
                        entity=_entity(first, index),
                    )
                    required = (first, second)
                elif stratum == "typed_numeric_units":
                    route = unit_routes[
                        shifted % len(unit_routes)
                    ]
                    query = _render(
                        language,
                        "unit",
                        term=_ROUTE_TERMS[route],
                        unit=_UNIT_BY_ROUTE[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "read_write_siblings":
                    read_route, write_route = _READ_WRITE_PAIRS[
                        shifted % len(_READ_WRITE_PAIRS)
                    ]
                    route = (
                        read_route
                        if (index + ordinal) % 2 == 0
                        else write_route
                    )
                    query = _render(
                        language,
                        (
                            "read"
                            if route == read_route
                            else "write"
                        ),
                        term=_ROUTE_TERMS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "near_domain_unsupported":
                    term = _NEAR_UNSUPPORTED[index]
                    query = _render(
                        language,
                        "clear",
                        term=term,
                        entity=f"SPEC-{index + 901}",
                    )
                    required = ()
                else:
                    topic = _OOD_TOPICS[index]
                    wrappers = {
                        "en": (
                            "This is unrelated to registered research tools: "
                            f"{topic}."
                        ),
                        "ko": (
                            "등록된 연구 도구와 무관한 요청입니다: "
                            f"{topic}."
                        ),
                        "es": (
                            "Esta tarea no corresponde a las herramientas "
                            f"de investigación registradas: {topic}."
                        ),
                        "ja": (
                            "登録済み研究ツールとは無関係の依頼です: "
                            f"{topic}."
                        ),
                        "de": (
                            "Diese Aufgabe gehört nicht zu den registrierten "
                            f"Forschungswerkzeugen: {topic}."
                        ),
                        "mixed": (
                            "registered research tool 범위 밖 요청: "
                            f"{topic}."
                        ),
                    }
                    query = wrappers[language]
                    required = ()

                tasks.append(
                    {
                        "task_id": task_id,
                        "task_stratum": stratum,
                        "language": language,
                        "query": query,
                        "required_route_ids": list(required),
                    }
                )

    if len(tasks) != 240:
        raise RuntimeError(
            "confirmation task count drifted: "
            f"{len(tasks)}"
        )
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise RuntimeError(
            "confirmation semantic task IDs must be unique"
        )
    if len({task["query"] for task in tasks}) != len(tasks):
        raise RuntimeError(
            "confirmation query strings must be unique"
        )
    return tasks
