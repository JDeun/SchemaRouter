# ruff: noqa: E501
"""Disjoint 0.12-E catalogs for capability-set membership experiment #363."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")


@dataclass(frozen=True)
class RouteCaseSpec:
    route_id: str
    leaf: str
    objects: dict[str, str]
    temporal_scope: str | None = None


def _field(
    name: str,
    *,
    identifier: bool = False,
    unit: str | None = None,
) -> FieldSpec:
    return FieldSpec(
        name=name,
        json_schema={"type": "number" if unit else "string"},
        unit=unit,
        identifier=identifier,
    )


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    permits_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Quarry Permit Service", "version": "1.0.0"},
        "paths": {
            "/permits/{permit_id}": {
                "get": {
                    "operationId": "qp17",
                    "summary": "Retrieve one existing quarry permit",
                    "responses": {"200": {"description": "permit"}},
                },
                "patch": {
                    "operationId": "qp28",
                    "summary": "Update an existing quarry permit",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "qp39",
                    "summary": "Delete an existing quarry permit permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("quarry_permits_api", permits_openapi))

    registry.register(
        tool_from_mcp(
            "ledger_index_ops",
            {
                "tools": [
                    {
                        "name": "li11",
                        "description": "Search ledger entries matching criteria or text",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "li22",
                        "description": "Retrieve one already identified ledger entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"entry_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "li33",
                        "description": "List all ledger entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="transfer_packets",
            description="Packet delivery and access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a transfer packet to its destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a transfer packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="render_ops",
            description="Render artifact transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a render artifact to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate a render artifact into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a render artifact into key points",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="service_units",
            description="Managed service-unit control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing service unit",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered service-unit operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="access_passes",
            description="Access-pass lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new access pass",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active access pass",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid access-pass charge",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="thermal_flux",
            description="Thermal-flux observations and prediction",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current thermal flux",
                    read_only=True,
                    output_fields=[_field("value", unit="W/m2")],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical thermal-flux observations",
                    read_only=True,
                    output_fields=[_field("value", unit="W/m2")],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future thermal flux",
                    read_only=True,
                    output_fields=[_field("value", unit="W/m2")],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    clearance_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Harbor Clearance Service", "version": "1.0.0"},
        "paths": {
            "/clearances/{clearance_id}": {
                "get": {
                    "operationId": "hc17",
                    "summary": "Retrieve one existing harbor clearance",
                    "responses": {"200": {"description": "clearance"}},
                },
                "patch": {
                    "operationId": "hc28",
                    "summary": "Update an existing harbor clearance",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "hc39",
                    "summary": "Delete an existing harbor clearance permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("harbor_clearance_api", clearance_openapi))

    registry.register(
        tool_from_mcp(
            "memo_index_ops",
            {
                "tools": [
                    {
                        "name": "mi10",
                        "description": "Search memo records matching text or criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "mi20",
                        "description": "Retrieve one already identified memo record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"memo_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "mi30",
                        "description": "List all memo records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="brief_access",
            description="Brief delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a brief to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a brief with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="text_transform",
            description="Text transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export text content to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare text items for differences",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple text items into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="task_runners",
            description="Task-runner control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing task runner",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered task-runner workflow",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="credit_claims",
            description="Credit claim retrieval and reimbursement service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve an existing credit claim",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active credit claim",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid credit claim amount",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="flow_rate",
            description="Flow-rate observations and prediction",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current flow rate",
                    read_only=True,
                    output_fields=[_field("value", unit="L/s")],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical flow-rate observations",
                    read_only=True,
                    output_fields=[_field("value", unit="L/s")],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future flow rate",
                    read_only=True,
                    output_fields=[_field("value", unit="L/s")],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("quarry_permits_api.qp17", "retrieve", {"en":"quarry permit QP-8","ko":"채석장 허가 QP-8","es":"permiso de cantera QP-8","ja":"採石許可QP-8","de":"steinbruchgenehmigung QP-8","mixed":"quarry permit QP-8"}),
    RouteCaseSpec("quarry_permits_api.qp28", "update", {"en":"quarry permit QP-8","ko":"채석장 허가 QP-8","es":"permiso de cantera QP-8","ja":"採石許可QP-8","de":"steinbruchgenehmigung QP-8","mixed":"quarry permit QP-8"}),
    RouteCaseSpec("quarry_permits_api.qp39", "delete", {"en":"quarry permit QP-8","ko":"채석장 허가 QP-8","es":"permiso de cantera QP-8","ja":"採石許可QP-8","de":"steinbruchgenehmigung QP-8","mixed":"quarry permit QP-8"}),
    RouteCaseSpec("ledger_index_ops.li11", "search", {"en":"ledger entries about cobalt","ko":"cobalt 관련 원장 항목","es":"entradas del libro mayor sobre cobalt","ja":"cobaltに関する台帳項目","de":"bucheinträge zu cobalt","mixed":"cobalt 관련 ledger entries"}),
    RouteCaseSpec("ledger_index_ops.li22", "retrieve", {"en":"ledger entry LE-4","ko":"원장 항목 LE-4","es":"entrada del libro mayor LE-4","ja":"台帳項目LE-4","de":"bucheintrag LE-4","mixed":"ledger entry LE-4"}),
    RouteCaseSpec("ledger_index_ops.li33", "list", {"en":"ledger entries","ko":"원장 항목","es":"entradas del libro mayor","ja":"台帳項目","de":"bucheinträge","mixed":"ledger entries"}),
    RouteCaseSpec("transfer_packets.send", "send", {"en":"transfer packet TP-5","ko":"전송 패킷 TP-5","es":"paquete de transferencia TP-5","ja":"転送パケットTP-5","de":"transferpaket TP-5","mixed":"transfer packet TP-5"}),
    RouteCaseSpec("transfer_packets.share", "share", {"en":"transfer packet TP-5","ko":"전송 패킷 TP-5","es":"paquete de transferencia TP-5","ja":"転送パケットTP-5","de":"transferpaket TP-5","mixed":"transfer packet TP-5"}),
    RouteCaseSpec("render_ops.export", "export", {"en":"render artifact RA-3","ko":"렌더 산출물 RA-3","es":"artefacto renderizado RA-3","ja":"レンダー成果物RA-3","de":"render-artefakt RA-3","mixed":"render artifact RA-3"}),
    RouteCaseSpec("render_ops.translate", "translate", {"en":"render artifact RA-3","ko":"렌더 산출물 RA-3","es":"artefacto renderizado RA-3","ja":"レンダー成果物RA-3","de":"render-artefakt RA-3","mixed":"render artifact RA-3"}),
    RouteCaseSpec("render_ops.summarize", "summarize", {"en":"render artifact RA-3","ko":"렌더 산출물 RA-3","es":"artefacto renderizado RA-3","ja":"レンダー成果物RA-3","de":"render-artefakt RA-3","mixed":"render artifact RA-3"}),
    RouteCaseSpec("service_units.restart", "restart", {"en":"service unit SU-2","ko":"서비스 유닛 SU-2","es":"unidad de servicio SU-2","ja":"サービスユニットSU-2","de":"serviceeinheit SU-2","mixed":"service unit SU-2"}),
    RouteCaseSpec("service_units.execute", "execute", {"en":"service-unit operation SU-2","ko":"서비스 유닛 작업 SU-2","es":"operación de unidad SU-2","ja":"サービスユニット操作SU-2","de":"serviceeinheit-operation SU-2","mixed":"service-unit operation SU-2"}),
    RouteCaseSpec("access_passes.create", "create", {"en":"access pass","ko":"접근 패스","es":"pase de acceso","ja":"アクセスパス","de":"zugangspass","mixed":"access pass"}),
    RouteCaseSpec("access_passes.cancel", "cancel", {"en":"access pass AP-7","ko":"접근 패스 AP-7","es":"pase de acceso AP-7","ja":"アクセスパスAP-7","de":"zugangspass AP-7","mixed":"access pass AP-7"}),
    RouteCaseSpec("access_passes.refund", "refund", {"en":"access-pass charge AP-7","ko":"접근 패스 결제 AP-7","es":"cargo de pase AP-7","ja":"アクセスパス料金AP-7","de":"zugangspassgebühr AP-7","mixed":"access-pass charge AP-7"}),
    RouteCaseSpec("thermal_flux.current", "retrieve", {"en":"thermal flux","ko":"열 유속","es":"flujo térmico","ja":"熱流束","de":"wärmestromdichte","mixed":"thermal flux"}, temporal_scope="current"),
    RouteCaseSpec("thermal_flux.history", "retrieve", {"en":"thermal-flux values","ko":"열 유속 값","es":"valores de flujo térmico","ja":"熱流束値","de":"wärmestromwerte","mixed":"thermal-flux values"}, temporal_scope="historical"),
    RouteCaseSpec("thermal_flux.forecast", "forecast", {"en":"thermal-flux values","ko":"열 유속 값","es":"valores de flujo térmico","ja":"熱流束値","de":"wärmestromwerte","mixed":"thermal-flux values"}, temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("harbor_clearance_api.hc17", "retrieve", {"en":"harbor clearance HC-6","ko":"항만 허가 HC-6","es":"autorización portuaria HC-6","ja":"港湾許可HC-6","de":"hafengenehmigung HC-6","mixed":"harbor clearance HC-6"}),
    RouteCaseSpec("harbor_clearance_api.hc28", "update", {"en":"harbor clearance HC-6","ko":"항만 허가 HC-6","es":"autorización portuaria HC-6","ja":"港湾許可HC-6","de":"hafengenehmigung HC-6","mixed":"harbor clearance HC-6"}),
    RouteCaseSpec("harbor_clearance_api.hc39", "delete", {"en":"harbor clearance HC-6","ko":"항만 허가 HC-6","es":"autorización portuaria HC-6","ja":"港湾許可HC-6","de":"hafengenehmigung HC-6","mixed":"harbor clearance HC-6"}),
    RouteCaseSpec("memo_index_ops.mi10", "search", {"en":"memo records about calibration","ko":"calibration 관련 메모 기록","es":"registros de memo sobre calibration","ja":"calibrationに関するメモ記録","de":"memo-einträge zu calibration","mixed":"calibration 관련 memo records"}),
    RouteCaseSpec("memo_index_ops.mi20", "retrieve", {"en":"memo record MR-9","ko":"메모 기록 MR-9","es":"registro de memo MR-9","ja":"メモ記録MR-9","de":"memo-eintrag MR-9","mixed":"memo record MR-9"}),
    RouteCaseSpec("memo_index_ops.mi30", "list", {"en":"memo records","ko":"메모 기록","es":"registros de memo","ja":"メモ記録","de":"memo-einträge","mixed":"memo records"}),
    RouteCaseSpec("brief_access.send", "send", {"en":"brief BF-2","ko":"브리프 BF-2","es":"informe breve BF-2","ja":"ブリーフBF-2","de":"briefing BF-2","mixed":"brief BF-2"}),
    RouteCaseSpec("brief_access.share", "share", {"en":"brief BF-2","ko":"브리프 BF-2","es":"informe breve BF-2","ja":"ブリーフBF-2","de":"briefing BF-2","mixed":"brief BF-2"}),
    RouteCaseSpec("text_transform.export", "export", {"en":"text item TX-1","ko":"텍스트 항목 TX-1","es":"elemento de texto TX-1","ja":"テキスト項目TX-1","de":"textelement TX-1","mixed":"text item TX-1"}),
    RouteCaseSpec("text_transform.compare", "compare", {"en":"text items TX-1 and TX-2","ko":"텍스트 항목 TX-1과 TX-2","es":"elementos de texto TX-1 y TX-2","ja":"テキスト項目TX-1とTX-2","de":"textelemente TX-1 und TX-2","mixed":"text items TX-1 TX-2"}),
    RouteCaseSpec("text_transform.merge", "merge", {"en":"text items TX-1 and TX-2","ko":"텍스트 항목 TX-1과 TX-2","es":"elementos de texto TX-1 y TX-2","ja":"テキスト項目TX-1とTX-2","de":"textelemente TX-1 und TX-2","mixed":"text items TX-1 TX-2"}),
    RouteCaseSpec("task_runners.restart", "restart", {"en":"task runner TR-5","ko":"태스크 러너 TR-5","es":"ejecutor de tareas TR-5","ja":"タスクランナーTR-5","de":"task-runner TR-5","mixed":"task runner TR-5"}),
    RouteCaseSpec("task_runners.execute", "execute", {"en":"task-runner workflow TR-5","ko":"태스크 러너 워크플로 TR-5","es":"flujo de ejecutor TR-5","ja":"タスクランナーワークフローTR-5","de":"task-runner-workflow TR-5","mixed":"task-runner workflow TR-5"}),
    RouteCaseSpec("credit_claims.retrieve", "retrieve", {"en":"credit claim CC-4","ko":"크레딧 클레임 CC-4","es":"reclamación de crédito CC-4","ja":"クレジット請求CC-4","de":"gutschriftanspruch CC-4","mixed":"credit claim CC-4"}),
    RouteCaseSpec("credit_claims.cancel", "cancel", {"en":"credit claim CC-4","ko":"크레딧 클레임 CC-4","es":"reclamación de crédito CC-4","ja":"クレジット請求CC-4","de":"gutschriftanspruch CC-4","mixed":"credit claim CC-4"}),
    RouteCaseSpec("credit_claims.refund", "refund", {"en":"credit claim payment CC-4","ko":"크레딧 클레임 결제 CC-4","es":"pago de reclamación CC-4","ja":"クレジット請求支払いCC-4","de":"gutschriftzahlung CC-4","mixed":"credit claim payment CC-4"}),
    RouteCaseSpec("flow_rate.current", "retrieve", {"en":"flow rate","ko":"유량","es":"caudal","ja":"流量","de":"durchflussrate","mixed":"flow rate"}, temporal_scope="current"),
    RouteCaseSpec("flow_rate.history", "retrieve", {"en":"flow-rate values","ko":"유량 값","es":"valores de caudal","ja":"流量値","de":"durchflusswerte","mixed":"flow-rate values"}, temporal_scope="historical"),
    RouteCaseSpec("flow_rate.forecast", "forecast", {"en":"flow-rate values","ko":"유량 값","es":"valores de caudal","ja":"流量値","de":"durchflusswerte","mixed":"flow-rate values"}, temporal_scope="future"),
)
