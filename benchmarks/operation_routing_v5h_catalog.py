# ruff: noqa: E501
"""Disjoint V5H catalogs for pairwise NLI membership experiment #378."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")


@dataclass(frozen=True)
class RouteCaseSpec:
    route_id: str
    leaf: str
    objects: dict[str, str]
    temporal_scope: str | None = None


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    certificates_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Certificate Records", "version": "1.0.0"},
        "paths": {
            "/certificates/{certificate_id}": {
                "get": {
                    "operationId": "crt17",
                    "summary": "Retrieve one already-identified certificate",
                    "responses": {"200": {"description": "certificate"}},
                },
                "patch": {
                    "operationId": "crt28",
                    "summary": "Update fields on an existing certificate",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "crt39",
                    "summary": "Delete an existing certificate permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(
        tool_from_openapi("certificate_records_api", certificates_openapi)
    )

    registry.register(
        tool_from_mcp(
            "specimen_index_ops",
            {
                "tools": [
                    {
                        "name": "sp17",
                        "description": "Search specimen index entries that match criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "sp28",
                        "description": "Retrieve one already-identified specimen index entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"specimen_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "sp39",
                        "description": "List all available specimen index entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="document_delivery",
            description="Document delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a document to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a document with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="report_transform",
            description="Report transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a report as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a report into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple reports for differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="node_control",
            description="Managed node runtime control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing managed node",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered node operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="reservation_credits",
            description="Reservation-credit lifecycle and reimbursement",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new reservation-credit request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active reservation-credit request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid reservation-credit transaction",
                    read_only=False,
                ),
            ],
        )
    )

    flow = FieldSpec(
        name="flow_rate",
        semantic_id="process.flow_rate",
        description="Measured volumetric flow rate",
        json_schema={"type": "number"},
        unit="mL/s",
        unit_normalization=UnitNormalizationSpec(
            dimension="volumetric_flow_rate",
            canonical_unit="L/s",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="flow_probe",
            description="Flow observations and forecast",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current flow rate",
                    read_only=True,
                    output_fields=[flow],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical flow rates",
                    read_only=True,
                    output_fields=[flow],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future flow rates",
                    read_only=True,
                    output_fields=[flow],
                ),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    authorizations_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Authorization Records", "version": "1.0.0"},
        "paths": {
            "/authorizations/{authorization_id}": {
                "get": {
                    "operationId": "auth17",
                    "summary": "Retrieve one already-identified authorization",
                    "responses": {"200": {"description": "authorization"}},
                },
                "patch": {
                    "operationId": "auth28",
                    "summary": "Update an existing authorization",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/authorizations": {
                "post": {
                    "operationId": "auth39",
                    "summary": "Create a brand-new authorization",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(
        tool_from_openapi("authorization_records_api", authorizations_openapi)
    )

    registry.register(
        tool_from_mcp(
            "dataset_index_ops",
            {
                "tools": [
                    {
                        "name": "ds17",
                        "description": "Search dataset index entries that match criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "ds28",
                        "description": "Retrieve one already-identified dataset index entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"dataset_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "ds39",
                        "description": "List all available dataset index entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="notice_delivery",
            description="Notice delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a notice to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a notice with another user",
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
                    description="Export text as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate text into another human language",
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
            name="task_control",
            description="Task runtime control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing task runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered task workflow",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="fee_claims",
            description="Fee claim and reimbursement service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified fee claim",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active fee claim",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid fee claim amount",
                    read_only=False,
                ),
            ],
        )
    )

    power = FieldSpec(
        name="power",
        semantic_id="energy.power",
        description="Measured electrical power",
        json_schema={"type": "number"},
        unit="W",
        unit_normalization=UnitNormalizationSpec(
            dimension="power",
            canonical_unit="kW",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="power_probe",
            description="Power observations and forecast",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current power value",
                    read_only=True,
                    output_fields=[power],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical power values",
                    read_only=True,
                    output_fields=[power],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future power values",
                    read_only=True,
                    output_fields=[power],
                ),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("certificate_records_api.crt17","retrieve",{"en":"certificate C-8","ko":"인증서 C-8","es":"certificado C-8","ja":"証明書C-8","de":"zertifikat C-8","mixed":"certificate C-8"}),
    RouteCaseSpec("certificate_records_api.crt28","update",{"en":"certificate C-8","ko":"인증서 C-8","es":"certificado C-8","ja":"証明書C-8","de":"zertifikat C-8","mixed":"certificate C-8"}),
    RouteCaseSpec("certificate_records_api.crt39","delete",{"en":"certificate C-8","ko":"인증서 C-8","es":"certificado C-8","ja":"証明書C-8","de":"zertifikat C-8","mixed":"certificate C-8"}),
    RouteCaseSpec("specimen_index_ops.sp17","search",{"en":"specimen entries about resin","ko":"resin 관련 시편 항목","es":"entradas de espécimen sobre resin","ja":"resinに関する試料項目","de":"probeneinträge zu resin","mixed":"resin 관련 specimen entries"}),
    RouteCaseSpec("specimen_index_ops.sp28","retrieve",{"en":"specimen entry SP-4","ko":"시편 항목 SP-4","es":"entrada de espécimen SP-4","ja":"試料項目SP-4","de":"probeneintrag SP-4","mixed":"specimen entry SP-4"}),
    RouteCaseSpec("specimen_index_ops.sp39","list",{"en":"specimen entries","ko":"시편 항목","es":"entradas de espécimen","ja":"試料項目","de":"probeneinträge","mixed":"specimen entries"}),
    RouteCaseSpec("document_delivery.send","send",{"en":"document D-5","ko":"문서 D-5","es":"documento D-5","ja":"文書D-5","de":"dokument D-5","mixed":"document D-5"}),
    RouteCaseSpec("document_delivery.share","share",{"en":"document D-5","ko":"문서 D-5","es":"documento D-5","ja":"文書D-5","de":"dokument D-5","mixed":"document D-5"}),
    RouteCaseSpec("report_transform.export","export",{"en":"report RP-3","ko":"보고서 RP-3","es":"informe RP-3","ja":"レポートRP-3","de":"bericht RP-3","mixed":"report RP-3"}),
    RouteCaseSpec("report_transform.summarize","summarize",{"en":"report RP-3","ko":"보고서 RP-3","es":"informe RP-3","ja":"レポートRP-3","de":"bericht RP-3","mixed":"report RP-3"}),
    RouteCaseSpec("report_transform.compare","compare",{"en":"reports RP-3 and RP-4","ko":"보고서 RP-3과 RP-4","es":"informes RP-3 y RP-4","ja":"レポートRP-3とRP-4","de":"berichte RP-3 und RP-4","mixed":"reports RP-3 RP-4"}),
    RouteCaseSpec("node_control.restart","restart",{"en":"node N-2","ko":"노드 N-2","es":"nodo N-2","ja":"ノードN-2","de":"knoten N-2","mixed":"node N-2"}),
    RouteCaseSpec("node_control.execute","execute",{"en":"node operation N-2","ko":"노드 작업 N-2","es":"operación de nodo N-2","ja":"ノード操作N-2","de":"knotenoperation N-2","mixed":"node operation N-2"}),
    RouteCaseSpec("reservation_credits.create","create",{"en":"reservation-credit request","ko":"예약 크레딧 요청","es":"solicitud de crédito de reserva","ja":"予約クレジット申請","de":"reservierungsgutschrift-antrag","mixed":"reservation credit request"}),
    RouteCaseSpec("reservation_credits.cancel","cancel",{"en":"reservation-credit request RC-7","ko":"예약 크레딧 요청 RC-7","es":"solicitud de crédito RC-7","ja":"予約クレジット申請RC-7","de":"reservierungsgutschrift RC-7","mixed":"reservation credit RC-7"}),
    RouteCaseSpec("reservation_credits.refund","refund",{"en":"reservation-credit payment RC-7","ko":"예약 크레딧 결제 RC-7","es":"pago de crédito RC-7","ja":"予約クレジット支払いRC-7","de":"reservierungsgutschrift-zahlung RC-7","mixed":"reservation credit payment RC-7"}),
    RouteCaseSpec("flow_probe.current","retrieve",{"en":"flow rate","ko":"유량","es":"caudal","ja":"流量","de":"durchfluss","mixed":"flow rate"},temporal_scope="current"),
    RouteCaseSpec("flow_probe.history","retrieve",{"en":"flow rates","ko":"유량 값","es":"valores de caudal","ja":"流量値","de":"durchflusswerte","mixed":"flow rates"},temporal_scope="historical"),
    RouteCaseSpec("flow_probe.forecast","forecast",{"en":"flow rates","ko":"유량 값","es":"valores de caudal","ja":"流量値","de":"durchflusswerte","mixed":"flow rates"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("authorization_records_api.auth17","retrieve",{"en":"authorization A-6","ko":"승인 A-6","es":"autorización A-6","ja":"承認A-6","de":"autorisierung A-6","mixed":"authorization A-6"}),
    RouteCaseSpec("authorization_records_api.auth28","update",{"en":"authorization A-6","ko":"승인 A-6","es":"autorización A-6","ja":"承認A-6","de":"autorisierung A-6","mixed":"authorization A-6"}),
    RouteCaseSpec("authorization_records_api.auth39","create",{"en":"authorization","ko":"승인","es":"autorización","ja":"承認","de":"autorisierung","mixed":"authorization"}),
    RouteCaseSpec("dataset_index_ops.ds17","search",{"en":"dataset entries about laminate","ko":"laminate 관련 데이터셋 항목","es":"entradas de dataset sobre laminate","ja":"laminateに関するデータセット項目","de":"datensatzeinträge zu laminate","mixed":"laminate 관련 dataset entries"}),
    RouteCaseSpec("dataset_index_ops.ds28","retrieve",{"en":"dataset entry DS-9","ko":"데이터셋 항목 DS-9","es":"entrada de dataset DS-9","ja":"データセット項目DS-9","de":"datensatzeintrag DS-9","mixed":"dataset entry DS-9"}),
    RouteCaseSpec("dataset_index_ops.ds39","list",{"en":"dataset entries","ko":"데이터셋 항목","es":"entradas de dataset","ja":"データセット項目","de":"datensatzeinträge","mixed":"dataset entries"}),
    RouteCaseSpec("notice_delivery.send","send",{"en":"notice NT-2","ko":"공지 NT-2","es":"aviso NT-2","ja":"通知NT-2","de":"mitteilung NT-2","mixed":"notice NT-2"}),
    RouteCaseSpec("notice_delivery.share","share",{"en":"notice NT-2","ko":"공지 NT-2","es":"aviso NT-2","ja":"通知NT-2","de":"mitteilung NT-2","mixed":"notice NT-2"}),
    RouteCaseSpec("text_transform.export","export",{"en":"text T-1","ko":"텍스트 T-1","es":"texto T-1","ja":"テキストT-1","de":"text T-1","mixed":"text T-1"}),
    RouteCaseSpec("text_transform.translate","translate",{"en":"text T-1","ko":"텍스트 T-1","es":"texto T-1","ja":"テキストT-1","de":"text T-1","mixed":"text T-1"}),
    RouteCaseSpec("text_transform.merge","merge",{"en":"texts T-1 and T-2","ko":"텍스트 T-1과 T-2","es":"textos T-1 y T-2","ja":"テキストT-1とT-2","de":"texte T-1 und T-2","mixed":"texts T-1 T-2"}),
    RouteCaseSpec("task_control.restart","restart",{"en":"task TK-5","ko":"태스크 TK-5","es":"tarea TK-5","ja":"タスクTK-5","de":"aufgabe TK-5","mixed":"task TK-5"}),
    RouteCaseSpec("task_control.execute","execute",{"en":"task workflow TK-5","ko":"태스크 워크플로 TK-5","es":"flujo de tarea TK-5","ja":"タスクワークフローTK-5","de":"aufgaben-workflow TK-5","mixed":"task workflow TK-5"}),
    RouteCaseSpec("fee_claims.retrieve","retrieve",{"en":"fee claim F-4","ko":"수수료 청구 F-4","es":"reclamo de tarifa F-4","ja":"手数料請求F-4","de":"gebührenanspruch F-4","mixed":"fee claim F-4"}),
    RouteCaseSpec("fee_claims.cancel","cancel",{"en":"fee claim F-4","ko":"수수료 청구 F-4","es":"reclamo de tarifa F-4","ja":"手数料請求F-4","de":"gebührenanspruch F-4","mixed":"fee claim F-4"}),
    RouteCaseSpec("fee_claims.refund","refund",{"en":"fee payment F-4","ko":"수수료 결제 F-4","es":"pago de tarifa F-4","ja":"手数料支払いF-4","de":"gebührenzahlung F-4","mixed":"fee payment F-4"}),
    RouteCaseSpec("power_probe.current","retrieve",{"en":"power","ko":"전력","es":"potencia","ja":"電力","de":"leistung","mixed":"power"},temporal_scope="current"),
    RouteCaseSpec("power_probe.history","retrieve",{"en":"power values","ko":"전력 값","es":"valores de potencia","ja":"電力値","de":"leistungswerte","mixed":"power values"},temporal_scope="historical"),
    RouteCaseSpec("power_probe.forecast","forecast",{"en":"power values","ko":"전력 값","es":"valores de potencia","ja":"電力値","de":"leistungswerte","mixed":"power values"},temporal_scope="future"),
)
