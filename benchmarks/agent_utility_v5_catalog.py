"""Fresh #430 adaptive-depth DEV catalog and 240-task surface.

This module is independent of #420/#423 and does not reuse #434 query text.
Each semantic task has exactly one language rendering.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    ToolSpec,
    UnitNormalizationSpec,
)

CATALOG_SIZES = (100, 250, 500)
LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
STRATA = (
    "clear_single_tool",
    "sibling_operation_ambiguity",
    "semantically_adjacent_distractors",
    "multi_step_first_hop",
    "typed_numeric_units",
    "read_write_siblings",
    "near_domain_unsupported",
    "out_of_domain",
)
TASKS_PER_CELL = 5


def _field(
    name: str,
    semantic_id: str,
    *,
    description: str,
    json_type: str = "string",
    unit: str | None = None,
    dimension: str | None = None,
) -> FieldSpec:
    normalization = None
    if unit is not None and dimension is not None:
        normalization = UnitNormalizationSpec(
            dimension=dimension,
            canonical_unit=unit,
        )
    return FieldSpec(
        name=name,
        semantic_id=semantic_id,
        description=description,
        json_schema={"type": json_type},
        unit=unit,
        unit_normalization=normalization,
    )


def _parameter(
    name: str,
    *,
    description: str,
    required: bool = True,
) -> ParameterSpec:
    return ParameterSpec(
        name=name,
        description=description,
        required=required,
        json_schema={"type": "string"},
    )


def _endpoint(
    name: str,
    description: str,
    *,
    read_only: bool,
    destructive: bool = False,
    parameters: Iterable[ParameterSpec] = (),
    fields: Iterable[FieldSpec] = (),
) -> EndpointSpec:
    return EndpointSpec(
        name=name,
        description=description,
        parameters=list(parameters),
        output_fields=list(fields),
        read_only=read_only,
        destructive=destructive,
    )


def _numeric_field(
    semantic_id: str,
    label: str,
    unit: str,
    dimension: str,
) -> FieldSpec:
    return _field(
        "value",
        semantic_id,
        description=label,
        json_type="number",
        unit=unit,
        dimension=dimension,
    )


def _core_tools() -> list[ToolSpec]:
    id_field = _field(
        "id",
        "resource.identifier",
        description="stable registered identifier",
    )
    return [
        ToolSpec(
            name="literature",
            description="Scientific literature discovery and document access",
            endpoints=[
                _endpoint(
                    "search",
                    "Search scientific literature by topic or keywords",
                    read_only=True,
                    parameters=(_parameter("query", description="literature search query"),),
                    fields=(id_field,),
                ),
                _endpoint(
                    "retrieve",
                    "Retrieve one literature document by identifier",
                    read_only=True,
                    parameters=(_parameter("document_id", description="document identifier"),),
                    fields=(
                        _field(
                            "text",
                            "literature.full_text",
                            description="full document text",
                        ),
                    ),
                ),
                _endpoint(
                    "summarize",
                    "Summarize one literature document by identifier",
                    read_only=True,
                    parameters=(_parameter("document_id", description="document identifier"),),
                    fields=(
                        _field(
                            "summary",
                            "literature.summary",
                            description="document summary",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="patents",
            description="Patent discovery and patent-record access",
            endpoints=[
                _endpoint(
                    "search",
                    "Search patent records by concept or assignee",
                    read_only=True,
                    parameters=(_parameter("query", description="patent search query"),),
                    fields=(id_field,),
                ),
                _endpoint(
                    "retrieve",
                    "Retrieve one patent record by patent identifier",
                    read_only=True,
                    parameters=(_parameter("patent_id", description="patent identifier"),),
                    fields=(_field("text", "patent.full_text", description="patent record text"),),
                ),
            ],
        ),
        ToolSpec(
            name="datasets",
            description="Research dataset discovery and retrieval",
            endpoints=[
                _endpoint(
                    "search",
                    "Search registered research datasets",
                    read_only=True,
                    parameters=(_parameter("query", description="dataset search query"),),
                    fields=(id_field,),
                ),
                _endpoint(
                    "retrieve",
                    "Retrieve metadata for one registered dataset",
                    read_only=True,
                    parameters=(_parameter("dataset_id", description="dataset identifier"),),
                    fields=(
                        _field(
                            "metadata",
                            "dataset.metadata",
                            description="dataset metadata",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="samples",
            description="Laboratory sample record lifecycle",
            endpoints=[
                _endpoint(
                    "get",
                    "Read one laboratory sample record without modifying it",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(id_field,),
                ),
                _endpoint(
                    "update",
                    "Update fields on one laboratory sample record",
                    read_only=False,
                    parameters=(
                        _parameter("sample_id", description="sample identifier"),
                        _parameter("patch", description="sample record patch"),
                    ),
                    fields=(id_field,),
                ),
                _endpoint(
                    "delete",
                    "Permanently delete one laboratory sample record",
                    read_only=False,
                    destructive=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                ),
            ],
        ),
        ToolSpec(
            name="jobs",
            description="Registered computation-job lifecycle",
            endpoints=[
                _endpoint(
                    "status",
                    "Read the current status of a computation job",
                    read_only=True,
                    parameters=(_parameter("job_id", description="job identifier"),),
                    fields=(_field("status", "job.status", description="job status"),),
                ),
                _endpoint(
                    "cancel",
                    "Cancel a running computation job",
                    read_only=False,
                    parameters=(_parameter("job_id", description="job identifier"),),
                ),
                _endpoint(
                    "restart",
                    "Restart a stopped computation job",
                    read_only=False,
                    parameters=(_parameter("job_id", description="job identifier"),),
                ),
            ],
        ),
        ToolSpec(
            name="messages",
            description="Research communication drafting and sending",
            endpoints=[
                _endpoint(
                    "draft",
                    "Create a message draft without sending it",
                    read_only=False,
                    parameters=(_parameter("body", description="message body"),),
                    fields=(id_field,),
                ),
                _endpoint(
                    "send",
                    "Send a research message to a recipient",
                    read_only=False,
                    parameters=(
                        _parameter("recipient", description="message recipient"),
                        _parameter("body", description="message body"),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="assets",
            description="Research asset archival, deletion, and export",
            endpoints=[
                _endpoint(
                    "archive",
                    "Archive a research asset reversibly",
                    read_only=False,
                    parameters=(_parameter("asset_id", description="asset identifier"),),
                ),
                _endpoint(
                    "delete",
                    "Permanently delete a research asset",
                    read_only=False,
                    destructive=True,
                    parameters=(_parameter("asset_id", description="asset identifier"),),
                ),
                _endpoint(
                    "export",
                    "Export a research asset as a portable file",
                    read_only=True,
                    parameters=(_parameter("asset_id", description="asset identifier"),),
                    fields=(_field("uri", "asset.export_uri", description="export file URI"),),
                ),
            ],
        ),
        ToolSpec(
            name="experiments",
            description="Experimental run creation and status tracking",
            endpoints=[
                _endpoint(
                    "create",
                    "Create a new experimental run",
                    read_only=False,
                    parameters=(_parameter("protocol_id", description="protocol identifier"),),
                    fields=(id_field,),
                ),
                _endpoint(
                    "status",
                    "Read current experimental run status",
                    read_only=True,
                    parameters=(_parameter("experiment_id", description="experiment identifier"),),
                    fields=(
                        _field(
                            "status",
                            "experiment.status",
                            description="experiment status",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="spectroscopy",
            description="Spectroscopy measurement service",
            endpoints=[
                _endpoint(
                    "raman_peak",
                    "Read Raman peak position for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "spectroscopy.raman_peak",
                            "Raman peak position",
                            "cm^-1",
                            "wavenumber",
                        ),
                    ),
                ),
                _endpoint(
                    "absorbance",
                    "Read optical absorbance for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "spectroscopy.absorbance",
                            "optical absorbance",
                            "AU",
                            "absorbance",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="thermal",
            description="Thermal-property measurement service",
            endpoints=[
                _endpoint(
                    "conductivity",
                    "Read thermal conductivity for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "thermal.conductivity",
                            "thermal conductivity",
                            "W/(m*K)",
                            "thermal_conductivity",
                        ),
                    ),
                ),
                _endpoint(
                    "heat_capacity",
                    "Read specific heat capacity for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "thermal.heat_capacity",
                            "specific heat capacity",
                            "J/(g*K)",
                            "specific_heat_capacity",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="mechanics",
            description="Mechanical-property measurement service",
            endpoints=[
                _endpoint(
                    "hardness",
                    "Read Vickers hardness for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "mechanics.hardness",
                            "Vickers hardness",
                            "HV",
                            "hardness",
                        ),
                    ),
                ),
                _endpoint(
                    "elastic_modulus",
                    "Read Young elastic modulus for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "mechanics.elastic_modulus",
                            "Young elastic modulus",
                            "GPa",
                            "elastic_modulus",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="rheology",
            description="Rheology measurement service",
            endpoints=[
                _endpoint(
                    "viscosity",
                    "Read dynamic viscosity for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "rheology.viscosity",
                            "dynamic viscosity",
                            "mPa*s",
                            "dynamic_viscosity",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="optics",
            description="Optical-property measurement service",
            endpoints=[
                _endpoint(
                    "refractive_index",
                    "Read refractive index for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "optics.refractive_index",
                            "refractive index",
                            "1",
                            "dimensionless",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="geometry",
            description="Geometric measurement service",
            endpoints=[
                _endpoint(
                    "particle_diameter",
                    "Read particle diameter for a sample",
                    read_only=True,
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _numeric_field(
                            "geometry.particle_diameter",
                            "particle diameter",
                            "nm",
                            "length",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="electrochem",
            description="Electrochemical measurement service",
            endpoints=[
                _endpoint(
                    "capacity",
                    "Read specific discharge capacity for a cell",
                    read_only=True,
                    parameters=(_parameter("cell_id", description="cell identifier"),),
                    fields=(
                        _numeric_field(
                            "electrochem.capacity",
                            "specific discharge capacity",
                            "mAh/g",
                            "specific_capacity",
                        ),
                    ),
                ),
            ],
        ),
    ]


_DISTRACTOR_RESOURCES = (
    "literature", "patent", "dataset", "sample", "job", "message", "asset",
    "experiment", "raman_peak", "absorbance", "thermal_conductivity",
    "heat_capacity", "hardness", "elastic_modulus", "viscosity",
    "refractive_index", "particle_diameter", "capacity", "microscopy",
    "supplier", "shipment", "notebook", "workflow", "annotation", "invoice",
    "calendar", "spectral_map", "composition", "batch", "recipe", "model",
    "checkpoint", "report", "citation", "organization", "workspace",
)
_DISTRACTOR_ACTIONS = (
    "search", "retrieve", "summarize", "read", "update", "delete", "status",
    "cancel", "restart", "draft", "send", "archive", "export", "estimate",
    "forecast", "compare",
)


def _distractor(index: int) -> ToolSpec:
    resource = _DISTRACTOR_RESOURCES[index % len(_DISTRACTOR_RESOURCES)]
    action = _DISTRACTOR_ACTIONS[(index * 7 + index // 5) % len(_DISTRACTOR_ACTIONS)]
    adjacent = index % 4 == 0
    qualifier = (
        "Semantically adjacent auxiliary capability; not the canonical registered "
        "research measurement or lifecycle route."
        if adjacent
        else "Auxiliary research-service capability."
    )
    read_only = action in {
        "search", "retrieve", "summarize", "read", "status", "export",
        "estimate", "forecast", "compare",
    }
    return ToolSpec(
        name=f"aux_{resource}_{index:03d}",
        description=f"Auxiliary {resource} service {index:03d}",
        endpoints=[
            _endpoint(
                action,
                f"{action.title()} {resource} records. {qualifier}",
                read_only=read_only,
                destructive=action == "delete",
                parameters=(
                    (_parameter("record_id", description="auxiliary record identifier"),)
                    if action not in {"search", "status"}
                    else ()
                ),
                fields=(
                    _field(
                        "value",
                        f"aux.{resource}.value",
                        description=f"auxiliary {resource} value",
                    ),
                )
                if read_only
                else (),
            ),
        ],
    )


def build_registry(endpoint_count: int) -> InMemoryRegistry:
    if endpoint_count not in CATALOG_SIZES:
        raise ValueError(f"unsupported catalog size: {endpoint_count}")
    registry = InMemoryRegistry()
    core = _core_tools()
    registry.update_many(core)
    core_count = sum(len(tool.endpoints) for tool in core)
    if core_count != 30:
        raise RuntimeError(f"adaptive core endpoint count drifted: {core_count}")
    for index in range(endpoint_count - core_count):
        registry.register(_distractor(index))
    actual = sum(len(tool.endpoints) for tool in registry.tools())
    if actual != endpoint_count:
        raise RuntimeError(
            f"catalog endpoint count drifted: expected={endpoint_count} actual={actual}"
        )
    return registry


_ROUTE_LABELS = {
    "literature.search": "literature search",
    "literature.retrieve": "literature document retrieval",
    "literature.summarize": "literature summarization",
    "patents.search": "patent search",
    "patents.retrieve": "patent record retrieval",
    "datasets.search": "dataset search",
    "datasets.retrieve": "dataset retrieval",
    "samples.get": "sample record read",
    "samples.update": "sample record update",
    "samples.delete": "sample record deletion",
    "jobs.status": "job status",
    "jobs.cancel": "job cancellation",
    "jobs.restart": "job restart",
    "messages.draft": "message drafting",
    "messages.send": "message sending",
    "assets.archive": "asset archiving",
    "assets.delete": "asset deletion",
    "assets.export": "asset export",
    "experiments.create": "experiment creation",
    "experiments.status": "experiment status",
    "spectroscopy.raman_peak": "Raman peak",
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


def _entity(route: str, index: int) -> str:
    if route.startswith(("literature.", "patents.")):
        prefix = "DOC" if route.startswith("literature.") else "PAT"
    elif route.startswith("jobs."):
        prefix = "JOB"
    elif route.startswith("messages."):
        prefix = "MSG"
    elif route.startswith("assets."):
        prefix = "AST"
    elif route.startswith("experiments."):
        prefix = "EXP"
    elif route.startswith("datasets."):
        prefix = "DS"
    elif route.startswith("electrochem."):
        prefix = "CELL"
    else:
        prefix = "S"
    return f"{prefix}-{index + 101}"


def _localized(lang: str, kind: str, **values: str) -> str:
    term = values.get("term", "")
    entity = values.get("entity", "")
    avoid = values.get("avoid", "")
    second = values.get("second", "")
    unit = values.get("unit", "")
    if kind == "single":
        templates = {
            "en": f"Read {term} for {entity}.",
            "ko": f"{entity}의 {term} 값을 조회해 주세요.",
            "es": f"Obtén {term} para {entity}.",
            "ja": f"{entity} の {term} を取得してください。",
            "de": f"Lies {term} für {entity} aus.",
            "mixed": f"{entity}의 {term} value를 read해줘.",
        }
    elif kind == "sibling":
        templates = {
            "en": f"Use {term} for {entity}; do not use {avoid}.",
            "ko": f"{entity}에는 {term}을 사용하고 {avoid}은 사용하지 마세요.",
            "es": f"Usa {term} para {entity}; no uses {avoid}.",
            "ja": f"{entity} には {term} を使い、{avoid} は使わないでください。",
            "de": f"Nutze {term} für {entity}; verwende nicht {avoid}.",
            "mixed": f"{entity}에는 {term}만 use하고 {avoid}은 쓰지 마.",
        }
    elif kind == "adjacent":
        templates = {
            "en": f"For {entity}, get the exact {term}; not a related proxy or forecast.",
            "ko": f"{entity}의 정확한 {term} 값을 가져오고, 유사 proxy나 forecast는 쓰지 마세요.",
            "es": f"Para {entity}, obtén {term} exacto; no un proxy ni forecast.",
            "ja": f"{entity} の正確な {term} を取得し、proxy や forecast は使わないでください。",
            "de": f"Ermittle für {entity} exakt {term}; keinen Proxy oder Forecast.",
            "mixed": f"{entity}의 exact {term}만 가져와. proxy/forecast 말고.",
        }
    elif kind == "multi":
        templates = {
            "en": f"First use {term} for {entity}, then use {second}.",
            "ko": f"먼저 {entity}에 {term}을 사용한 뒤 {second}을 수행해 주세요.",
            "es": f"Primero usa {term} para {entity} y después {second}.",
            "ja": f"まず {entity} に {term} を使い、その後 {second} を実行してください。",
            "de": f"Nutze zuerst {term} für {entity} und danach {second}.",
            "mixed": f"먼저 {entity}에 {term}, then {second}까지 해줘.",
        }
    elif kind == "unit":
        templates = {
            "en": f"Read {term} for {entity} in {unit}.",
            "ko": f"{entity}의 {term} 값을 {unit} 단위로 조회해 주세요.",
            "es": f"Obtén {term} de {entity} en {unit}.",
            "ja": f"{entity} の {term} を {unit} 単位で取得してください。",
            "de": f"Lies {term} für {entity} in {unit} aus.",
            "mixed": f"{entity}의 {term} 값을 {unit} unit으로 read해줘.",
        }
    elif kind == "read":
        templates = {
            "en": f"Read {entity} using {term}; do not modify it.",
            "ko": f"{entity}는 {term}으로 읽기만 하고 수정하지 마세요.",
            "es": f"Lee {entity} con {term}; no lo modifiques.",
            "ja": f"{entity} は {term} で読むだけにして、変更しないでください。",
            "de": f"Lies {entity} mit {term}; ändere es nicht.",
            "mixed": f"{entity}는 {term}으로 read only. modify하지 마.",
        }
    else:
        templates = {
            "en": f"Modify {entity} using {term}; do not just read it.",
            "ko": f"{entity}를 {term}으로 수정하고 읽기만 하지 마세요.",
            "es": f"Modifica {entity} con {term}; no te limites a leerlo.",
            "ja": f"{entity} を {term} で変更し、読むだけにしないでください。",
            "de": f"Ändere {entity} mit {term}; lies es nicht nur.",
            "mixed": f"{entity}는 {term}으로 modify해. read only 말고.",
        }
    return templates[lang]


_SINGLE_ROUTES = (
    "spectroscopy.raman_peak",
    "spectroscopy.absorbance",
    "thermal.conductivity",
    "thermal.heat_capacity",
    "mechanics.hardness",
    "mechanics.elastic_modulus",
    "rheology.viscosity",
    "optics.refractive_index",
    "geometry.particle_diameter",
    "electrochem.capacity",
    "literature.search",
    "patents.search",
    "datasets.retrieve",
    "jobs.status",
    "assets.export",
)
_SIBLING_PAIRS = (
    ("literature.retrieve", "literature.search"),
    ("literature.summarize", "literature.retrieve"),
    ("patents.retrieve", "patents.search"),
    ("datasets.retrieve", "datasets.search"),
    ("messages.draft", "messages.send"),
    ("assets.archive", "assets.delete"),
    ("jobs.status", "jobs.cancel"),
    ("samples.get", "samples.update"),
    ("experiments.status", "experiments.create"),
    ("jobs.restart", "jobs.cancel"),
)
_ADJACENT_ROUTES = (
    "spectroscopy.raman_peak",
    "spectroscopy.absorbance",
    "thermal.conductivity",
    "thermal.heat_capacity",
    "mechanics.hardness",
    "mechanics.elastic_modulus",
    "rheology.viscosity",
    "optics.refractive_index",
    "geometry.particle_diameter",
    "electrochem.capacity",
)
_MULTI_PAIRS = (
    ("literature.search", "literature.retrieve"),
    ("literature.retrieve", "literature.summarize"),
    ("patents.search", "patents.retrieve"),
    ("datasets.search", "datasets.retrieve"),
    ("samples.get", "samples.update"),
    ("messages.draft", "messages.send"),
    ("assets.archive", "assets.export"),
    ("experiments.create", "experiments.status"),
)
_READ_WRITE_PAIRS = (
    ("samples.get", "samples.update"),
    ("jobs.status", "jobs.cancel"),
    ("messages.draft", "messages.send"),
    ("assets.export", "assets.archive"),
    ("experiments.status", "experiments.create"),
)
_NEAR_UNSUPPORTED = (
    "fracture toughness", "thermal expansion coefficient", "zeta potential",
    "contact angle", "Hall mobility", "Seebeck coefficient",
    "dielectric loss tangent", "surface roughness Ra", "BET surface area",
    "pore size distribution", "crystallite size from XRD", "XPS binding energy",
    "NMR chemical shift", "fluorescence lifetime", "glass transition temperature",
    "melting enthalpy", "yield strength", "Poisson ratio", "creep compliance",
    "shear modulus", "electrochemical impedance spectrum", "C-rate capability",
    "coulombic efficiency", "patent legal status", "patent family graph",
    "dataset lineage graph", "sample sterilization", "job priority change",
    "asset restore after deletion", "message delivery recall",
)
_OOD_TOPICS = (
    "compose a jazz chord progression", "write a haiku about winter",
    "recommend a chess opening", "plan a three-day beach vacation",
    "explain the plot of Macbeth", "suggest a pasta recipe",
    "design a fantasy character name", "summarize a football match",
    "teach a beginner guitar riff", "draft a wedding toast",
    "compare two coffee brewing methods", "recommend a mystery novel",
    "invent a board-game rule", "write a bedtime story",
    "explain a photography composition trick", "suggest a home workout",
    "create a meditation prompt", "name a fictional spaceship",
    "write a limerick about rain", "suggest a museum itinerary",
    "explain a baseball rule", "recommend a film genre",
    "draft a birthday greeting", "suggest a garden layout",
    "invent a mocktail recipe", "create a language-learning exercise",
    "explain a piano voicing", "suggest a camping checklist",
    "write a short detective premise", "recommend a watercolor subject",
)


def build_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for stratum in STRATA:
        for language_index, language in enumerate(LANGUAGES):
            for ordinal in range(TASKS_PER_CELL):
                index = language_index * TASKS_PER_CELL + ordinal
                task_id = f"v5-{stratum}-{language}-{ordinal + 1:02d}"
                required: tuple[str, ...]
                if stratum == "clear_single_tool":
                    route = _SINGLE_ROUTES[index % len(_SINGLE_ROUTES)]
                    query = _localized(
                        language,
                        "single",
                        term=_ROUTE_LABELS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "sibling_operation_ambiguity":
                    route, avoid = _SIBLING_PAIRS[index % len(_SIBLING_PAIRS)]
                    query = _localized(
                        language,
                        "sibling",
                        term=_ROUTE_LABELS[route],
                        avoid=_ROUTE_LABELS[avoid],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "semantically_adjacent_distractors":
                    route = _ADJACENT_ROUTES[index % len(_ADJACENT_ROUTES)]
                    query = _localized(
                        language,
                        "adjacent",
                        term=_ROUTE_LABELS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "multi_step_first_hop":
                    first, second = _MULTI_PAIRS[index % len(_MULTI_PAIRS)]
                    query = _localized(
                        language,
                        "multi",
                        term=_ROUTE_LABELS[first],
                        second=_ROUTE_LABELS[second],
                        entity=_entity(first, index),
                    )
                    required = (first, second)
                elif stratum == "typed_numeric_units":
                    route = tuple(_UNIT_BY_ROUTE)[index % len(_UNIT_BY_ROUTE)]
                    query = _localized(
                        language,
                        "unit",
                        term=_ROUTE_LABELS[route],
                        unit=_UNIT_BY_ROUTE[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "read_write_siblings":
                    read_route, write_route = _READ_WRITE_PAIRS[
                        index % len(_READ_WRITE_PAIRS)
                    ]
                    route = read_route if index % 2 == 0 else write_route
                    query = _localized(
                        language,
                        "read" if route == read_route else "write",
                        term=_ROUTE_LABELS[route],
                        entity=_entity(route, index),
                    )
                    required = (route,)
                elif stratum == "near_domain_unsupported":
                    term = _NEAR_UNSUPPORTED[index]
                    query = _localized(
                        language,
                        "single",
                        term=term,
                        entity=f"S-{index + 401}",
                    )
                    required = ()
                else:
                    topic = _OOD_TOPICS[index]
                    wrappers = {
                        "en": f"Please {topic}.",
                        "ko": f"다음 작업을 해 주세요: {topic}.",
                        "es": f"Por favor, realiza esta tarea: {topic}.",
                        "ja": f"次の作業をしてください: {topic}.",
                        "de": f"Bitte erledige diese Aufgabe: {topic}.",
                        "mixed": f"이건 tool task 아님: {topic}.",
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
        raise RuntimeError(f"adaptive DEV task count drifted: {len(tasks)}")
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise RuntimeError("adaptive DEV task IDs must be unique")
    if len({task["query"] for task in tasks}) != len(tasks):
        raise RuntimeError("adaptive DEV query strings must be unique")
    return tasks
