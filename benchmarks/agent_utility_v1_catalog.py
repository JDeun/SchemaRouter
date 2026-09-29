"""Frozen catalog/task fixture for #418 agent-utility research."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    ToolSpec,
    UnitNormalizationSpec,
)

CATALOG_SIZES = (20, 50, 100, 250)
K_VALUES = (1, 3, 5, 10)


@dataclass(frozen=True)
class AgentUtilityTask:
    task_id: str
    query: str
    required_routes: tuple[str, ...]
    kind: str
    expected_answer: str


def _field(
    name: str,
    *,
    semantic_id: str | None = None,
    unit: str | None = None,
    dimension: str | None = None,
    canonical_unit: str | None = None,
) -> FieldSpec:
    normalization = None
    if unit is not None and dimension is not None and canonical_unit is not None:
        normalization = UnitNormalizationSpec(
            dimension=dimension,
            canonical_unit=canonical_unit,
            scale=1.0,
            offset=0.0,
        )
    return FieldSpec(
        name=name,
        semantic_id=semantic_id,
        description=name.replace("_", " "),
        json_schema={"type": "number"} if unit else {"type": "string"},
        unit=unit,
        unit_normalization=normalization,
    )


def _endpoint(
    name: str,
    description: str,
    *,
    read_only: bool,
    destructive: bool = False,
    parameters: Iterable[str] = (),
    fields: Iterable[FieldSpec] = (),
) -> EndpointSpec:
    return EndpointSpec(
        name=name,
        description=description,
        parameters=[
            ParameterSpec(
                name=parameter,
                description=parameter.replace("_", " "),
                required=True,
                json_schema={"type": "string"},
            )
            for parameter in parameters
        ],
        output_fields=list(fields),
        read_only=read_only,
        destructive=destructive,
    )


def _base_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="papers",
            description="Scientific paper discovery and document access",
            endpoints=[
                _endpoint(
                    "search",
                    "Search scientific papers by topic or keywords",
                    read_only=True,
                    parameters=("query",),
                    fields=(_field("paper_id", semantic_id="paper.id"),),
                ),
                _endpoint(
                    "retrieve",
                    "Retrieve one scientific paper by paper identifier",
                    read_only=True,
                    parameters=("paper_id",),
                    fields=(_field("paper_text", semantic_id="paper.text"),),
                ),
                _endpoint(
                    "summarize",
                    "Summarize one retrieved scientific paper",
                    read_only=True,
                    parameters=("paper_id",),
                    fields=(_field("summary", semantic_id="paper.summary"),),
                ),
            ],
        ),
        ToolSpec(
            name="materials",
            description="Materials reference and physical-property service",
            endpoints=[
                _endpoint(
                    "search",
                    "Search material records by formula or material name",
                    read_only=True,
                    parameters=("query",),
                    fields=(_field("material_id", semantic_id="material.id"),),
                ),
                _endpoint(
                    "retrieve",
                    "Retrieve one material record by material identifier",
                    read_only=True,
                    parameters=("material_id",),
                    fields=(
                        _field("formula", semantic_id="material.formula"),
                        _field("artifact_id", semantic_id="artifact.id"),
                    ),
                ),
                _endpoint(
                    "current",
                    "Retrieve the current Young's modulus value for a material",
                    read_only=True,
                    parameters=("material_id",),
                    fields=(
                        _field(
                            "youngs_modulus",
                            semantic_id="material.youngs_modulus",
                            unit="GPa",
                            dimension="elastic_modulus",
                            canonical_unit="GPa",
                        ),
                    ),
                ),
                _endpoint(
                    "history",
                    "Retrieve historical Young's modulus values for a material",
                    read_only=True,
                    parameters=("material_id",),
                    fields=(
                        _field(
                            "youngs_modulus",
                            semantic_id="material.youngs_modulus",
                            unit="GPa",
                            dimension="elastic_modulus",
                            canonical_unit="GPa",
                        ),
                    ),
                ),
                _endpoint(
                    "forecast",
                    "Forecast future Young's modulus values for a material",
                    read_only=True,
                    parameters=("material_id",),
                    fields=(
                        _field(
                            "youngs_modulus",
                            semantic_id="material.youngs_modulus",
                            unit="GPa",
                            dimension="elastic_modulus",
                            canonical_unit="GPa",
                        ),
                    ),
                ),
            ],
        ),
        ToolSpec(
            name="inventory",
            description="Laboratory inventory lifecycle service",
            endpoints=[
                _endpoint(
                    "list",
                    "List laboratory inventory items",
                    read_only=True,
                    fields=(_field("item_id", semantic_id="inventory.item_id"),),
                ),
                _endpoint(
                    "create",
                    "Create a new laboratory inventory item",
                    read_only=False,
                    parameters=("item_name",),
                    fields=(_field("item_id", semantic_id="inventory.item_id"),),
                ),
                _endpoint(
                    "update",
                    "Update an existing laboratory inventory item",
                    read_only=False,
                    parameters=("item_id",),
                    fields=(_field("item_id", semantic_id="inventory.item_id"),),
                ),
                _endpoint(
                    "delete",
                    "Delete a laboratory inventory item permanently",
                    read_only=False,
                    destructive=True,
                    parameters=("item_id",),
                ),
            ],
        ),
        ToolSpec(
            name="messaging",
            description="Research message and access-sharing service",
            endpoints=[
                _endpoint(
                    "send",
                    "Send a research message to a recipient",
                    read_only=False,
                    parameters=("recipient", "message"),
                ),
                _endpoint(
                    "share",
                    "Share access to a research artifact with a collaborator",
                    read_only=False,
                    parameters=("artifact_id", "recipient"),
                ),
            ],
        ),
        ToolSpec(
            name="credits",
            description="Research-credit request and payment lifecycle",
            endpoints=[
                _endpoint(
                    "create",
                    "Create a new research-credit request",
                    read_only=False,
                    parameters=("amount",),
                    fields=(
                        _field("credit_id", semantic_id="credit.id"),
                        _field("artifact_id", semantic_id="artifact.id"),
                    ),
                ),
                _endpoint(
                    "cancel",
                    "Cancel an active research-credit request",
                    read_only=False,
                    parameters=("credit_id",),
                ),
                _endpoint(
                    "refund",
                    "Refund a completed research-credit payment",
                    read_only=False,
                    parameters=("credit_id",),
                ),
            ],
        ),
        ToolSpec(
            name="runtime",
            description="Registered workflow runtime control",
            endpoints=[
                _endpoint(
                    "restart",
                    "Restart a registered workflow runtime",
                    read_only=False,
                    parameters=("runtime_id",),
                ),
                _endpoint(
                    "execute",
                    "Execute a registered workflow operation",
                    read_only=False,
                    parameters=("runtime_id", "operation"),
                ),
            ],
        ),
        ToolSpec(
            name="exports",
            description="Research artifact export service",
            endpoints=[
                _endpoint(
                    "export",
                    "Export a research artifact as a file",
                    read_only=True,
                    parameters=("artifact_id",),
                    fields=(_field("file_uri", semantic_id="artifact.file_uri"),),
                )
            ],
        ),
    ]


_DISTRACTOR_ACTIONS = (
    "search",
    "retrieve",
    "list",
    "create",
    "update",
    "delete",
    "cancel",
    "refund",
    "send",
    "share",
    "export",
    "translate",
    "summarize",
    "compare",
    "merge",
    "restart",
    "execute",
    "forecast",
)

_DISTRACTOR_RESOURCES = (
    "patent",
    "dataset",
    "sample",
    "experiment",
    "protocol",
    "invoice",
    "shipment",
    "calendar",
    "notebook",
    "image",
    "spectrum",
    "microscopy",
    "supplier",
    "purchase",
    "device",
    "sensor",
    "batch",
    "recipe",
    "project",
    "report",
    "citation",
    "author",
    "organization",
    "workspace",
    "archive",
    "ticket",
    "approval",
    "policy",
    "contract",
    "metric",
    "dashboard",
    "job",
    "queue",
    "model",
    "checkpoint",
    "annotation",
    "document",
    "folder",
    "account",
    "profile",
)


def _distractor_endpoint(index: int) -> ToolSpec:
    resource = _DISTRACTOR_RESOURCES[index % len(_DISTRACTOR_RESOURCES)]
    action = _DISTRACTOR_ACTIONS[(index * 7 + index // 3) % len(_DISTRACTOR_ACTIONS)]
    adjacent = index % 3 == 0
    if adjacent:
        description = (
            f"{action.title()} {resource} records in an adjacent research service; "
            "not the canonical papers, materials, inventory, messaging, credits, "
            "runtime, or exports capability"
        )
    else:
        description = f"{action.title()} {resource} records in an auxiliary service"

    destructive = action == "delete"
    read_only = action in {
        "search",
        "retrieve",
        "list",
        "export",
        "translate",
        "summarize",
        "compare",
        "forecast",
    }
    return ToolSpec(
        name=f"aux_{resource}_{index:03d}",
        description=f"Auxiliary {resource} service {index:03d}",
        endpoints=[
            _endpoint(
                action,
                description,
                read_only=read_only,
                destructive=destructive,
                parameters=("record_id",) if action not in {"list", "search"} else (),
                fields=(
                    _field(
                        f"{resource}_value",
                        semantic_id=f"aux.{resource}.value",
                    ),
                )
                if read_only
                else (),
            )
        ],
    )


def build_registry(endpoint_count: int) -> InMemoryRegistry:
    if endpoint_count not in CATALOG_SIZES:
        raise ValueError(f"unsupported catalog size: {endpoint_count}")

    registry = InMemoryRegistry()
    base = _base_tools()
    registry.update_many(base)
    base_count = sum(len(tool.endpoints) for tool in base)
    if base_count != 20:
        raise RuntimeError(f"base endpoint count drifted: {base_count}")

    for index in range(endpoint_count - base_count):
        registry.register(_distractor_endpoint(index))

    actual = sum(len(tool.endpoints) for tool in registry.tools())
    if actual != endpoint_count:
        raise RuntimeError(
            f"catalog endpoint count drifted: expected={endpoint_count} actual={actual}"
        )
    return registry


TASKS = (
    AgentUtilityTask(
        "single-paper-search",
        "Search scientific papers about solid-state battery electrolytes.",
        ("papers.search",),
        "single",
        "paper search completed",
    ),
    AgentUtilityTask(
        "single-paper-retrieve",
        "Retrieve scientific paper P-104 by its paper identifier.",
        ("papers.retrieve",),
        "single",
        "paper P-104 retrieved",
    ),
    AgentUtilityTask(
        "single-paper-summary",
        "Summarize scientific paper P-104.",
        ("papers.summarize",),
        "single",
        "paper P-104 summarized",
    ),
    AgentUtilityTask(
        "single-material-search",
        "Search material records for lithium iron phosphate.",
        ("materials.search",),
        "single",
        "material search completed",
    ),
    AgentUtilityTask(
        "single-material-retrieve",
        "Retrieve material record MAT-7 by material identifier.",
        ("materials.retrieve",),
        "single",
        "material MAT-7 retrieved",
    ),
    AgentUtilityTask(
        "single-material-current",
        "Get the current Young's modulus in GPa for material MAT-7.",
        ("materials.current",),
        "single",
        "current Young's modulus returned",
    ),
    AgentUtilityTask(
        "single-material-history",
        "Get historical Young's modulus values for material MAT-7.",
        ("materials.history",),
        "single",
        "historical Young's modulus returned",
    ),
    AgentUtilityTask(
        "single-material-forecast",
        "Forecast future Young's modulus values for material MAT-7.",
        ("materials.forecast",),
        "single",
        "Young's modulus forecast returned",
    ),
    AgentUtilityTask(
        "single-inventory-list",
        "List the laboratory inventory items.",
        ("inventory.list",),
        "single",
        "inventory listed",
    ),
    AgentUtilityTask(
        "single-inventory-create",
        "Create a new laboratory inventory item named cathode-powder.",
        ("inventory.create",),
        "single",
        "inventory item created",
    ),
    AgentUtilityTask(
        "single-inventory-update",
        "Update inventory item INV-3.",
        ("inventory.update",),
        "single",
        "inventory item updated",
    ),
    AgentUtilityTask(
        "single-inventory-delete",
        "Delete inventory item INV-3 permanently.",
        ("inventory.delete",),
        "single",
        "destructive action requires approval",
    ),
    AgentUtilityTask(
        "single-message-send",
        "Send a research message to analyst@example.org.",
        ("messaging.send",),
        "single",
        "message sent",
    ),
    AgentUtilityTask(
        "single-share",
        "Share artifact ART-2 with analyst@example.org.",
        ("messaging.share",),
        "single",
        "artifact shared",
    ),
    AgentUtilityTask(
        "single-credit-refund",
        "Refund research-credit payment CR-8.",
        ("credits.refund",),
        "single",
        "credit payment refunded",
    ),
    AgentUtilityTask(
        "single-runtime-restart",
        "Restart registered workflow runtime RT-2.",
        ("runtime.restart",),
        "single",
        "runtime restarted",
    ),
    AgentUtilityTask(
        "single-export",
        "Export research artifact ART-2 as a file.",
        ("exports.export",),
        "single",
        "artifact exported",
    ),
    AgentUtilityTask(
        "multi-paper-search-retrieve",
        "Search scientific papers about perovskite stability, then retrieve the selected paper.",
        ("papers.search", "papers.retrieve"),
        "multi",
        "selected paper retrieved",
    ),
    AgentUtilityTask(
        "multi-paper-retrieve-summary",
        "Retrieve scientific paper P-205 and summarize it.",
        ("papers.retrieve", "papers.summarize"),
        "multi",
        "paper P-205 summarized",
    ),
    AgentUtilityTask(
        "multi-material-search-current",
        "Search for nickel-rich cathode material records and then get the current Young's modulus.",
        ("materials.search", "materials.current"),
        "multi",
        "current modulus for selected material returned",
    ),
    AgentUtilityTask(
        "multi-create-share",
        (
            "Create a research-credit request and share the resulting artifact "
            "with analyst@example.org."
        ),
        ("credits.create", "messaging.share"),
        "multi",
        "credit request created and artifact shared",
    ),
    AgentUtilityTask(
        "multi-create-send",
        "Create a laboratory inventory item and send a research message confirming creation.",
        ("inventory.create", "messaging.send"),
        "multi",
        "inventory item created and confirmation sent",
    ),
    AgentUtilityTask(
        "multi-retrieve-export",
        "Retrieve material record MAT-7 and export the resulting research artifact.",
        ("materials.retrieve", "exports.export"),
        "multi",
        "material artifact exported",
    ),
)


def route_ids(registry: InMemoryRegistry) -> tuple[str, ...]:
    return tuple(
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    )
