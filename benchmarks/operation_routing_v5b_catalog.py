# ruff: noqa: E501
"""Disjoint 0.12-B catalogs for semantic-action-ontology experiment #349."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")


@dataclass(frozen=True)
class RouteCaseSpec:
    route_id: str
    action: str
    objects: dict[str, str]
    temporal_scope: str | None = None


def _text_field(name: str, *, identifier: bool = False) -> FieldSpec:
    return FieldSpec(
        name=name,
        json_schema={"type": "string"},
        identifier=identifier,
    )


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    profiles_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Profile Directory", "version": "1.0.0"},
        "paths": {
            "/profiles/{profile_id}": {
                "get": {
                    "operationId": "r17",
                    "summary": "Retrieve an existing profile",
                    "parameters": [
                        {
                            "name": "profile_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "profile"}},
                },
                "patch": {
                    "operationId": "u42",
                    "summary": "Update an existing profile",
                    "parameters": [
                        {
                            "name": "profile_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "d93",
                    "summary": "Delete an existing profile permanently",
                    "parameters": [
                        {
                            "name": "profile_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("profiles_api", profiles_openapi))

    registry.register(
        tool_from_mcp(
            "mailbox_ops",
            {
                "tools": [
                    {
                        "name": "m11",
                        "description": "Search mailbox messages by subject or sender",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "m22",
                        "description": "Retrieve one existing mailbox message",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"message_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "m33",
                        "description": "Send a mailbox message to a recipient",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "recipient": {"type": "string"},
                                "body": {"type": "string"},
                            },
                        },
                    },
                    {
                        "name": "m44",
                        "description": "Delete a mailbox message permanently",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"message_id": {"type": "string"}},
                        },
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="exports",
            description="Dataset export catalog",
            endpoints=[
                EndpointSpec(
                    name="list",
                    description="List available dataset exports",
                    read_only=True,
                    output_fields=[
                        _text_field("export_id", identifier=True),
                        _text_field("title"),
                    ],
                ),
                EndpointSpec(
                    name="export",
                    description="Export a dataset into an external file",
                    read_only=True,
                    output_fields=[
                        _text_field("export_id", identifier=True),
                        _text_field("download_url"),
                    ],
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="payments",
            description="Payment record and reimbursement service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve an existing payment record",
                    read_only=True,
                    output_fields=[
                        _text_field("payment_id", identifier=True),
                        FieldSpec(
                            name="amount",
                            json_schema={"type": "number"},
                            unit="USD",
                        ),
                    ],
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund an existing completed payment",
                    read_only=False,
                    output_fields=[_text_field("payment_id", identifier=True)],
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="machines",
            description="Managed machine status and control",
            endpoints=[
                EndpointSpec(
                    name="status",
                    description="Retrieve the current status of a managed machine",
                    read_only=True,
                    output_fields=[
                        _text_field("machine_id", identifier=True),
                        _text_field("status"),
                    ],
                ),
                EndpointSpec(
                    name="restart",
                    description="Restart a managed machine",
                    read_only=False,
                    output_fields=[_text_field("machine_id", identifier=True)],
                ),
            ],
        )
    )

    registry.register(
        tool_from_mcp(
            "workflow_ops",
            {
                "tools": [
                    {
                        "name": "w10",
                        "description": "List existing automation workflows",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "w20",
                        "description": "Create a new automation workflow",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                    {
                        "name": "w30",
                        "description": "Update an existing automation workflow",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"workflow_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "w40",
                        "description": "Cancel an active automation workflow",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"workflow_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "w50",
                        "description": "Execute an automation workflow",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"workflow_id": {"type": "string"}},
                        },
                    },
                ]
            },
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    bookings_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Booking Service", "version": "1.0.0"},
        "paths": {
            "/bookings/{booking_id}": {
                "get": {
                    "operationId": "b17",
                    "summary": "Retrieve an existing booking",
                    "responses": {"200": {"description": "booking"}},
                },
                "patch": {
                    "operationId": "b28",
                    "summary": "Update an existing booking",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/bookings/{booking_id}/cancel": {
                "post": {
                    "operationId": "b39",
                    "summary": "Cancel an existing booking",
                    "responses": {"200": {"description": "cancelled"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("bookings_api", bookings_openapi))

    registry.register(
        tool_from_mcp(
            "archive_ops",
            {
                "tools": [
                    {
                        "name": "a01",
                        "description": "Search archived records by phrase",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "a02",
                        "description": "Retrieve one archived record",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                    {
                        "name": "a03",
                        "description": "Export an archived record to a file",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                    {
                        "name": "a04",
                        "description": "Share an archived record with another user",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                    {
                        "name": "a05",
                        "description": "Translate an archived record into another language",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="notes",
            description="Team note management",
            endpoints=[
                EndpointSpec(name="list", description="List existing team notes", read_only=True),
                EndpointSpec(name="create", description="Create a new team note", read_only=False),
                EndpointSpec(name="update", description="Update an existing team note", read_only=False),
                EndpointSpec(
                    name="delete",
                    description="Delete an existing team note",
                    read_only=False,
                    destructive=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="deployments",
            description="Deployment listing and control",
            endpoints=[
                EndpointSpec(name="list", description="List existing deployments", read_only=True),
                EndpointSpec(name="restart", description="Restart a deployment", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active deployment", read_only=False),
                EndpointSpec(name="execute", description="Execute a deployment workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="invoices",
            description="Invoice record and payment operations",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve an existing invoice", read_only=True),
                EndpointSpec(name="refund", description="Refund a paid invoice", read_only=False),
                EndpointSpec(name="send", description="Send an invoice to a recipient", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="signals",
            description="Signal observations and forecasts",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current signal value",
                    read_only=True,
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical signal values",
                    read_only=True,
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future signal values",
                    read_only=True,
                ),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("profiles_api.r17", "read", {"en":"profile P-8","ko":"프로필 P-8","es":"perfil P-8","ja":"プロフィールP-8","de":"profil P-8","mixed":"profile P-8"}),
    RouteCaseSpec("profiles_api.u42", "update", {"en":"profile P-8","ko":"프로필 P-8","es":"perfil P-8","ja":"プロフィールP-8","de":"profil P-8","mixed":"profile P-8"}),
    RouteCaseSpec("profiles_api.d93", "delete", {"en":"profile P-8","ko":"프로필 P-8","es":"perfil P-8","ja":"プロフィールP-8","de":"profil P-8","mixed":"profile P-8"}),
    RouteCaseSpec("mailbox_ops.m11", "read", {"en":"messages about launch","ko":"launch 관련 메시지","es":"mensajes sobre launch","ja":"launchに関するメッセージ","de":"nachrichten über launch","mixed":"launch 관련 messages"}),
    RouteCaseSpec("mailbox_ops.m22", "read", {"en":"message M-4","ko":"메시지 M-4","es":"mensaje M-4","ja":"メッセージM-4","de":"nachricht M-4","mixed":"message M-4"}),
    RouteCaseSpec("mailbox_ops.m33", "send", {"en":"message M-4","ko":"메시지 M-4","es":"mensaje M-4","ja":"メッセージM-4","de":"nachricht M-4","mixed":"message M-4"}),
    RouteCaseSpec("mailbox_ops.m44", "delete", {"en":"message M-4","ko":"메시지 M-4","es":"mensaje M-4","ja":"メッセージM-4","de":"nachricht M-4","mixed":"message M-4"}),
    RouteCaseSpec("exports.list", "read", {"en":"available dataset exports","ko":"사용 가능한 데이터 내보내기","es":"exportaciones de datos disponibles","ja":"利用可能なデータエクスポート","de":"verfügbare datenexporte","mixed":"available 데이터 exports"}),
    RouteCaseSpec("exports.export", "export", {"en":"dataset export E-2","ko":"데이터 내보내기 E-2","es":"exportación de datos E-2","ja":"データエクスポートE-2","de":"datenexport E-2","mixed":"dataset export E-2"}),
    RouteCaseSpec("payments.retrieve", "read", {"en":"payment PAY-7","ko":"결제 PAY-7","es":"pago PAY-7","ja":"支払いPAY-7","de":"zahlung PAY-7","mixed":"payment PAY-7"}),
    RouteCaseSpec("payments.refund", "refund", {"en":"payment PAY-7","ko":"결제 PAY-7","es":"pago PAY-7","ja":"支払いPAY-7","de":"zahlung PAY-7","mixed":"payment PAY-7"}),
    RouteCaseSpec("machines.status", "read", {"en":"machine X-3 status","ko":"장비 X-3 상태","es":"estado de la máquina X-3","ja":"マシンX-3の状態","de":"status der maschine X-3","mixed":"machine X-3 상태"}, temporal_scope="current"),
    RouteCaseSpec("machines.restart", "restart", {"en":"machine X-3","ko":"장비 X-3","es":"máquina X-3","ja":"マシンX-3","de":"maschine X-3","mixed":"machine X-3"}),
    RouteCaseSpec("workflow_ops.w10", "read", {"en":"automation workflows","ko":"자동화 워크플로","es":"flujos de automatización","ja":"自動化ワークフロー","de":"automatisierungs-workflows","mixed":"automation 워크플로"}),
    RouteCaseSpec("workflow_ops.w20", "create", {"en":"automation workflow","ko":"자동화 워크플로","es":"flujo de automatización","ja":"自動化ワークフロー","de":"automatisierungs-workflow","mixed":"automation 워크플로"}),
    RouteCaseSpec("workflow_ops.w30", "update", {"en":"workflow W-9","ko":"워크플로 W-9","es":"flujo W-9","ja":"ワークフローW-9","de":"workflow W-9","mixed":"workflow W-9"}),
    RouteCaseSpec("workflow_ops.w40", "cancel", {"en":"workflow W-9","ko":"워크플로 W-9","es":"flujo W-9","ja":"ワークフローW-9","de":"workflow W-9","mixed":"workflow W-9"}),
    RouteCaseSpec("workflow_ops.w50", "execute", {"en":"workflow W-9","ko":"워크플로 W-9","es":"flujo W-9","ja":"ワークフローW-9","de":"workflow W-9","mixed":"workflow W-9"}),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("bookings_api.b17", "read", {"en":"booking B-6","ko":"예약 B-6","es":"reserva B-6","ja":"予約B-6","de":"buchung B-6","mixed":"booking B-6"}),
    RouteCaseSpec("bookings_api.b28", "update", {"en":"booking B-6","ko":"예약 B-6","es":"reserva B-6","ja":"予約B-6","de":"buchung B-6","mixed":"booking B-6"}),
    RouteCaseSpec("bookings_api.b39", "cancel", {"en":"booking B-6","ko":"예약 B-6","es":"reserva B-6","ja":"予約B-6","de":"buchung B-6","mixed":"booking B-6"}),
    RouteCaseSpec("archive_ops.a01", "read", {"en":"archived records about policy","ko":"policy 관련 보관 기록","es":"registros archivados sobre policy","ja":"policyに関する保存記録","de":"archivierte einträge über policy","mixed":"policy 관련 archived records"}),
    RouteCaseSpec("archive_ops.a02", "read", {"en":"archived record A-4","ko":"보관 기록 A-4","es":"registro archivado A-4","ja":"保存記録A-4","de":"archivierter eintrag A-4","mixed":"archived record A-4"}),
    RouteCaseSpec("archive_ops.a03", "export", {"en":"archived record A-4","ko":"보관 기록 A-4","es":"registro archivado A-4","ja":"保存記録A-4","de":"archivierter eintrag A-4","mixed":"archived record A-4"}),
    RouteCaseSpec("archive_ops.a04", "share", {"en":"archived record A-4","ko":"보관 기록 A-4","es":"registro archivado A-4","ja":"保存記録A-4","de":"archivierter eintrag A-4","mixed":"archived record A-4"}),
    RouteCaseSpec("archive_ops.a05", "translate", {"en":"archived record A-4","ko":"보관 기록 A-4","es":"registro archivado A-4","ja":"保存記録A-4","de":"archivierter eintrag A-4","mixed":"archived record A-4"}),
    RouteCaseSpec("notes.list", "read", {"en":"team notes","ko":"팀 노트","es":"notas de equipo","ja":"チームノート","de":"teamnotizen","mixed":"team 노트"}),
    RouteCaseSpec("notes.create", "create", {"en":"team note","ko":"팀 노트","es":"nota de equipo","ja":"チームノート","de":"teamnotiz","mixed":"team 노트"}),
    RouteCaseSpec("notes.update", "update", {"en":"team note N-3","ko":"팀 노트 N-3","es":"nota de equipo N-3","ja":"チームノートN-3","de":"teamnotiz N-3","mixed":"team note N-3"}),
    RouteCaseSpec("notes.delete", "delete", {"en":"team note N-3","ko":"팀 노트 N-3","es":"nota de equipo N-3","ja":"チームノートN-3","de":"teamnotiz N-3","mixed":"team note N-3"}),
    RouteCaseSpec("deployments.list", "read", {"en":"deployments","ko":"배포 목록","es":"despliegues","ja":"デプロイ一覧","de":"deployments","mixed":"deployment 목록"}),
    RouteCaseSpec("deployments.restart", "restart", {"en":"deployment D-5","ko":"배포 D-5","es":"despliegue D-5","ja":"デプロイD-5","de":"deployment D-5","mixed":"deployment D-5"}),
    RouteCaseSpec("deployments.cancel", "cancel", {"en":"deployment D-5","ko":"배포 D-5","es":"despliegue D-5","ja":"デプロイD-5","de":"deployment D-5","mixed":"deployment D-5"}),
    RouteCaseSpec("deployments.execute", "execute", {"en":"deployment D-5","ko":"배포 D-5","es":"despliegue D-5","ja":"デプロイD-5","de":"deployment D-5","mixed":"deployment D-5"}),
    RouteCaseSpec("invoices.retrieve", "read", {"en":"invoice I-8","ko":"청구서 I-8","es":"factura I-8","ja":"請求書I-8","de":"rechnung I-8","mixed":"invoice I-8"}),
    RouteCaseSpec("invoices.refund", "refund", {"en":"invoice I-8","ko":"청구서 I-8","es":"factura I-8","ja":"請求書I-8","de":"rechnung I-8","mixed":"invoice I-8"}),
    RouteCaseSpec("invoices.send", "send", {"en":"invoice I-8","ko":"청구서 I-8","es":"factura I-8","ja":"請求書I-8","de":"rechnung I-8","mixed":"invoice I-8"}),
    RouteCaseSpec("signals.current", "read", {"en":"signal S-2 value","ko":"신호 S-2 값","es":"valor de señal S-2","ja":"信号S-2の値","de":"signalwert S-2","mixed":"signal S-2 값"}, temporal_scope="current"),
    RouteCaseSpec("signals.history", "read", {"en":"signal S-2 values","ko":"신호 S-2 값","es":"valores de señal S-2","ja":"信号S-2の値","de":"signalwerte S-2","mixed":"signal S-2 값"}, temporal_scope="historical"),
    RouteCaseSpec("signals.forecast", "forecast", {"en":"signal S-2 value","ko":"신호 S-2 값","es":"valor de señal S-2","ja":"信号S-2の値","de":"signalwert S-2","mixed":"signal S-2 값"}, temporal_scope="future"),
)
