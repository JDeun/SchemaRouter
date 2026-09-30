"""Fresh confirmation surface for structural fixed Top-3 v4."""

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
from benchmarks.agent_utility_v5_structural_confirmation import (
    _ADJACENT_ROUTES,
    _CLEAR_ROUTES,
    _MULTI_PAIRS,
    _READ_WRITE_PAIRS,
    _ROUTE_TERMS,
    _SIBLING_PAIRS,
    _UNIT_BY_ROUTE,
)
from schemarouter import InMemoryRegistry, ToolSpec

FIXED3_CONFIRM_CATALOG_SIZES = CATALOG_SIZES
FIXED3_CONFIRM_LANGUAGES = LANGUAGES
FIXED3_CONFIRM_STRATA = STRATA
FIXED3_CONFIRM_TASKS_PER_CELL = TASKS_PER_CELL

_RESOURCES = (
    "literature", "patent", "dataset", "sample", "job", "message",
    "asset", "experiment", "raman", "absorbance", "conductivity",
    "heat_capacity", "hardness", "elasticity", "viscosity",
    "refraction", "particle_size", "capacity", "microscopy", "supplier",
    "shipment", "notebook", "workflow", "annotation", "invoice",
    "calendar", "spectrum", "composition", "batch", "recipe", "model",
    "checkpoint", "report", "citation", "organization", "workspace",
)
_ACTIONS = (
    "search", "retrieve", "summarize", "read", "update", "delete",
    "status", "cancel", "restart", "draft", "send", "archive",
    "export", "estimate", "forecast", "compare",
)
_PREFIXES = (
    "fallback", "secondary", "compat", "replica",
    "staging", "historical", "derived",
)


def _distractor(index: int) -> ToolSpec:
    resource = _RESOURCES[(index * 13 + 9) % len(_RESOURCES)]
    action = _ACTIONS[(index * 5 + 7) % len(_ACTIONS)]
    prefix = _PREFIXES[(index * 11 + 2) % len(_PREFIXES)]
    read_only = action in {
        "search", "retrieve", "summarize", "read", "status",
        "export", "estimate", "forecast", "compare",
    }
    return ToolSpec(
        name=f"{prefix}_{resource}_fx{index:03d}",
        description=(
            f"{prefix.title()} {resource} compatibility endpoint. "
            "It is not the canonical registered capability."
        ),
        endpoints=[
            _endpoint(
                action,
                (
                    f"{action.title()} {resource} records through a "
                    f"{prefix} compatibility path."
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
                            f"fixed3.{prefix}.{resource}.payload",
                            description="compatibility payload",
                        ),
                    )
                    if read_only
                    else ()
                ),
            )
        ],
    )


def build_fixed3_confirmation_registry(
    endpoint_count: int,
) -> InMemoryRegistry:
    if endpoint_count not in FIXED3_CONFIRM_CATALOG_SIZES:
        raise ValueError(
            f"unsupported fixed3 confirmation catalog size: {endpoint_count}"
        )

    registry = InMemoryRegistry()
    core = _core_tools()
    registry.update_many(core)
    core_count = sum(len(tool.endpoints) for tool in core)
    if core_count != 30:
        raise RuntimeError(
            f"fixed3 confirmation core endpoint count drifted: {core_count}"
        )

    for index in range(endpoint_count - core_count):
        registry.register(_distractor(index))

    actual = sum(
        len(tool.endpoints)
        for tool in registry.tools()
    )
    if actual != endpoint_count:
        raise RuntimeError(
            "fixed3 confirmation catalog endpoint count drifted: "
            f"expected={endpoint_count} actual={actual}"
        )
    return registry


