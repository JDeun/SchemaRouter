"""Fresh independent confirmation surface for structural fixed K=3.

The surface shares only the canonical 30 registered capability routes with prior
surfaces. Query text and auxiliary route identities are freshly generated.
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
from benchmarks.agent_utility_v5_structural_confirmation import (
    _ROUTE_TERMS,
    _UNIT_BY_ROUTE,
)
from schemarouter import InMemoryRegistry, ToolSpec

CONFIRMATION_CATALOG_SIZES = CATALOG_SIZES
CONFIRMATION_LANGUAGES = LANGUAGES
CONFIRMATION_STRATA = STRATA
CONFIRMATION_TASKS_PER_CELL = TASKS_PER_CELL

_FRESH_RESOURCES = (
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
    "thermal",
    "calorimetry",
    "hardness",
    "modulus",
    "rheology",
    "optical",
    "particle",
    "electrochemical",
    "microscopy",
    "vendor",
    "logistics",
    "labbook",
    "pipeline",
    "label",
    "billing",
    "scheduler",
    "spectrum",
    "formula",
    "lot",
    "protocol",
    "surrogate",
    "snapshot",
    "brief",
    "reference",
    "tenant",
    "project",
)
_FRESH_ACTIONS = (
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
_FRESH_PREFIXES = (
    "audit",
    "sandbox",
    "replica",
    "staging",
    "observer",
    "fallback",
    "preview",
)


def _fresh_distractor(index: int) -> ToolSpec:
    resource = _FRESH_RESOURCES[
        (index * 13 + 11) % len(_FRESH_RESOURCES)
    ]
    action = _FRESH_ACTIONS[
        (index * 7 + 5) % len(_FRESH_ACTIONS)
    ]
    prefix = _FRESH_PREFIXES[
        (index * 5 + 2) % len(_FRESH_PREFIXES)
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
        name=f"{prefix}_{resource}_check_{index:03d}",
        description=(
            f"{prefix.title()}-only {resource} verification interface. "
            "It is not the canonical registered research capability."
        ),
        endpoints=[
            _endpoint(
                action,
                (
                    f"{action.title()} {resource} verification data through "
                    f"the {prefix} interface."
                ),
                read_only=read_only,
                destructive=action == "delete",
                parameters=(
                    (
                        _parameter(
                            "verification_id",
                            description="verification record identifier",
                        ),
                    )
                    if action not in {"search", "status"}
                    else ()
                ),
                fields=(
                    (
                        _field(
                            "verification_payload",
                            f"verify.{prefix}.{resource}.payload",
                            description="noncanonical verification payload",
                        ),
                    )
                    if read_only
                    else ()
                ),
            )
        ],
    )


def build_fixed_k3_confirmation_registry(
    endpoint_count: int,
) -> InMemoryRegistry:
    if endpoint_count not in CONFIRMATION_CATALOG_SIZES:
        raise ValueError(
            f"unsupported fixed-K3 confirmation size: {endpoint_count}"
        )

    registry = InMemoryRegistry()
    core = _core_tools()
    registry.update_many(core)
    core_count = sum(len(tool.endpoints) for tool in core)
    if core_count != 30:
        raise RuntimeError(
            f"fixed-K3 canonical endpoint count drifted: {core_count}"
        )

    for index in range(endpoint_count - core_count):
        registry.register(_fresh_distractor(index))

    actual = sum(
        len(tool.endpoints)
        for tool in registry.tools()
    )
    if actual != endpoint_count:
        raise RuntimeError(
            f"fixed-K3 catalog drifted: {actual} != {endpoint_count}"
        )
    return registry


def _entity(route: str, index: int) -> str:
    if route.startswith("literature."):
        prefix = "PAPER"
    elif route.startswith("patents."):
        prefix = "CLAIM"
    elif route.startswith("datasets."):
        prefix = "CORPUS"
    elif route.startswith("jobs."):
        prefix = "TASK"
    elif route.startswith("messages."):
        prefix = "MEMO"
    elif route.startswith("assets."):
        prefix = "FILE"
    elif route.startswith("experiments."):
        prefix = "RUN"
    elif route.startswith("electrochem."):
        prefix = "CELL"
    else:
        prefix = "MAT"
    return f"{prefix}-K3-{index + 1201}"


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
            "en": "Resolve {term} for {entity} through the canonical registered route.",
            "ko": "{entity}의 {term}을 canonical 등록 경로로 확인해 주세요.",
            "es": "Resuelve {term} para {entity} mediante la ruta canónica registrada.",
            "ja": "{entity} の {term} を canonical 登録ルートで確認してください。",
            "de": "Bestimme {term} für {entity} über die kanonisch registrierte Route.",
            "mixed": "{entity}의 {term}을 canonical registered route로 resolve해.",
        },
        "sibling": {
            "en": "For {entity}, perform {term}; the sibling action {avoid} is not requested.",
            "ko": "{entity}에는 {term}을 수행하고 sibling action인 {avoid}은 선택하지 마세요.",
            "es": "Para {entity}, ejecuta {term}; no se solicita la acción hermana {avoid}.",
            "ja": "{entity} では {term} を実行し、sibling action の {avoid} は選ばないでください。",
            "de": (
                "Führe für {entity} {term} aus; die Schwesteraktion "
                "{avoid} ist nicht angefordert."
            ),
            "mixed": "{entity}에는 {term} 수행. sibling {avoid}은 not requested.",
        },
        "adjacent": {
            "en": (
                "Fetch the registered measured {term} for {entity}, "
                "excluding surrogate or predicted alternatives."
            ),
            "ko": "{entity}의 등록된 측정 {term}을 가져오고 surrogate나 prediction 대안은 제외해 주세요.",
            "es": (
                "Obtén {term} medido y registrado para {entity}, "
                "excluyendo alternativas estimadas."
            ),
            "ja": "{entity} の登録済み測定 {term} を取得し、surrogate や予測値は除外してください。",
            "de": (
                "Hole den registrierten Messwert {term} für {entity}; "
                "Surrogat- oder Prognosewerte ausschließen."
            ),
            "mixed": "{entity}의 registered measured {term}만 fetch. surrogate/predicted 제외.",
        },
        "multi": {
            "en": (
                "Begin with {term} for {entity}, then continue to "
                "{second} using the observed result."
            ),
            "ko": "{entity}에서 먼저 {term}을 수행한 뒤 관측 결과를 이용해 {second}로 이어가 주세요.",
            "es": (
                "Empieza con {term} para {entity} y continúa con "
                "{second} usando el resultado observado."
            ),
            "ja": "{entity} でまず {term} を実行し、その観測結果を使って {second} に進んでください。",
            "de": (
                "Beginne bei {entity} mit {term} und fahre mit dem "
                "beobachteten Ergebnis zu {second} fort."
            ),
            "mixed": "{entity}에서 first {term}, observed result로 then {second}.",
        },
        "unit": {
            "en": "Return the registered {term} for {entity}; keep its value expressed in {unit}.",
            "ko": "{entity}의 등록된 {term}을 반환하고 값의 단위는 {unit}로 유지해 주세요.",
            "es": "Devuelve {term} registrado para {entity} y conserva la unidad {unit}.",
            "ja": "{entity} の登録済み {term} を返し、単位は {unit} のままにしてください。",
            "de": "Gib den registrierten Wert {term} für {entity} in der Einheit {unit} zurück.",
            "mixed": "{entity}의 registered {term} 반환, value unit은 {unit} 유지.",
        },
        "read": {
            "en": "Read {entity} via {term}; no state-changing operation is authorized.",
            "ko": "{entity}를 {term}으로 읽고 상태 변경 작업은 수행하지 마세요.",
            "es": (
                "Lee {entity} mediante {term}; no se autoriza ninguna "
                "operación que cambie estado."
            ),
            "ja": "{entity} を {term} で読み取り、状態変更操作は実行しないでください。",
            "de": "Lies {entity} über {term}; keine zustandsändernde Operation ist autorisiert.",
            "mixed": "{entity}는 {term}으로 read. state-changing operation은 금지.",
        },
        "write": {
            "en": "Apply {term} to {entity}; a read-only lookup is insufficient.",
            "ko": "{entity}에 {term}을 적용해 주세요. read-only 조회만으로는 부족합니다.",
            "es": "Aplica {term} a {entity}; una consulta de solo lectura no es suficiente.",
            "ja": "{entity} に {term} を適用してください。read-only の参照だけでは不十分です。",
            "de": "Wende {term} auf {entity} an; eine reine Leseabfrage reicht nicht aus.",
            "mixed": "{entity}에 {term} apply. read-only lookup만으로는 insufficient.",
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
    "mechanics.hardness",
    "spectroscopy.absorbance",
    "literature.retrieve",
    "datasets.search",
    "jobs.status",
    "assets.export",
    "thermal.heat_capacity",
    "geometry.particle_diameter",
    "optics.refractive_index",
    "electrochem.capacity",
    "mechanics.elastic_modulus",
    "rheology.viscosity",
    "thermal.conductivity",
    "spectroscopy.raman_peak",
    "patents.retrieve",
)
_SIBLING_PAIRS = (
    ("samples.get", "samples.update"),
    ("jobs.cancel", "jobs.restart"),
    ("assets.delete", "assets.archive"),
    ("messages.draft", "messages.send"),
    ("literature.search", "literature.retrieve"),
    ("patents.search", "patents.retrieve"),
    ("datasets.search", "datasets.retrieve"),
    ("experiments.create", "experiments.status"),
    ("literature.summarize", "literature.retrieve"),
    ("jobs.status", "jobs.cancel"),
)
_ADJACENT_ROUTES = (
    "mechanics.hardness",
    "mechanics.elastic_modulus",
    "thermal.conductivity",
    "thermal.heat_capacity",
    "spectroscopy.raman_peak",
    "spectroscopy.absorbance",
    "rheology.viscosity",
    "optics.refractive_index",
    "geometry.particle_diameter",
    "electrochem.capacity",
)
_MULTI_PAIRS = (
    ("datasets.search", "datasets.retrieve"),
    ("literature.search", "literature.retrieve"),
    ("patents.search", "patents.retrieve"),
    ("literature.retrieve", "literature.summarize"),
    ("samples.get", "samples.update"),
    ("messages.draft", "messages.send"),
    ("experiments.create", "experiments.status"),
    ("assets.archive", "assets.export"),
)
_READ_WRITE_PAIRS = (
    ("samples.get", "samples.update"),
    ("jobs.status", "jobs.cancel"),
    ("jobs.status", "jobs.restart"),
    ("assets.export", "assets.archive"),
    ("experiments.status", "experiments.create"),
)
_NEAR_UNSUPPORTED = (
    "thermal diffusivity",
    "plane-strain fracture toughness",
    "electrophoretic mobility",
    "receding wetting angle",
    "carrier concentration",
    "Peltier coefficient",
    "dielectric constant at frequency",
    "root-mean-square surface roughness",
    "Langmuir surface area",
    "micropore volume distribution",
    "XRD lattice strain",
    "XPS atomic concentration",
    "solid-state NMR linewidth",
    "photoluminescence quantum yield",
    "softening temperature",
    "latent heat of crystallization",
    "ultimate tensile strength",
    "bulk modulus",
    "stress relaxation time",
    "storage shear modulus",
    "charge-transfer resistance",
    "rate retention after cycling",
    "energy efficiency",
    "patent claim chart",
    "patent assignment history",
    "dataset checksum lineage",
    "sample freeze-drying protocol",
    "job resource quota",
    "undelete a purged asset",
    "withdraw a message after confirmed delivery",
)
_OOD_TOPICS = (
    "write a synthwave bass line",
    "compose a five-line spring poem",
    "suggest a chess endgame exercise",
    "plan a city walking holiday",
    "explain a scene from King Lear",
    "suggest a lentil dinner",
    "invent a science-fiction surname",
    "summarize a volleyball match",
    "teach a fingerstyle guitar pattern",
    "draft a best-man joke",
    "compare espresso grinders",
    "recommend a biography",
    "invent a dice-game scoring rule",
    "write a robot bedtime story",
    "explain portrait lighting",
    "suggest a stretching circuit",
    "create a focus exercise",
    "name a fictional research vessel",
    "write a short poem about fog",
    "suggest an architecture museum route",
    "explain a tennis tie-break",
    "recommend an animation genre",
    "draft a promotion congratulations message",
    "suggest an indoor plant layout",
    "invent a ginger mocktail",
    "create a pronunciation drill",
    "explain a gospel piano voicing",
    "suggest a cycling packing list",
    "write a courtroom mystery premise",
    "recommend an ink sketch subject",
)


def build_fixed_k3_confirmation_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    unit_routes = tuple(_UNIT_BY_ROUTE)

    for stratum in CONFIRMATION_STRATA:
        for language_index, language in enumerate(
            CONFIRMATION_LANGUAGES
        ):
            for ordinal in range(CONFIRMATION_TASKS_PER_CELL):
                index = (
                    language_index * CONFIRMATION_TASKS_PER_CELL
                    + ordinal
                )
                shifted = (index * 11 + 5) % 30
                task_id = (
                    f"v5-k3-confirm-{stratum}-{language}-"
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
                        write_route
                        if (index + ordinal) % 2
                        else read_route
                    )
                    query = _render(
                        language,
                        "write" if route == write_route else "read",
                        term=_ROUTE_TERMS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "near_domain_unsupported":
                    query = _render(
                        language,
                        "clear",
                        term=_NEAR_UNSUPPORTED[index],
                        entity=f"MAT-K3-{index + 1501}",
                    )
                    required = ()
                else:
                    topic = _OOD_TOPICS[index]
                    wrappers = {
                        "en": f"Outside the registered research-tool scope: {topic}.",
                        "ko": f"등록된 연구 도구 범위 밖 요청: {topic}.",
                        "es": f"Fuera del alcance de las herramientas registradas: {topic}.",
                        "ja": f"登録済み研究ツールの対象外です: {topic}.",
                        "de": f"Außerhalb des registrierten Forschungswerkzeug-Bereichs: {topic}.",
                        "mixed": f"registered tool scope 밖: {topic}.",
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
            f"fixed-K3 confirmation task count drifted: {len(tasks)}"
        )
    if len({task["task_id"] for task in tasks}) != 240:
        raise RuntimeError("fixed-K3 task IDs must be unique")
    if len({task["query"] for task in tasks}) != 240:
        raise RuntimeError("fixed-K3 queries must be unique")
    return tasks
