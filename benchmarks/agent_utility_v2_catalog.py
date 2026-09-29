"""Fresh DEV-only representation-ablation surface for #434.

The confirmation surface is deliberately not generated here.  It remains unopened until a
representation candidate is frozen, as required by the preregistration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    ToolSpec,
    UnitNormalizationSpec,
)

CATALOG_SIZES = (100, 250, 500, 1000)
K_VALUES = (1, 3, 5, 10)
LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")
STRATA = (
    "single_tool_exact",
    "two_step_composition",
    "three_step_composition",
    "sibling_operation_ambiguity",
    "same_field_name_different_semantic_id",
    "compatible_vs_incompatible_units",
    "read_vs_write_siblings",
    "destructive_vs_non_destructive_siblings",
    "implicit_or_omitted_parameter",
    "naturalistic_ambiguous_request",
    "near_domain_unsupported",
    "out_of_domain",
)


@dataclass(frozen=True)
class RepresentationTask:
    semantic_task_id: str
    stratum: str
    queries: dict[str, str]
    required_routes: tuple[str, ...]
    supported: bool


def _queries(en: str) -> dict[str, str]:
    """Render one semantic request in six fixed language surfaces.

    Technical nouns stay in English where that is common in software/tooling usage.  The
    surrounding request language changes deterministically.  These are development renderings,
    not the later held-out multilingual generalization surface from #432.
    """

    return {
        "en": en,
        "ko": f"다음 요청을 처리해 주세요: {en}",
        "es": f"Resuelve esta solicitud: {en}",
        "ja": f"次の依頼を処理してください: {en}",
        "de": f"Bearbeite diese Anfrage: {en}",
        "mixed": f"이 요청 처리해줘 / please: {en}",
    }


def _task(
    task_id: str,
    stratum: str,
    en: str,
    *routes: str,
    supported: bool = True,
) -> RepresentationTask:
    return RepresentationTask(
        semantic_task_id=task_id,
        stratum=stratum,
        queries=_queries(en),
        required_routes=tuple(routes),
        supported=supported,
    )


def _field(
    name: str,
    semantic_id: str,
    *,
    description: str,
    json_type: str = "string",
    unit: str | None = None,
    dimension: str | None = None,
    canonical_unit: str | None = None,
) -> FieldSpec:
    normalization = None
    if unit is not None and dimension is not None and canonical_unit is not None:
        normalization = UnitNormalizationSpec(
            dimension=dimension,
            canonical_unit=canonical_unit,
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
    json_type: str = "string",
) -> ParameterSpec:
    return ParameterSpec(
        name=name,
        description=description,
        required=required,
        json_schema={"type": json_type},
    )


def _endpoint(
    name: str,
    description: str,
    *,
    parameters: tuple[ParameterSpec, ...] = (),
    fields: tuple[FieldSpec, ...] = (),
    read_only: bool,
    destructive: bool = False,
) -> EndpointSpec:
    return EndpointSpec(
        name=name,
        description=description,
        parameters=list(parameters),
        output_fields=list(fields),
        read_only=read_only,
        destructive=destructive,
    )


def _core_tools() -> list[ToolSpec]:
    item_id = _field(
        "id",
        "resource.identifier",
        description="stable resource identifier",
    )
    value_elastic = _field(
        "value",
        "materials.elastic_modulus",
        description="Young modulus value",
        json_type="number",
        unit="GPa",
        dimension="elastic_modulus",
        canonical_unit="GPa",
    )
    value_resistance = _field(
        "value",
        "electrical.resistance",
        description="electrical resistance value",
        json_type="number",
        unit="ohm",
        dimension="electrical_resistance",
        canonical_unit="ohm",
    )
    value_temperature = _field(
        "value",
        "environment.temperature",
        description="temperature value",
        json_type="number",
        unit="K",
        dimension="temperature",
        canonical_unit="K",
    )
    value_ph = _field(
        "value",
        "chemistry.ph",
        description="pH value",
        json_type="number",
    )
    value_quote = _field(
        "value",
        "finance.market_price",
        description="market price value",
        json_type="number",
        unit="USD",
        dimension="currency",
        canonical_unit="USD",
    )

    return [
        ToolSpec(
            name="materials",
            description="Typed materials-property reference service",
            provider="representation_dev",
            access_mode="python",
            endpoints=[
                _endpoint(
                    "elastic_modulus",
                    "Read Young modulus for a material",
                    parameters=(_parameter("material_id", description="material identifier"),),
                    fields=(value_elastic,),
                    read_only=True,
                ),
                _endpoint(
                    "thermal_conductivity",
                    "Read thermal conductivity for a material",
                    parameters=(_parameter("material_id", description="material identifier"),),
                    fields=(
                        _field(
                            "value",
                            "materials.thermal_conductivity",
                            description="thermal conductivity value",
                            json_type="number",
                            unit="W/(m*K)",
                            dimension="thermal_conductivity",
                            canonical_unit="W/(m*K)",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "band_gap",
                    "Read electronic band gap for a material",
                    parameters=(_parameter("material_id", description="material identifier"),),
                    fields=(
                        _field(
                            "value",
                            "materials.band_gap",
                            description="electronic band gap value",
                            json_type="number",
                            unit="eV",
                            dimension="energy",
                            canonical_unit="eV",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "density",
                    "Read mass density for a material",
                    parameters=(_parameter("material_id", description="material identifier"),),
                    fields=(
                        _field(
                            "value",
                            "materials.density",
                            description="mass density value",
                            json_type="number",
                            unit="g/cm3",
                            dimension="density",
                            canonical_unit="g/cm3",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "formation_energy",
                    "Read formation energy per atom",
                    parameters=(_parameter("material_id", description="material identifier"),),
                    fields=(
                        _field(
                            "value",
                            "materials.formation_energy_per_atom",
                            description="formation energy per atom",
                            json_type="number",
                            unit="eV/atom",
                            dimension="energy_per_atom",
                            canonical_unit="eV/atom",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="electrical",
            description="Electrical measurement service",
            endpoints=[
                _endpoint(
                    "resistance",
                    "Read electrical resistance",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(value_resistance,),
                    read_only=True,
                ),
                _endpoint(
                    "capacitance",
                    "Read electrical capacitance",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "electrical.capacitance",
                            description="electrical capacitance value",
                            json_type="number",
                            unit="F",
                            dimension="capacitance",
                            canonical_unit="F",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "conductivity",
                    "Read electrical conductivity",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "electrical.conductivity",
                            description="electrical conductivity value",
                            json_type="number",
                            unit="S/m",
                            dimension="electrical_conductivity",
                            canonical_unit="S/m",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="environment",
            description="Environmental sensor service",
            endpoints=[
                _endpoint(
                    "temperature",
                    "Read temperature from a sensor",
                    parameters=(_parameter("sensor_id", description="sensor identifier"),),
                    fields=(value_temperature,),
                    read_only=True,
                ),
                _endpoint(
                    "pressure",
                    "Read pressure from a sensor",
                    parameters=(_parameter("sensor_id", description="sensor identifier"),),
                    fields=(
                        _field(
                            "value",
                            "environment.pressure",
                            description="pressure value",
                            json_type="number",
                            unit="kPa",
                            dimension="pressure",
                            canonical_unit="kPa",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "humidity",
                    "Read relative humidity from a sensor",
                    parameters=(_parameter("sensor_id", description="sensor identifier"),),
                    fields=(
                        _field(
                            "value",
                            "environment.relative_humidity",
                            description="relative humidity value",
                            json_type="number",
                            unit="%",
                            dimension="relative_humidity",
                            canonical_unit="%",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="chemistry",
            description="Chemical measurement service",
            endpoints=[
                _endpoint(
                    "ph",
                    "Read pH for a chemical sample",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(value_ph,),
                    read_only=True,
                ),
                _endpoint(
                    "concentration",
                    "Read solute concentration",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "chemistry.concentration",
                            description="molar concentration value",
                            json_type="number",
                            unit="mol/L",
                            dimension="concentration",
                            canonical_unit="mol/L",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "viscosity",
                    "Read dynamic viscosity",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "chemistry.dynamic_viscosity",
                            description="dynamic viscosity value",
                            json_type="number",
                            unit="mPa*s",
                            dimension="dynamic_viscosity",
                            canonical_unit="mPa*s",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="geometry",
            description="Geometric measurement service with explicit units",
            endpoints=[
                _endpoint(
                    "particle_diameter_nm",
                    "Read particle diameter",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "geometry.particle_diameter",
                            description="particle diameter value",
                            json_type="number",
                            unit="nm",
                            dimension="length",
                            canonical_unit="nm",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "film_thickness_um",
                    "Read film thickness",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "geometry.film_thickness",
                            description="film thickness value",
                            json_type="number",
                            unit="um",
                            dimension="length",
                            canonical_unit="um",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "specimen_length_mm",
                    "Read specimen length",
                    parameters=(_parameter("sample_id", description="sample identifier"),),
                    fields=(
                        _field(
                            "value",
                            "geometry.specimen_length",
                            description="specimen length value",
                            json_type="number",
                            unit="mm",
                            dimension="length",
                            canonical_unit="mm",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="papers",
            description="Scientific literature discovery and retrieval",
            endpoints=[
                _endpoint(
                    "search",
                    "Search papers by topic and keywords",
                    parameters=(_parameter("query", description="search query"),),
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "retrieve",
                    "Retrieve a paper by paper identifier",
                    parameters=(_parameter("paper_id", description="paper identifier"),),
                    fields=(
                        _field(
                            "text",
                            "paper.full_text",
                            description="paper full text",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "summarize",
                    "Summarize a paper by paper identifier",
                    parameters=(_parameter("paper_id", description="paper identifier"),),
                    fields=(
                        _field(
                            "summary",
                            "paper.summary",
                            description="paper summary text",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="records",
            description="Research-record lifecycle service",
            endpoints=[
                _endpoint(
                    "read",
                    "Read a research record without changing it",
                    parameters=(_parameter("record_id", description="record identifier"),),
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "update",
                    "Update a research record",
                    parameters=(
                        _parameter("record_id", description="record identifier"),
                        _parameter("patch", description="record patch"),
                    ),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "delete",
                    "Permanently delete a research record",
                    parameters=(_parameter("record_id", description="record identifier"),),
                    read_only=False,
                    destructive=True,
                ),
            ],
        ),
        ToolSpec(
            name="inventory",
            description="Laboratory inventory lifecycle service",
            endpoints=[
                _endpoint(
                    "get",
                    "Read one inventory item",
                    parameters=(_parameter("item_id", description="inventory item identifier"),),
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "list",
                    "List inventory items",
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "create",
                    "Create an inventory item",
                    parameters=(_parameter("name", description="item name"),),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "update",
                    "Update an inventory item",
                    parameters=(
                        _parameter("item_id", description="inventory item identifier"),
                        _parameter("patch", description="item patch"),
                    ),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "delete",
                    "Permanently delete an inventory item",
                    parameters=(_parameter("item_id", description="inventory item identifier"),),
                    read_only=False,
                    destructive=True,
                ),
            ],
        ),
        ToolSpec(
            name="files",
            description="Artifact file lifecycle service",
            endpoints=[
                _endpoint(
                    "read",
                    "Read an artifact file",
                    parameters=(_parameter("file_id", description="file identifier"),),
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "create",
                    "Create an artifact file",
                    parameters=(_parameter("name", description="file name"),),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "share",
                    "Share an artifact file with a collaborator",
                    parameters=(
                        _parameter("file_id", description="file identifier"),
                        _parameter("recipient", description="recipient"),
                    ),
                    read_only=False,
                ),
                _endpoint(
                    "archive",
                    "Archive a file reversibly without permanent deletion",
                    parameters=(_parameter("file_id", description="file identifier"),),
                    read_only=False,
                ),
                _endpoint(
                    "delete",
                    "Permanently delete a file",
                    parameters=(_parameter("file_id", description="file identifier"),),
                    read_only=False,
                    destructive=True,
                ),
                _endpoint(
                    "export",
                    "Export a file to a portable artifact",
                    parameters=(_parameter("file_id", description="file identifier"),),
                    fields=(
                        _field(
                            "uri",
                            "artifact.uri",
                            description="exported artifact URI",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="messages",
            description="Message lifecycle service",
            endpoints=[
                _endpoint(
                    "draft",
                    "Create a message draft without sending it",
                    parameters=(_parameter("text", description="message text"),),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "send",
                    "Send a message to a recipient",
                    parameters=(
                        _parameter("recipient", description="recipient"),
                        _parameter("text", description="message text"),
                    ),
                    read_only=False,
                ),
                _endpoint(
                    "status",
                    "Read delivery status for a message",
                    parameters=(_parameter("message_id", description="message identifier"),),
                    fields=(
                        _field(
                            "status",
                            "message.delivery_status",
                            description="delivery status",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
        ToolSpec(
            name="calendar",
            description="Calendar event lifecycle service",
            endpoints=[
                _endpoint(
                    "list",
                    "List calendar events",
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "create",
                    "Create a calendar event",
                    parameters=(_parameter("title", description="event title"),),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "update",
                    "Update a calendar event",
                    parameters=(_parameter("event_id", description="event identifier"),),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "delete",
                    "Permanently delete a calendar event",
                    parameters=(_parameter("event_id", description="event identifier"),),
                    read_only=False,
                    destructive=True,
                ),
            ],
        ),
        ToolSpec(
            name="users",
            description="User account lifecycle service",
            endpoints=[
                _endpoint(
                    "get",
                    "Read a user account",
                    parameters=(_parameter("user_id", description="user identifier"),),
                    fields=(item_id,),
                    read_only=True,
                ),
                _endpoint(
                    "update",
                    "Update a user account",
                    parameters=(_parameter("user_id", description="user identifier"),),
                    fields=(item_id,),
                    read_only=False,
                ),
                _endpoint(
                    "deactivate",
                    "Deactivate a user account irreversibly for this benchmark",
                    parameters=(_parameter("user_id", description="user identifier"),),
                    read_only=False,
                    destructive=True,
                ),
            ],
        ),
        ToolSpec(
            name="finance",
            description="Market data and trading service",
            endpoints=[
                _endpoint(
                    "quote",
                    "Read the current market price for a symbol",
                    parameters=(_parameter("symbol", description="market symbol"),),
                    fields=(value_quote,),
                    read_only=True,
                ),
                _endpoint(
                    "history",
                    "Read historical market prices",
                    parameters=(_parameter("symbol", description="market symbol"),),
                    fields=(value_quote,),
                    read_only=True,
                ),
                _endpoint(
                    "buy",
                    "Submit a buy order",
                    parameters=(
                        _parameter("symbol", description="market symbol"),
                        _parameter("quantity", description="order quantity", json_type="integer"),
                    ),
                    read_only=False,
                ),
                _endpoint(
                    "cancel_order",
                    "Cancel an existing market order",
                    parameters=(_parameter("order_id", description="order identifier"),),
                    read_only=False,
                ),
            ],
        ),
        ToolSpec(
            name="compute",
            description="Deterministic data-transformation service",
            endpoints=[
                _endpoint(
                    "statistics",
                    "Compute descriptive statistics for a dataset",
                    parameters=(_parameter("dataset_id", description="dataset identifier"),),
                    fields=(
                        _field(
                            "summary",
                            "statistics.summary",
                            description="statistical summary",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "normalize",
                    "Normalize a numeric dataset",
                    parameters=(_parameter("dataset_id", description="dataset identifier"),),
                    fields=(
                        _field(
                            "dataset_id",
                            "dataset.identifier",
                            description="normalized dataset identifier",
                        ),
                    ),
                    read_only=True,
                ),
                _endpoint(
                    "convert_units",
                    "Convert a numeric value between declared units",
                    parameters=(
                        _parameter("value", description="numeric value", json_type="number"),
                        _parameter("from_unit", description="source unit"),
                        _parameter("to_unit", description="target unit"),
                    ),
                    fields=(
                        _field(
                            "value",
                            "quantity.converted_value",
                            description="converted numeric value",
                            json_type="number",
                        ),
                    ),
                    read_only=True,
                ),
            ],
        ),
    ]


_DISTRACTOR_ACTIONS = (
    "search",
    "read",
    "list",
    "create",
    "update",
    "delete",
    "archive",
    "send",
    "export",
    "compare",
    "summarize",
    "forecast",
)
_DISTRACTOR_RESOURCES = (
    "patent",
    "shipment",
    "supplier",
    "protocol",
    "notebook",
    "image",
    "spectrum",
    "microscopy",
    "dataset",
    "experiment",
    "project",
    "report",
    "citation",
    "author",
    "workspace",
    "ticket",
    "approval",
    "policy",
    "contract",
    "dashboard",
    "job",
    "queue",
    "model",
    "checkpoint",
    "annotation",
    "folder",
    "profile",
    "invoice",
    "purchase",
    "batch",
)


def _distractor(index: int) -> ToolSpec:
    action = _DISTRACTOR_ACTIONS[(index * 5 + index // 7) % len(_DISTRACTOR_ACTIONS)]
    resource = _DISTRACTOR_RESOURCES[index % len(_DISTRACTOR_RESOURCES)]
    read_only = action in {
        "search",
        "read",
        "list",
        "export",
        "compare",
        "summarize",
        "forecast",
    }
    destructive = action == "delete"
    return ToolSpec(
        name=f"aux_{resource}_{index:04d}",
        description=f"Auxiliary {resource} service with adjacent lifecycle vocabulary",
        provider="representation_dev_aux",
        access_mode="python",
        endpoints=[
            _endpoint(
                action,
                f"{action.title()} {resource} records in an auxiliary service",
                parameters=(
                    (_parameter("record_id", description=f"{resource} record identifier"),)
                    if action not in {"search", "list"}
                    else ()
                ),
                fields=(
                    _field(
                        "value",
                        f"aux.{resource}.value",
                        description=f"{resource} auxiliary value",
                    ),
                )
                if read_only
                else (),
                read_only=read_only,
                destructive=destructive,
            )
        ],
    )


def build_registry(endpoint_count: int) -> InMemoryRegistry:
    if endpoint_count not in CATALOG_SIZES:
        raise ValueError(f"unsupported catalog size: {endpoint_count}")

    registry = InMemoryRegistry()
    core = _core_tools()
    registry.update_many(core)
    base_count = sum(len(tool.endpoints) for tool in core)
    if base_count >= min(CATALOG_SIZES):
        raise RuntimeError(
            f"core catalog must stay below the smallest stratum: {base_count}"
        )

    for index in range(endpoint_count - base_count):
        registry.register(_distractor(index))

    actual = sum(len(tool.endpoints) for tool in registry.tools())
    if actual != endpoint_count:
        raise RuntimeError(
            f"catalog endpoint count drifted: expected={endpoint_count} actual={actual}"
        )
    return registry


def _development_tasks() -> tuple[RepresentationTask, ...]:
    rows = (
        # single_tool_exact
        _task(
            "dev-single-01",
            "single_tool_exact",
            "Get Young modulus for material MAT-A.",
            "materials.elastic_modulus",
        ),
        _task(
            "dev-single-02",
            "single_tool_exact",
            "Search scientific papers about solid electrolytes.",
            "papers.search",
        ),
        _task(
            "dev-single-03",
            "single_tool_exact",
            "List laboratory inventory items.",
            "inventory.list",
        ),
        _task(
            "dev-single-04",
            "single_tool_exact",
            "Read the current price quote for NVDA.",
            "finance.quote",
        ),
        _task(
            "dev-single-05",
            "single_tool_exact",
            "Read relative humidity from sensor S-5.",
            "environment.humidity",
        ),

        # two_step_composition
        _task(
            "dev-two-01",
            "two_step_composition",
            "Search papers about sodium batteries and retrieve the selected paper.",
            "papers.search",
            "papers.retrieve",
        ),
        _task(
            "dev-two-02",
            "two_step_composition",
            "Create an artifact file and share it with a collaborator.",
            "files.create",
            "files.share",
        ),
        _task(
            "dev-two-03",
            "two_step_composition",
            "Read inventory item INV-7 and then update that item.",
            "inventory.get",
            "inventory.update",
        ),
        _task(
            "dev-two-04",
            "two_step_composition",
            "Read a market quote and historical prices for TSLA.",
            "finance.quote",
            "finance.history",
        ),
        _task(
            "dev-two-05",
            "two_step_composition",
            "Create a calendar event and then update its details.",
            "calendar.create",
            "calendar.update",
        ),

        # three_step_composition
        _task(
            "dev-three-01",
            "three_step_composition",
            "Search a paper, retrieve it, and summarize it.",
            "papers.search",
            "papers.retrieve",
            "papers.summarize",
        ),
        _task(
            "dev-three-02",
            "three_step_composition",
            "Create a file, share it, and export it.",
            "files.create",
            "files.share",
            "files.export",
        ),
        _task(
            "dev-three-03",
            "three_step_composition",
            "Read record R-2, create a file with the result, and share that file.",
            "records.read",
            "files.create",
            "files.share",
        ),
        _task(
            "dev-three-04",
            "three_step_composition",
            "Get inventory item INV-9, update it, and list inventory.",
            "inventory.get",
            "inventory.update",
            "inventory.list",
        ),
        _task(
            "dev-three-05",
            "three_step_composition",
            "Create a calendar event, update it, and list the calendar.",
            "calendar.create",
            "calendar.update",
            "calendar.list",
        ),

        # sibling_operation_ambiguity
        _task(
            "dev-sibling-01",
            "sibling_operation_ambiguity",
            "Retrieve paper P-42 itself; do not search or summarize.",
            "papers.retrieve",
        ),
        _task(
            "dev-sibling-02",
            "sibling_operation_ambiguity",
            "Summarize paper P-42; do not retrieve a raw full-text response.",
            "papers.summarize",
        ),
        _task(
            "dev-sibling-03",
            "sibling_operation_ambiguity",
            "Draft a message only; do not send it.",
            "messages.draft",
        ),
        _task(
            "dev-sibling-04",
            "sibling_operation_ambiguity",
            "Archive file F-8 reversibly; do not delete it.",
            "files.archive",
        ),
        _task(
            "dev-sibling-05",
            "sibling_operation_ambiguity",
            "Read one inventory item INV-4 rather than listing all items.",
            "inventory.get",
        ),

        # same_field_name_different_semantic_id
        _task(
            "dev-semantic-01",
            "same_field_name_different_semantic_id",
            "Read the materials elastic modulus value.",
            "materials.elastic_modulus",
        ),
        _task(
            "dev-semantic-02",
            "same_field_name_different_semantic_id",
            "Read the electrical resistance value.",
            "electrical.resistance",
        ),
        _task(
            "dev-semantic-03",
            "same_field_name_different_semantic_id",
            "Read the environmental temperature value.",
            "environment.temperature",
        ),
        _task(
            "dev-semantic-04",
            "same_field_name_different_semantic_id",
            "Read the chemistry pH value.",
            "chemistry.ph",
        ),
        _task(
            "dev-semantic-05",
            "same_field_name_different_semantic_id",
            "Read the finance market price value.",
            "finance.quote",
        ),

        # compatible_vs_incompatible_units
        _task(
            "dev-units-01",
            "compatible_vs_incompatible_units",
            "Get particle diameter in nm.",
            "geometry.particle_diameter_nm",
        ),
        _task(
            "dev-units-02",
            "compatible_vs_incompatible_units",
            "Get film thickness in um.",
            "geometry.film_thickness_um",
        ),
        _task(
            "dev-units-03",
            "compatible_vs_incompatible_units",
            "Get specimen length in mm.",
            "geometry.specimen_length_mm",
        ),
        _task(
            "dev-units-04",
            "compatible_vs_incompatible_units",
            "Get material density in g/cm3.",
            "materials.density",
        ),
        _task(
            "dev-units-05",
            "compatible_vs_incompatible_units",
            "Get solute concentration in mol/L.",
            "chemistry.concentration",
        ),

        # read_vs_write_siblings
        _task(
            "dev-readwrite-01",
            "read_vs_write_siblings",
            "Read record R-11 without modifying it.",
            "records.read",
        ),
        _task(
            "dev-readwrite-02",
            "read_vs_write_siblings",
            "Update record R-11.",
            "records.update",
        ),
        _task(
            "dev-readwrite-03",
            "read_vs_write_siblings",
            "Read user U-3 without changing the account.",
            "users.get",
        ),
        _task("dev-readwrite-04", "read_vs_write_siblings", "Update user U-3.", "users.update"),
        _task(
            "dev-readwrite-05",
            "read_vs_write_siblings",
            "Check message delivery status without sending anything.",
            "messages.status",
        ),

        # destructive_vs_non_destructive_siblings
        _task(
            "dev-destructive-01",
            "destructive_vs_non_destructive_siblings",
            "Archive file F-20 but keep it recoverable.",
            "files.archive",
        ),
        _task(
            "dev-destructive-02",
            "destructive_vs_non_destructive_siblings",
            "Permanently delete file F-20.",
            "files.delete",
        ),
        _task(
            "dev-destructive-03",
            "destructive_vs_non_destructive_siblings",
            "Update inventory item INV-2 without deleting it.",
            "inventory.update",
        ),
        _task(
            "dev-destructive-04",
            "destructive_vs_non_destructive_siblings",
            "Permanently delete research record R-2.",
            "records.delete",
        ),
        _task(
            "dev-destructive-05",
            "destructive_vs_non_destructive_siblings",
            "Deactivate user U-9.",
            "users.deactivate",
        ),

        # implicit_or_omitted_parameter
        _task(
            "dev-implicit-01",
            "implicit_or_omitted_parameter",
            "I need the band gap for the material we are discussing.",
            "materials.band_gap",
        ),
        _task(
            "dev-implicit-02",
            "implicit_or_omitted_parameter",
            "Pull up the paper I referenced earlier.",
            "papers.retrieve",
        ),
        _task(
            "dev-implicit-03",
            "implicit_or_omitted_parameter",
            "Show me the current temperature reading.",
            "environment.temperature",
        ),
        _task(
            "dev-implicit-04",
            "implicit_or_omitted_parameter",
            "Check the status of that message.",
            "messages.status",
        ),
        _task(
            "dev-implicit-05",
            "implicit_or_omitted_parameter",
            "Open the inventory item we were just looking at.",
            "inventory.get",
        ),

        # naturalistic_ambiguous_request
        _task(
            "dev-natural-01",
            "naturalistic_ambiguous_request",
            "Can you pull up that paper instead of hunting for new ones?",
            "papers.retrieve",
        ),
        _task(
            "dev-natural-02",
            "naturalistic_ambiguous_request",
            "Just park that file somewhere safe for now, don't wipe it.",
            "files.archive",
        ),
        _task(
            "dev-natural-03",
            "naturalistic_ambiguous_request",
            "What's NVDA sitting at right now?",
            "finance.quote",
        ),
        _task(
            "dev-natural-04",
            "naturalistic_ambiguous_request",
            "Give me the acidity reading for this sample.",
            "chemistry.ph",
        ),
        _task(
            "dev-natural-05",
            "naturalistic_ambiguous_request",
            "I only want to see the user profile, no edits.",
            "users.get",
        ),

        # near_domain_unsupported
        _task(
            "dev-near-01",
            "near_domain_unsupported",
            "Get Poisson ratio for material MAT-A.",
            supported=False,
        ),
        _task(
            "dev-near-02",
            "near_domain_unsupported",
            "Show the options chain for NVDA.",
            supported=False,
        ),
        _task(
            "dev-near-03",
            "near_domain_unsupported",
            "Restore a permanently deleted file.",
            supported=False,
        ),
        _task(
            "dev-near-04",
            "near_domain_unsupported",
            "Measure zeta potential for sample S-2.",
            supported=False,
        ),
        _task(
            "dev-near-05",
            "near_domain_unsupported",
            "Book a meeting room resource for the calendar event.",
            supported=False,
        ),

        # out_of_domain
        _task("dev-ood-01", "out_of_domain", "Write a sonnet about autumn.", supported=False),
        _task(
            "dev-ood-02",
            "out_of_domain",
            "Recommend a chess opening for Black.",
            supported=False,
        ),
        _task(
            "dev-ood-03",
            "out_of_domain",
            "Generate a photorealistic image of a lighthouse.",
            supported=False,
        ),
        _task("dev-ood-04", "out_of_domain", "Explain the plot of Hamlet.", supported=False),
        _task("dev-ood-05", "out_of_domain", "Give me a sourdough bread recipe.", supported=False),
    )
    return rows


DEVELOPMENT_TASKS = _development_tasks()


def development_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in DEVELOPMENT_TASKS:
        for language in LANGUAGES:
            rows.append(
                {
                    "semantic_task_id": task.semantic_task_id,
                    "stratum": task.stratum,
                    "language": language,
                    "query": task.queries[language],
                    "required_routes": list(task.required_routes),
                    "supported": task.supported,
                }
            )
    return rows