def _entity(route: str, index: int) -> str:
    if route.startswith("literature."):
        prefix = "LITCHK"
    elif route.startswith("patents."):
        prefix = "PATCHK"
    elif route.startswith("datasets."):
        prefix = "DSCHK"
    elif route.startswith("jobs."):
        prefix = "JOBCHK"
    elif route.startswith("messages."):
        prefix = "MSGCHK"
    elif route.startswith("assets."):
        prefix = "ASTCHK"
    elif route.startswith("experiments."):
        prefix = "EXPCHK"
    elif route.startswith("electrochem."):
        prefix = "CELLCHK"
    else:
        prefix = "SPECHK"
    return f"{prefix}-{index + 1101}"


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
            "en": "Resolve {term} for {entity} with the primary registered tool.",
            "ko": "{entity}의 {term} 작업을 primary registered tool로 처리해 주세요.",
            "es": "Resuelve {term} para {entity} con la herramienta registrada principal.",
            "ja": "{entity} の {term} を主要な登録ツールで処理してください。",
            "de": "Bearbeite {term} für {entity} mit dem primären registrierten Werkzeug.",
            "mixed": "{entity}에서 primary registered tool로 {term}만 resolve해.",
        },
        "sibling": {
            "en": "For {entity}, execute {term}, specifically not {avoid}.",
            "ko": "{entity}에서는 {term}을 실행하고 {avoid}은 선택하지 마세요.",
            "es": "Para {entity}, ejecuta {term}, específicamente no {avoid}.",
            "ja": "{entity}では {term} を実行し、{avoid} は選ばないでください。",
            "de": "Führe für {entity} {term} aus, ausdrücklich nicht {avoid}.",
            "mixed": "{entity}: {term} execute, {avoid}은 not selected.",
        },
        "adjacent": {
            "en": (
                "Fetch the registered measured {term} for {entity}, "
                "not any surrogate prediction."
            ),
            "ko": "{entity}의 registered measured {term}을 가져오고 surrogate prediction은 제외하세요.",
            "es": "Obtén {term} medido y registrado para {entity}, no una predicción sustituta.",
            "ja": "{entity} の登録済み実測 {term} を取得し、代替予測は使わないでください。",
            "de": "Liefere den registrierten Messwert {term} für {entity}, keine Ersatzprognose.",
            "mixed": "{entity}의 registered measured {term}만 fetch. surrogate prediction 금지.",
        },
        "multi": {
            "en": "Start with {term} for {entity}; then continue the workflow with {second}.",
            "ko": "{entity}에 먼저 {term}을 수행하고 이후 workflow를 {second}으로 이어가세요.",
            "es": "Empieza con {term} para {entity} y continúa después con {second}.",
            "ja": "{entity}にまず {term} を実行し、その後 {second} に進んでください。",
            "de": "Beginne bei {entity} mit {term} und fahre danach mit {second} fort.",
            "mixed": "{entity}에 first {term}, 그 다음 workflow는 {second}.",
        },
        "unit": {
            "en": "Obtain {term} for {entity}; keep the reported unit exactly as {unit}.",
            "ko": "{entity}의 {term}을 구하고 reported unit은 정확히 {unit}로 유지하세요.",
            "es": "Obtén {term} para {entity} y conserva exactamente la unidad {unit}.",
            "ja": "{entity} の {term} を取得し、報告単位を正確に {unit} のままにしてください。",
            "de": "Ermittle {term} für {entity} und behalte exakt die Einheit {unit}.",
            "mixed": "{entity}의 {term} obtain, reported unit은 exact {unit}.",
        },
        "read": {
            "en": "Check {entity} via {term}; no state change is allowed.",
            "ko": "{entity}를 {term}으로 확인하되 state change는 허용하지 마세요.",
            "es": "Consulta {entity} mediante {term}; no se permite cambiar su estado.",
            "ja": "{entity} を {term} で確認し、状態変更は行わないでください。",
            "de": "Prüfe {entity} über {term}; eine Zustandsänderung ist nicht erlaubt.",
            "mixed": "{entity}는 {term}으로 check only; state change 금지.",
        },
        "write": {
            "en": "Apply {term} to {entity}; this request intentionally changes state.",
            "ko": "{entity}에 {term}을 적용하세요. 이 요청은 의도적으로 state를 변경합니다.",
            "es": "Aplica {term} a {entity}; esta solicitud cambia el estado intencionalmente.",
            "ja": "{entity} に {term} を適用してください。この要求は意図的に状態を変更します。",
            "de": "Wende {term} auf {entity} an; diese Anfrage ändert den Zustand absichtlich.",
            "mixed": "{entity}에 {term} apply. 이 요청은 intentionally state-changing.",
        },
    }
    return templates[kind][language].format(
        term=term,
        entity=entity,
        avoid=avoid,
        second=second,
        unit=unit,
    )


