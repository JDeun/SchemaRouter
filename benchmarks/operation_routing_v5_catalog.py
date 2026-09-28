"""Disjoint 0.12 development and confirmation catalogs for experiment #347."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")


@dataclass(frozen=True)
class RouteCaseSpec:
    route_id: str
    surface_action: str
    object_terms: dict[str, str]
    temporal_scope: str | None = None
    detail_terms: dict[str, str] | None = None


def _field(name: str, *, identifier: bool = False, unit: str | None = None) -> FieldSpec:
    schema = {"type": "number"} if unit else {"type": "string"}
    return FieldSpec(
        name=name,
        json_schema=schema,
        unit=unit,
        identifier=identifier,
    )


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        ToolSpec(
            name="shipments",
            description="Shipment tracking and delivery timing service",
            endpoints=[
                EndpointSpec(
                    name="status",
                    description="Get current shipment tracking status",
                    operation_aliases=["current shipment status", "track shipment now"],
                    read_only=True,
                    output_fields=[
                        _field("tracking_id", identifier=True),
                        _field("status"),
                    ],
                ),
                EndpointSpec(
                    name="eta",
                    description="Forecast future delivery arrival time for a shipment",
                    operation_aliases=["delivery forecast", "predicted arrival"],
                    read_only=True,
                    output_fields=[
                        _field("tracking_id", identifier=True),
                        _field("estimated_arrival"),
                    ],
                ),
            ],
        )
    )

    contacts_openapi = {
        "openapi": "3.1.0",
        "info": {
            "title": "Contact Profile Service",
            "version": "1.0.0",
            "description": "Contact profile retrieval and editing",
        },
        "paths": {
            "/contacts/{contact_id}": {
                "get": {
                    "operationId": "alpha_17",
                    "summary": "Retrieve one contact profile",
                    "parameters": [
                        {
                            "name": "contact_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "contact",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "contact_id": {"type": "string"},
                                            "display_name": {"type": "string"},
                                            "phone": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "patch": {
                    "operationId": "gamma_41",
                    "summary": "Update an existing contact profile",
                    "parameters": [
                        {
                            "name": "contact_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "display_name": {"type": "string"},
                                        "phone": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/contacts": {
                "post": {
                    "operationId": "beta_23",
                    "summary": "Create a new contact profile",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "display_name": {"type": "string"},
                                        "phone": {"type": "string"},
                                    },
                                    "required": ["display_name"],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("contacts_api", contacts_openapi))

    registry.register(
        tool_from_mcp(
            "media_ops",
            {
                "tools": [
                    {
                        "name": "x17",
                        "description": "Search media assets by tag or owner",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "tag": {"type": "string"},
                                "owner": {"type": "string"},
                            },
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "title": {"type": "string"},
                            },
                        },
                    },
                    {
                        "name": "q9",
                        "description": "Retrieve one media asset and its metadata",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"asset_id": {"type": "string"}},
                            "required": ["asset_id"],
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "title": {"type": "string"},
                                "owner": {"type": "string"},
                            },
                        },
                    },
                    {
                        "name": "r2",
                        "description": "Update the title of an existing media asset",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "title": {"type": "string"},
                            },
                            "required": ["asset_id", "title"],
                        },
                    },
                    {
                        "name": "z8",
                        "description": "Delete a media asset permanently",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"asset_id": {"type": "string"}},
                            "required": ["asset_id"],
                        },
                    },
                    {
                        "name": "m4",
                        "description": "Send a media asset to a review queue",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"asset_id": {"type": "string"}},
                            "required": ["asset_id"],
                        },
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="reports",
            description="Business report catalog and export service",
            endpoints=[
                EndpointSpec(
                    name="list",
                    description="List available business reports",
                    operation_aliases=["list reports", "browse reports"],
                    read_only=True,
                    output_fields=[_field("report_id", identifier=True), _field("title")],
                ),
                EndpointSpec(
                    name="export",
                    description="Export a business report as a file",
                    operation_aliases=["export report", "download report"],
                    read_only=True,
                    output_fields=[_field("report_id", identifier=True), _field("download_url")],
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="orders",
            description="Order lookup and order lifecycle operations",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    description="Retrieve an order by order number",
                    operation_aliases=["find order", "get order"],
                    read_only=True,
                    output_fields=[_field("order_id", identifier=True), _field("status")],
                ),
                EndpointSpec(
                    name="update",
                    description="Update shipping details for an existing order",
                    operation_aliases=["update order", "change order details"],
                    read_only=False,
                    output_fields=[_field("order_id", identifier=True), _field("status")],
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an existing order",
                    operation_aliases=["cancel order", "abort order"],
                    read_only=False,
                    output_fields=[_field("order_id", identifier=True), _field("status")],
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid order",
                    operation_aliases=["refund order", "reimburse order"],
                    read_only=False,
                    output_fields=[_field("order_id", identifier=True), _field("status")],
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="devices",
            description="Managed device status and control service",
            endpoints=[
                EndpointSpec(
                    name="status",
                    description="Retrieve current managed-device status",
                    operation_aliases=["device status", "current device state"],
                    read_only=True,
                    output_fields=[_field("device_id", identifier=True), _field("status")],
                ),
                EndpointSpec(
                    name="restart",
                    description="Restart a managed device",
                    operation_aliases=["restart device", "reboot device"],
                    read_only=False,
                    output_fields=[_field("device_id", identifier=True), _field("status")],
                ),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    parcels_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Parcel Service", "version": "1.0.0"},
        "paths": {
            "/parcels/{parcel_id}": {
                "get": {
                    "operationId": "p11",
                    "summary": "Get current parcel tracking state",
                    "parameters": [
                        {
                            "name": "parcel_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/pickups": {
                "post": {
                    "operationId": "p22",
                    "summary": "Create a new parcel pickup request",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"parcel_id": {"type": "string"}},
                                    "required": ["parcel_id"],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}},
                }
            },
            "/parcels/{parcel_id}/cancel": {
                "post": {
                    "operationId": "p33",
                    "summary": "Cancel a parcel delivery",
                    "parameters": [
                        {
                            "name": "parcel_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "cancelled"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("parcels_api", parcels_openapi))

    registry.register(
        tool_from_mcp(
            "documents_ops",
            {
                "tools": [
                    {
                        "name": "d1",
                        "description": "Search secure documents by title",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"title": {"type": "string"}},
                        },
                    },
                    {
                        "name": "d2",
                        "description": "Retrieve one secure document",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"document_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "d3",
                        "description": "Share a secure document with another user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "document_id": {"type": "string"},
                                "user": {"type": "string"},
                            },
                        },
                    },
                    {
                        "name": "d4",
                        "description": "Delete a secure document permanently",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"document_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "d5",
                        "description": "Translate a secure document into another language",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "document_id": {"type": "string"},
                                "language": {"type": "string"},
                            },
                        },
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="alerts",
            description="Alert rule management service",
            endpoints=[
                EndpointSpec(name="list", description="List alert rules", read_only=True),
                EndpointSpec(name="create", description="Create a new alert rule", read_only=False),
                EndpointSpec(name="update", description="Update an alert rule", read_only=False),
                EndpointSpec(
                    name="delete",
                    description="Delete an alert rule",
                    read_only=False,
                    destructive=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="subscriptions",
            description="Subscription account management",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve subscription details", read_only=True),
                EndpointSpec(name="update", description="Update subscription settings", read_only=False),
                EndpointSpec(name="cancel", description="Cancel a subscription", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="jobs",
            description="Background job monitoring and control",
            endpoints=[
                EndpointSpec(name="list", description="List background jobs", read_only=True),
                EndpointSpec(name="restart", description="Restart a background job", read_only=False),
                EndpointSpec(name="cancel", description="Cancel a background job", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="analytics",
            description="Analytics snapshots, history and forecasts",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current analytics snapshot",
                    read_only=True,
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical analytics observations",
                    read_only=True,
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future analytics values",
                    read_only=True,
                ),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("shipments.status", "read", {"en":"shipment status","ko":"배송 상태","es":"estado del envío","ja":"配送状況","de":"sendungsstatus","mixed":"shipment 배송 상태"}, temporal_scope="current"),
    RouteCaseSpec("shipments.eta", "forecast", {"en":"shipment arrival","ko":"배송 도착","es":"llegada del envío","ja":"配送到着","de":"sendungsankunft","mixed":"shipment 도착"}, temporal_scope="future"),
    RouteCaseSpec("contacts_api.alpha_17", "retrieve", {"en":"contact profile","ko":"연락처 프로필","es":"perfil de contacto","ja":"連絡先プロフィール","de":"kontaktprofil","mixed":"contact 프로필"}),
    RouteCaseSpec("contacts_api.beta_23", "create", {"en":"contact profile","ko":"연락처","es":"contacto","ja":"連絡先","de":"kontakt","mixed":"contact 연락처"}),
    RouteCaseSpec("contacts_api.gamma_41", "update", {"en":"contact profile","ko":"연락처 프로필","es":"perfil de contacto","ja":"連絡先プロフィール","de":"kontaktprofil","mixed":"contact 프로필"}),
    RouteCaseSpec("media_ops.x17", "search", {"en":"media assets","ko":"미디어 자산","es":"recursos multimedia","ja":"メディア資産","de":"medienobjekte","mixed":"media 자산"}, detail_terms={"en":"tagged launch","ko":"launch 태그","es":"con etiqueta launch","ja":"launchタグ","de":"mit tag launch","mixed":"launch tag"}),
    RouteCaseSpec("media_ops.q9", "retrieve", {"en":"media asset metadata","ko":"미디어 자산 메타데이터","es":"metadatos del recurso multimedia","ja":"メディア資産メタデータ","de":"medienmetadaten","mixed":"media asset metadata"}),
    RouteCaseSpec("media_ops.r2", "update", {"en":"media asset title","ko":"미디어 자산 제목","es":"título del recurso multimedia","ja":"メディア資産タイトル","de":"titel des medienobjekts","mixed":"media asset 제목"}),
    RouteCaseSpec("media_ops.z8", "delete", {"en":"media asset","ko":"미디어 자산","es":"recurso multimedia","ja":"メディア資産","de":"medienobjekt","mixed":"media asset"}),
    RouteCaseSpec("media_ops.m4", "send", {"en":"media asset","ko":"미디어 자산","es":"recurso multimedia","ja":"メディア資産","de":"medienobjekt","mixed":"media asset"}, detail_terms={"en":"to review","ko":"검토 대기열로","es":"a revisión","ja":"レビューへ","de":"zur prüfung","mixed":"review queue로"}),
    RouteCaseSpec("reports.list", "list", {"en":"business reports","ko":"업무 보고서","es":"informes empresariales","ja":"業務レポート","de":"geschäftsberichte","mixed":"business 보고서"}),
    RouteCaseSpec("reports.export", "export", {"en":"business report R-7","ko":"업무 보고서 R-7","es":"informe empresarial R-7","ja":"業務レポートR-7","de":"geschäftsbericht R-7","mixed":"business report R-7"}),
    RouteCaseSpec("orders.lookup", "retrieve", {"en":"order O-42","ko":"주문 O-42","es":"pedido O-42","ja":"注文O-42","de":"bestellung O-42","mixed":"order O-42"}),
    RouteCaseSpec("orders.update", "update", {"en":"order O-42 shipping details","ko":"주문 O-42 배송 정보","es":"datos de envío del pedido O-42","ja":"注文O-42の配送情報","de":"versanddaten der bestellung O-42","mixed":"order O-42 배송 정보"}),
    RouteCaseSpec("orders.cancel", "cancel", {"en":"order O-42","ko":"주문 O-42","es":"pedido O-42","ja":"注文O-42","de":"bestellung O-42","mixed":"order O-42"}),
    RouteCaseSpec("orders.refund", "refund", {"en":"order O-42","ko":"주문 O-42","es":"pedido O-42","ja":"注文O-42","de":"bestellung O-42","mixed":"order O-42"}),
    RouteCaseSpec("devices.status", "retrieve", {"en":"device D-9 status","ko":"기기 D-9 상태","es":"estado del dispositivo D-9","ja":"デバイスD-9の状態","de":"status von gerät D-9","mixed":"device D-9 상태"}, temporal_scope="current"),
    RouteCaseSpec("devices.restart", "restart", {"en":"device D-9","ko":"기기 D-9","es":"dispositivo D-9","ja":"デバイスD-9","de":"gerät D-9","mixed":"device D-9"}),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("parcels_api.p11", "retrieve", {"en":"parcel P-8 status","ko":"소포 P-8 상태","es":"estado del paquete P-8","ja":"荷物P-8の状態","de":"paket P-8 status","mixed":"parcel P-8 상태"}, temporal_scope="current"),
    RouteCaseSpec("parcels_api.p22", "create", {"en":"parcel P-8 pickup","ko":"소포 P-8 픽업","es":"recogida del paquete P-8","ja":"荷物P-8の集荷","de":"abholung für paket P-8","mixed":"parcel P-8 pickup"}),
    RouteCaseSpec("parcels_api.p33", "cancel", {"en":"parcel P-8 delivery","ko":"소포 P-8 배송","es":"entrega del paquete P-8","ja":"荷物P-8の配送","de":"lieferung von paket P-8","mixed":"parcel P-8 배송"}),
    RouteCaseSpec("documents_ops.d1", "search", {"en":"secure documents","ko":"보안 문서","es":"documentos seguros","ja":"安全な文書","de":"sichere dokumente","mixed":"secure 문서"}, detail_terms={"en":"about NDA","ko":"NDA 관련","es":"sobre NDA","ja":"NDAについて","de":"über NDA","mixed":"NDA 관련"}),
    RouteCaseSpec("documents_ops.d2", "retrieve", {"en":"secure document D-7","ko":"보안 문서 D-7","es":"documento seguro D-7","ja":"安全な文書D-7","de":"sicheres dokument D-7","mixed":"secure document D-7"}),
    RouteCaseSpec("documents_ops.d3", "share", {"en":"secure document D-7","ko":"보안 문서 D-7","es":"documento seguro D-7","ja":"安全な文書D-7","de":"sicheres dokument D-7","mixed":"secure document D-7"}),
    RouteCaseSpec("documents_ops.d4", "delete", {"en":"secure document D-7","ko":"보안 문서 D-7","es":"documento seguro D-7","ja":"安全な文書D-7","de":"sicheres dokument D-7","mixed":"secure document D-7"}),
    RouteCaseSpec("documents_ops.d5", "translate", {"en":"secure document D-7","ko":"보안 문서 D-7","es":"documento seguro D-7","ja":"安全な文書D-7","de":"sicheres dokument D-7","mixed":"secure document D-7"}),
    RouteCaseSpec("alerts.list", "list", {"en":"alert rules","ko":"알림 규칙","es":"reglas de alerta","ja":"アラートルール","de":"alarmregeln","mixed":"alert 규칙"}),
    RouteCaseSpec("alerts.create", "create", {"en":"alert rule","ko":"알림 규칙","es":"regla de alerta","ja":"アラートルール","de":"alarmregel","mixed":"alert 규칙"}),
    RouteCaseSpec("alerts.update", "update", {"en":"alert rule A-3","ko":"알림 규칙 A-3","es":"regla de alerta A-3","ja":"アラートルールA-3","de":"alarmregel A-3","mixed":"alert rule A-3"}),
    RouteCaseSpec("alerts.delete", "delete", {"en":"alert rule A-3","ko":"알림 규칙 A-3","es":"regla de alerta A-3","ja":"アラートルールA-3","de":"alarmregel A-3","mixed":"alert rule A-3"}),
    RouteCaseSpec("subscriptions.retrieve", "retrieve", {"en":"subscription S-2","ko":"구독 S-2","es":"suscripción S-2","ja":"サブスクリプションS-2","de":"abonnement S-2","mixed":"subscription S-2"}),
    RouteCaseSpec("subscriptions.update", "update", {"en":"subscription S-2 settings","ko":"구독 S-2 설정","es":"configuración de suscripción S-2","ja":"サブスクリプションS-2の設定","de":"einstellungen von abonnement S-2","mixed":"subscription S-2 설정"}),
    RouteCaseSpec("subscriptions.cancel", "cancel", {"en":"subscription S-2","ko":"구독 S-2","es":"suscripción S-2","ja":"サブスクリプションS-2","de":"abonnement S-2","mixed":"subscription S-2"}),
    RouteCaseSpec("jobs.list", "list", {"en":"background jobs","ko":"백그라운드 작업","es":"trabajos en segundo plano","ja":"バックグラウンドジョブ","de":"hintergrundjobs","mixed":"background 작업"}),
    RouteCaseSpec("jobs.restart", "restart", {"en":"background job J-4","ko":"백그라운드 작업 J-4","es":"trabajo J-4","ja":"ジョブJ-4","de":"job J-4","mixed":"background job J-4"}),
    RouteCaseSpec("jobs.cancel", "cancel", {"en":"background job J-4","ko":"백그라운드 작업 J-4","es":"trabajo J-4","ja":"ジョブJ-4","de":"job J-4","mixed":"background job J-4"}),
    RouteCaseSpec("analytics.current", "retrieve", {"en":"analytics snapshot","ko":"분석 스냅샷","es":"instantánea analítica","ja":"分析スナップショット","de":"analyse-snapshot","mixed":"analytics 스냅샷"}, temporal_scope="current"),
    RouteCaseSpec("analytics.history", "retrieve", {"en":"analytics observations","ko":"분석 관측값","es":"observaciones analíticas","ja":"分析観測値","de":"analysewerte","mixed":"analytics 관측값"}, temporal_scope="historical"),
    RouteCaseSpec("analytics.forecast", "forecast", {"en":"analytics values","ko":"분석 값","es":"valores analíticos","ja":"分析値","de":"analysewerte","mixed":"analytics 값"}, temporal_scope="future"),
)
