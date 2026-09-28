# ruff: noqa: E501
"""Identity-disjoint V6B catalogs for hard-negative ellipsoid experiment #395."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec, UnitNormalizationSpec
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

    registry.register(
        tool_from_openapi(
            "permits_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Permit Service",
                    "version": "1.0.0",
                    "description": "Permit record administration service",
                },
                "paths": {
                    "/permits/{permit_id}": {
                        "get": {
                            "operationId": "p41",
                            "summary": "Retrieve one already-identified permit",
                            "responses": {"200": {"description": "permit"}},
                        },
                        "patch": {
                            "operationId": "p52",
                            "summary": "Update fields on an existing permit",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "p63",
                            "summary": "Delete an existing permit permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "archive_ops",
            {
                "tools": [
                    {
                        "name": "a41",
                        "description": "Search archive records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "a52",
                        "description": "Retrieve one already-identified archive record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "a63",
                        "description": "List all available archive records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="dispatch",
            description="Shipment dispatch and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a shipment packet to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a shipment packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="briefings",
            description="Briefing document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a briefing document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a briefing document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple briefing documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="workers",
            description="Background worker control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing background worker",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered worker operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="claims",
            description="Expense claim lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new expense claim",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active expense claim",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed claim transaction",
                    read_only=False,
                ),
            ],
        )
    )

    viscosity = FieldSpec(
        name="dynamic_viscosity",
        semantic_id="material.dynamic_viscosity",
        description="Dynamic viscosity measurement",
        json_schema={"type": "number"},
        unit="mPa·s",
        unit_normalization=UnitNormalizationSpec(
            dimension="dynamic_viscosity",
            canonical_unit="Pa·s",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="viscosity",
            description="Viscosity observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current viscosity value",
                    read_only=True,
                    output_fields=[viscosity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical viscosity values",
                    read_only=True,
                    output_fields=[viscosity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future viscosity values",
                    read_only=True,
                    output_fields=[viscosity],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "badges_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Badge Service",
                    "version": "1.0.0",
                    "description": "Badge record administration service",
                },
                "paths": {
                    "/badges/{badge_id}": {
                        "get": {
                            "operationId": "b41",
                            "summary": "Retrieve one already-identified badge",
                            "responses": {"200": {"description": "badge"}},
                        },
                        "patch": {
                            "operationId": "b52",
                            "summary": "Update an existing badge",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/badges": {
                        "post": {
                            "operationId": "b63",
                            "summary": "Create a brand-new badge",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "inventory_index",
            {
                "tools": [
                    {
                        "name": "i41",
                        "description": "Search inventory index records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "i52",
                        "description": "Retrieve one already-identified inventory index record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "i63",
                        "description": "List all available inventory index records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="notifications",
            description="Notification delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a notification payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a notification payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="transcription",
            description="Transcript conversion and analysis service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export transcript content as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate transcript content into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple transcripts for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="pipelines",
            description="Data pipeline control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing data pipeline",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered data pipeline workflow",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="reservations",
            description="Reservation lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified reservation",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active reservation",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed reservation payment",
                    read_only=False,
                ),
            ],
        )
    )

    density = FieldSpec(
        name="mass_density",
        semantic_id="material.mass_density",
        description="Mass density measurement",
        json_schema={"type": "number"},
        unit="g/cm^3",
        unit_normalization=UnitNormalizationSpec(
            dimension="mass_density",
            canonical_unit="kg/m^3",
            scale=1000.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="density",
            description="Density observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current density value",
                    read_only=True,
                    output_fields=[density],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical density values",
                    read_only=True,
                    output_fields=[density],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future density values",
                    read_only=True,
                    output_fields=[density],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("permits_api.p41", "retrieve", {"en":"permit PM-8","ko":"허가서 PM-8","es":"permiso PM-8","ja":"許可証PM-8","de":"genehmigung PM-8","mixed":"permit PM-8"}),
    RouteCaseSpec("permits_api.p52", "update", {"en":"permit PM-8","ko":"허가서 PM-8","es":"permiso PM-8","ja":"許可証PM-8","de":"genehmigung PM-8","mixed":"permit PM-8"}),
    RouteCaseSpec("permits_api.p63", "delete", {"en":"permit PM-8","ko":"허가서 PM-8","es":"permiso PM-8","ja":"許可証PM-8","de":"genehmigung PM-8","mixed":"permit PM-8"}),
    RouteCaseSpec("archive_ops.a41", "search", {"en":"archive records about aerogel","ko":"aerogel 관련 보관 기록","es":"registros de archivo sobre aerogel","ja":"aerogelに関する保管記録","de":"archivdatensätze zu aerogel","mixed":"aerogel 관련 archive records"}),
    RouteCaseSpec("archive_ops.a52", "retrieve", {"en":"archive record AR-6","ko":"보관 기록 AR-6","es":"registro de archivo AR-6","ja":"保管記録AR-6","de":"archivdatensatz AR-6","mixed":"archive record AR-6"}),
    RouteCaseSpec("archive_ops.a63", "list", {"en":"archive records","ko":"보관 기록","es":"registros de archivo","ja":"保管記録","de":"archivdatensätze","mixed":"archive records"}),
    RouteCaseSpec("dispatch.send", "send", {"en":"shipment packet SH-7","ko":"배송 패킷 SH-7","es":"paquete de envío SH-7","ja":"配送パケットSH-7","de":"sendungspaket SH-7","mixed":"shipment packet SH-7"}),
    RouteCaseSpec("dispatch.share", "share", {"en":"shipment packet SH-7","ko":"배송 패킷 SH-7","es":"paquete de envío SH-7","ja":"配送パケットSH-7","de":"sendungspaket SH-7","mixed":"shipment packet SH-7"}),
    RouteCaseSpec("briefings.export", "export", {"en":"briefing document BF-3","ko":"브리핑 문서 BF-3","es":"documento informativo BF-3","ja":"ブリーフィング文書BF-3","de":"briefingdokument BF-3","mixed":"briefing document BF-3"}),
    RouteCaseSpec("briefings.summarize", "summarize", {"en":"briefing document BF-3","ko":"브리핑 문서 BF-3","es":"documento informativo BF-3","ja":"ブリーフィング文書BF-3","de":"briefingdokument BF-3","mixed":"briefing document BF-3"}),
    RouteCaseSpec("briefings.merge", "merge", {"en":"briefing documents BF-3 and BF-4","ko":"브리핑 문서 BF-3과 BF-4","es":"documentos informativos BF-3 y BF-4","ja":"ブリーフィング文書BF-3とBF-4","de":"briefingdokumente BF-3 und BF-4","mixed":"briefing documents BF-3 BF-4"}),
    RouteCaseSpec("workers.restart", "restart", {"en":"worker WK-2","ko":"작업 워커 WK-2","es":"worker WK-2","ja":"ワーカーWK-2","de":"worker WK-2","mixed":"worker WK-2"}),
    RouteCaseSpec("workers.execute", "execute", {"en":"worker operation WK-2","ko":"워커 작업 WK-2","es":"operación de worker WK-2","ja":"ワーカー操作WK-2","de":"worker-operation WK-2","mixed":"worker operation WK-2"}),
    RouteCaseSpec("claims.create", "create", {"en":"expense claim","ko":"비용 청구","es":"reclamación de gastos","ja":"経費請求","de":"spesenabrechnung","mixed":"expense claim"}),
    RouteCaseSpec("claims.cancel", "cancel", {"en":"expense claim CLM-7","ko":"비용 청구 CLM-7","es":"reclamación CLM-7","ja":"経費請求CLM-7","de":"spesenabrechnung CLM-7","mixed":"expense claim CLM-7"}),
    RouteCaseSpec("claims.refund", "refund", {"en":"claim payment CLM-7","ko":"청구 결제 CLM-7","es":"pago de reclamación CLM-7","ja":"請求支払いCLM-7","de":"abrechnungszahlung CLM-7","mixed":"claim payment CLM-7"}),
    RouteCaseSpec("viscosity.current", "retrieve", {"en":"viscosity value","ko":"점도 값","es":"valor de viscosidad","ja":"粘度値","de":"viskositätswert","mixed":"viscosity 값"}, temporal_scope="current"),
    RouteCaseSpec("viscosity.history", "retrieve", {"en":"viscosity values","ko":"점도 값","es":"valores de viscosidad","ja":"粘度値","de":"viskositätswerte","mixed":"viscosity 값"}, temporal_scope="historical"),
    RouteCaseSpec("viscosity.forecast", "forecast", {"en":"viscosity values","ko":"점도 값","es":"valores de viscosidad","ja":"粘度値","de":"viskositätswerte","mixed":"viscosity 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("badges_api.b41", "retrieve", {"en":"badge BG-6","ko":"배지 BG-6","es":"insignia BG-6","ja":"バッジBG-6","de":"abzeichen BG-6","mixed":"badge BG-6"}),
    RouteCaseSpec("badges_api.b52", "update", {"en":"badge BG-6","ko":"배지 BG-6","es":"insignia BG-6","ja":"バッジBG-6","de":"abzeichen BG-6","mixed":"badge BG-6"}),
    RouteCaseSpec("badges_api.b63", "create", {"en":"badge","ko":"배지","es":"insignia","ja":"バッジ","de":"abzeichen","mixed":"badge"}),
    RouteCaseSpec("inventory_index.i41", "search", {"en":"inventory index records about tungsten","ko":"tungsten 관련 재고 인덱스 기록","es":"registros de índice sobre tungsten","ja":"tungstenに関する在庫索引記録","de":"indexdatensätze zu tungsten","mixed":"tungsten 관련 inventory index records"}),
    RouteCaseSpec("inventory_index.i52", "retrieve", {"en":"inventory index record IV-9","ko":"재고 인덱스 기록 IV-9","es":"registro de índice IV-9","ja":"在庫索引記録IV-9","de":"indexdatensatz IV-9","mixed":"inventory index record IV-9"}),
    RouteCaseSpec("inventory_index.i63", "list", {"en":"inventory index records","ko":"재고 인덱스 기록","es":"registros de índice","ja":"在庫索引記録","de":"indexdatensätze","mixed":"inventory index records"}),
    RouteCaseSpec("notifications.send", "send", {"en":"notification payload NT-2","ko":"알림 페이로드 NT-2","es":"carga de notificación NT-2","ja":"通知ペイロードNT-2","de":"benachrichtigungspayload NT-2","mixed":"notification payload NT-2"}),
    RouteCaseSpec("notifications.share", "share", {"en":"notification payload NT-2","ko":"알림 페이로드 NT-2","es":"carga de notificación NT-2","ja":"通知ペイロードNT-2","de":"benachrichtigungspayload NT-2","mixed":"notification payload NT-2"}),
    RouteCaseSpec("transcription.export", "export", {"en":"transcript TS-1","ko":"전사문 TS-1","es":"transcripción TS-1","ja":"文字起こしTS-1","de":"transkript TS-1","mixed":"transcript TS-1"}),
    RouteCaseSpec("transcription.translate", "translate", {"en":"transcript TS-1","ko":"전사문 TS-1","es":"transcripción TS-1","ja":"文字起こしTS-1","de":"transkript TS-1","mixed":"transcript TS-1"}),
    RouteCaseSpec("transcription.compare", "compare", {"en":"transcripts TS-1 and TS-2","ko":"전사문 TS-1과 TS-2","es":"transcripciones TS-1 y TS-2","ja":"文字起こしTS-1とTS-2","de":"transkripte TS-1 und TS-2","mixed":"transcripts TS-1 TS-2"}),
    RouteCaseSpec("pipelines.restart", "restart", {"en":"data pipeline DP-5","ko":"데이터 파이프라인 DP-5","es":"canalización de datos DP-5","ja":"データパイプラインDP-5","de":"datenpipeline DP-5","mixed":"data pipeline DP-5"}),
    RouteCaseSpec("pipelines.execute", "execute", {"en":"pipeline workflow DP-5","ko":"파이프라인 워크플로 DP-5","es":"flujo de canalización DP-5","ja":"パイプラインワークフローDP-5","de":"pipeline-workflow DP-5","mixed":"pipeline workflow DP-5"}),
    RouteCaseSpec("reservations.retrieve", "retrieve", {"en":"reservation RS-4","ko":"예약 RS-4","es":"reserva RS-4","ja":"予約RS-4","de":"reservierung RS-4","mixed":"reservation RS-4"}),
    RouteCaseSpec("reservations.cancel", "cancel", {"en":"reservation RS-4","ko":"예약 RS-4","es":"reserva RS-4","ja":"予約RS-4","de":"reservierung RS-4","mixed":"reservation RS-4"}),
    RouteCaseSpec("reservations.refund", "refund", {"en":"reservation payment RS-4","ko":"예약 결제 RS-4","es":"pago de reserva RS-4","ja":"予約支払いRS-4","de":"reservierungszahlung RS-4","mixed":"reservation payment RS-4"}),
    RouteCaseSpec("density.current", "retrieve", {"en":"density value","ko":"밀도 값","es":"valor de densidad","ja":"密度値","de":"dichtewert","mixed":"density 값"}, temporal_scope="current"),
    RouteCaseSpec("density.history", "retrieve", {"en":"density values","ko":"밀도 값","es":"valores de densidad","ja":"密度値","de":"dichtewerte","mixed":"density 값"}, temporal_scope="historical"),
    RouteCaseSpec("density.forecast", "forecast", {"en":"density values","ko":"밀도 값","es":"valores de densidad","ja":"密度値","de":"dichtewerte","mixed":"density 값"}, temporal_scope="future"),
)