_NEAR_UNSUPPORTED = (
    "thermal diffusivity", "fracture toughness KIC", "streaming potential",
    "receding contact angle", "carrier concentration", "Peltier coefficient",
    "dielectric constant frequency sweep", "root mean square roughness",
    "Langmuir surface area", "micropore volume", "XRD lattice strain",
    "XPS Auger parameter", "solid-state NMR linewidth", "phosphorescence lifetime",
    "softening temperature", "crystallization enthalpy", "ultimate tensile strength",
    "bulk modulus", "stress relaxation spectrum", "torsional stiffness",
    "electrochemical Warburg coefficient", "rate retention at 10C",
    "voltage hysteresis", "patent opposition status", "patent inventor graph",
    "dataset access audit trail", "sample gamma sterilization",
    "job resource reservation", "recover an expunged asset",
    "withdraw a message after external delivery",
)
_OOD = (
    "outline a funk bass groove", "write a spring tanka",
    "recommend a beginner Go opening", "plan a city food walk",
    "explain the final scene of Othello", "suggest a lentil curry",
    "name a science-fiction guild", "summarize a tennis final",
    "teach a basic drum fill", "draft an anniversary toast",
    "compare espresso grinders", "recommend a travel memoir",
    "invent a dice-game mechanic", "write a short robot bedtime tale",
    "explain negative space in photography", "suggest a stretching circuit",
    "create a grounding exercise", "name a fictional observatory",
    "write a rhyme about fog", "suggest an architecture museum route",
    "explain a volleyball rotation", "recommend an animation genre",
    "draft a promotion greeting", "suggest an indoor succulent layout",
    "invent a ginger mocktail", "create a pronunciation drill",
    "explain a gospel piano turnaround", "suggest a cycling packing list",
    "write a compact spy premise", "recommend an ink drawing subject",
)


def build_fixed3_confirmation_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    unit_routes = tuple(_UNIT_BY_ROUTE)

    for stratum in FIXED3_CONFIRM_STRATA:
        for language_index, language in enumerate(
            FIXED3_CONFIRM_LANGUAGES
        ):
            for ordinal in range(FIXED3_CONFIRM_TASKS_PER_CELL):
                index = (
                    language_index * FIXED3_CONFIRM_TASKS_PER_CELL
                    + ordinal
                )
                shifted = (index * 11 + 5) % 30
                task_id = (
                    f"v5-fixed3-confirm-{stratum}-{language}-"
                    f"{ordinal + 1:02d}"
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
                        if shifted % 2 == 0
                        else write_route
                    )
                    query = _render(
                        language,
                        "read" if route == read_route else "write",
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
                        entity=f"UNKCHK-{index + 1301}",
                    )
                    required = ()
                else:
                    topic = _OOD[index]
                    wrappers = {
                        "en": f"Handle this non-research request: {topic}.",
                        "ko": f"연구 도구와 무관한 다음 요청을 처리해 주세요: {topic}.",
                        "es": f"Atiende esta solicitud no científica: {topic}.",
                        "ja": f"研究ツール外の次の依頼を処理してください: {topic}.",
                        "de": f"Bearbeite diese forschungsfremde Anfrage: {topic}.",
                        "mixed": f"research tool 범위 밖 요청: {topic}.",
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
            f"fixed3 confirmation task count drifted: {len(tasks)}"
        )
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise RuntimeError("fixed3 confirmation task ids must be unique")
    if len({task["query"] for task in tasks}) != len(tasks):
        raise RuntimeError("fixed3 confirmation queries must be unique")
    return tasks
