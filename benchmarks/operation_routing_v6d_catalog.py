# ruff: noqa: E501
"""Identity-disjoint V6D catalogs for component-mixture experiment #399."""

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

    registry.register(
        tool_from_openapi(
            "warrants_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Warrant Service",
                    "version": "1.0.0",
                    "description": "Warrant record administration service",
                },
                "paths": {
                    "/warrants/{warrant_id}": {
                        "get": {
                            "operationId": "w14",
                            "summary": "Retrieve one already-identified warrant record",
                            "responses": {"200": {"description": "warrant"}},
                        },
                        "patch": {
                            "operationId": "w25",
                            "summary": "Update fields on an existing warrant record",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "w36",
                            "summary": "Delete an existing warrant record permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "specimen_index",
            {
                "tools": [
                    {
                        "name": "x14",
                        "description": "Search specimen index records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "x25",
                        "description": "Retrieve one already-identified specimen index record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "x36",
                        "description": "List all available specimen index records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="relays",
            description="Relay packet delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a relay packet to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a relay packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="digests",
            description="Digest document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a digest document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a digest document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple digest documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="controllers",
            description="Controller runtime service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing controller runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a daemon operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="invoices",
            description="Invoice lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new invoice",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active invoice",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed invoice payment",
                    read_only=False,
                ),
            ],
        )
    )

    surface_tension = FieldSpec(
        name="surface_tension",
        semantic_id="material.surface_tension",
        description="Surface-tension measurement",
        json_schema={"type": "number"},
        unit="mN/m",
        unit_normalization=UnitNormalizationSpec(
            dimension="surface_tension",
            canonical_unit="N/m",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="surface_tension",
            description="Surface-tension observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current surface-tension value",
                    read_only=True,
                    output_fields=[surface_tension],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical surface-tension values",
                    read_only=True,
                    output_fields=[surface_tension],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future surface-tension values",
                    read_only=True,
                    output_fields=[surface_tension],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "passes_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Access pass Service",
                    "version": "1.0.0",
                    "description": "Access pass record administration service",
                },
                "paths": {
                    "/passes/{pass_id}": {
                        "get": {
                            "operationId": "y14",
                            "summary": "Retrieve one already-identified access pass",
                            "responses": {"200": {"description": "access pass"}},
                        },
                        "patch": {
                            "operationId": "y25",
                            "summary": "Update an existing access pass",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/passes": {
                        "post": {
                            "operationId": "y36",
                            "summary": "Create a brand-new access pass",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "artifact_catalog",
            {
                "tools": [
                    {
                        "name": "z14",
                        "description": "Search artifact catalog records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "z25",
                        "description": "Retrieve one already-identified artifact catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "z36",
                        "description": "List all available artifact catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="bulletins",
            description="Bulletin delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send an bulletin payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an bulletin payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="captions",
            description="Caption conversion and analysis service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export caption content as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate caption content into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple captions for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="runners",
            description="Task runner control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing task runner",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered task runner operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="entitlements",
            description="Entitlement lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified entitlement",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active entitlement",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed entitlement payment",
                    read_only=False,
                ),
            ],
        )
    )

    thermal_conductivity = FieldSpec(
        name="thermal_conductivity",
        semantic_id="material.thermal_conductivity",
        description="Thermal-conductivity measurement",
        json_schema={"type": "number"},
        unit="W/(m·K)",
        unit_normalization=UnitNormalizationSpec(
            dimension="thermal_conductivity",
            canonical_unit="W/(m·K)",
            scale=1.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="thermal_conductivity",
            description="Thermal-conductivity observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current thermal-conductivity value",
                    read_only=True,
                    output_fields=[thermal_conductivity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical thermal-conductivity values",
                    read_only=True,
                    output_fields=[thermal_conductivity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future thermal-conductivity values",
                    read_only=True,
                    output_fields=[thermal_conductivity],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("warrants_api.w14", "retrieve", {"en":"warrant WR-7","ko":"승인 기록 WR-7","es":"autorización WR-7","ja":"認可記録WR-7","de":"autorisierung WR-7","mixed":"warrant WR-7"}),
    RouteCaseSpec("warrants_api.w25", "update", {"en":"warrant WR-7","ko":"승인 기록 WR-7","es":"autorización WR-7","ja":"認可記録WR-7","de":"autorisierung WR-7","mixed":"warrant WR-7"}),
    RouteCaseSpec("warrants_api.w36", "delete", {"en":"warrant WR-7","ko":"승인 기록 WR-7","es":"autorización WR-7","ja":"認可記録WR-7","de":"autorisierung WR-7","mixed":"warrant WR-7"}),
    RouteCaseSpec("specimen_index.x14", "search", {"en":"specimen records about perovskite","ko":"perovskite 관련 문헌 기록","es":"registros bibliográficos sobre perovskite","ja":"perovskiteに関する文献記録","de":"literaturdatensätze zu perovskite","mixed":"perovskite 관련 specimen records"}),
    RouteCaseSpec("specimen_index.x25", "retrieve", {"en":"specimen record SX-8","ko":"문헌 기록 SX-8","es":"registro bibliográfico SX-8","ja":"文献記録SX-8","de":"literaturdatensatz SX-8","mixed":"specimen record SX-8"}),
    RouteCaseSpec("specimen_index.x36", "list", {"en":"specimen records","ko":"문헌 기록","es":"registros bibliográficos","ja":"文献記録","de":"literaturdatensätze","mixed":"specimen records"}),
    RouteCaseSpec("relays.send", "send", {"en":"relay packet RL-6","ko":"인계 패킷 RL-6","es":"paquete de traspaso RL-6","ja":"引継ぎパケットRL-6","de":"übergabepaket RL-6","mixed":"relay packet RL-6"}),
    RouteCaseSpec("relays.share", "share", {"en":"relay packet RL-6","ko":"인계 패킷 RL-6","es":"paquete de traspaso RL-6","ja":"引継ぎパケットRL-6","de":"übergabepaket RL-6","mixed":"relay packet RL-6"}),
    RouteCaseSpec("digests.export", "export", {"en":"digest document DG-5","ko":"메모 문서 DG-5","es":"documento digest DG-5","ja":"メモ文書DG-5","de":"digestdokument DG-5","mixed":"digest document DG-5"}),
    RouteCaseSpec("digests.summarize", "summarize", {"en":"digest document DG-5","ko":"메모 문서 DG-5","es":"documento digest DG-5","ja":"メモ文書DG-5","de":"digestdokument DG-5","mixed":"digest document DG-5"}),
    RouteCaseSpec("digests.merge", "merge", {"en":"digest documents DG-5 and DG-6","ko":"메모 문서 DG-5과 DG-6","es":"documentos digest DG-5 y DG-6","ja":"メモ文書DG-5とDG-6","de":"digestdokumente DG-5 und DG-6","mixed":"digest documents DG-5 DG-6"}),
    RouteCaseSpec("controllers.restart", "restart", {"en":"controller CT-4","ko":"등록 서비스 DM-4","es":"servicio registrado DM-4","ja":"登録サービスDM-4","de":"registrierter dienst DM-4","mixed":"controller CT-4"}),
    RouteCaseSpec("controllers.execute", "execute", {"en":"controller operation CT-4","ko":"서비스 작업 DM-4","es":"operación de servicio DM-4","ja":"サービス操作DM-4","de":"dienstoperation DM-4","mixed":"controller operation CT-4"}),
    RouteCaseSpec("invoices.create", "create", {"en":"invoice","ko":"구매 주문","es":"orden de compra","ja":"購入注文","de":"bestellung","mixed":"invoice"}),
    RouteCaseSpec("invoices.cancel", "cancel", {"en":"invoice IN-8","ko":"구매 주문 IN-8","es":"orden IN-8","ja":"購入注文IN-8","de":"bestellung IN-8","mixed":"invoice IN-8"}),
    RouteCaseSpec("invoices.refund", "refund", {"en":"invoice payment IN-8","ko":"주문 결제 IN-8","es":"pago de pedido IN-8","ja":"注文支払いIN-8","de":"bestellzahlung IN-8","mixed":"invoice payment IN-8"}),
    RouteCaseSpec("surface_tension.current", "retrieve", {"en":"surface-tension value","ko":"표면장력 값","es":"valor de tensión superficial","ja":"表面張力値","de":"oberflächenspannungswert","mixed":"surface-tension 값"}, temporal_scope="current"),
    RouteCaseSpec("surface_tension.history", "retrieve", {"en":"surface-tension values","ko":"표면장력 값","es":"valores de tensión superficial","ja":"表面張力値","de":"oberflächenspannungswerte","mixed":"surface-tension 값"}, temporal_scope="historical"),
    RouteCaseSpec("surface_tension.forecast", "forecast", {"en":"surface-tension values","ko":"표면장력 값","es":"valores de tensión superficial","ja":"表面張力値","de":"oberflächenspannungswerte","mixed":"surface-tension 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("passes_api.y14", "retrieve", {"en":"access pass PS-4","ko":"자격 증명 PS-4","es":"credencial PS-4","ja":"資格情報PS-4","de":"zugangsnachweis PS-4","mixed":"access pass PS-4"}),
    RouteCaseSpec("passes_api.y25", "update", {"en":"access pass PS-4","ko":"자격 증명 PS-4","es":"credencial PS-4","ja":"資格情報PS-4","de":"zugangsnachweis PS-4","mixed":"access pass PS-4"}),
    RouteCaseSpec("passes_api.y36", "create", {"en":"access pass","ko":"자격 증명","es":"credencial","ja":"資格情報","de":"zugangsnachweis","mixed":"access pass"}),
    RouteCaseSpec("artifact_catalog.z14", "search", {"en":"artifact records about hafnia","ko":"hafnia 관련 시료 기록","es":"registros de muestras sobre hafnia","ja":"hafniaに関する試料記録","de":"probendatensätze zu hafnia","mixed":"hafnia 관련 artifact records"}),
    RouteCaseSpec("artifact_catalog.z25", "retrieve", {"en":"artifact record AR-7","ko":"시료 기록 AR-7","es":"registro de muestra AR-7","ja":"試料記録AR-7","de":"probendatensatz AR-7","mixed":"artifact record AR-7"}),
    RouteCaseSpec("artifact_catalog.z36", "list", {"en":"artifact records","ko":"시료 기록","es":"registros de muestras","ja":"試料記録","de":"probendatensätze","mixed":"artifact records"}),
    RouteCaseSpec("bulletins.send", "send", {"en":"bulletin payload BL-9","ko":"경보 페이로드 BL-9","es":"carga de bulletina BL-9","ja":"アラートペイロードBL-9","de":"alarmpayload BL-9","mixed":"bulletin payload BL-9"}),
    RouteCaseSpec("bulletins.share", "share", {"en":"bulletin payload BL-9","ko":"경보 페이로드 BL-9","es":"carga de bulletina BL-9","ja":"アラートペイロードBL-9","de":"alarmpayload BL-9","mixed":"bulletin payload BL-9"}),
    RouteCaseSpec("captions.export", "export", {"en":"caption CP-4","ko":"원고 CP-4","es":"manuscrito CP-4","ja":"原稿CP-4","de":"manuskript CP-4","mixed":"caption CP-4"}),
    RouteCaseSpec("captions.translate", "translate", {"en":"caption CP-4","ko":"원고 CP-4","es":"manuscrito CP-4","ja":"原稿CP-4","de":"manuskript CP-4","mixed":"caption CP-4"}),
    RouteCaseSpec("captions.compare", "compare", {"en":"captions CP-4 and CP-5","ko":"원고 CP-4과 CP-5","es":"manuscritos CP-4 y CP-5","ja":"原稿CP-4とCP-5","de":"manuskripte CP-4 und CP-5","mixed":"captions CP-4 CP-5"}),
    RouteCaseSpec("runners.restart", "restart", {"en":"task runner RN-6","ko":"처리 엔진 RN-6","es":"motor de procesamiento RN-6","ja":"処理エンジンRN-6","de":"verarbeitungsengine RN-6","mixed":"task runner RN-6"}),
    RouteCaseSpec("runners.execute", "execute", {"en":"runner operation RN-6","ko":"엔진 작업 RN-6","es":"operación de motor RN-6","ja":"エンジン操作RN-6","de":"engine-operation RN-6","mixed":"runner operation RN-6"}),
    RouteCaseSpec("entitlements.retrieve", "retrieve", {"en":"entitlement ET-3","ko":"구독 ET-3","es":"suscripción ET-3","ja":"購読ET-3","de":"abonnement ET-3","mixed":"entitlement ET-3"}),
    RouteCaseSpec("entitlements.cancel", "cancel", {"en":"entitlement ET-3","ko":"구독 ET-3","es":"suscripción ET-3","ja":"購読ET-3","de":"abonnement ET-3","mixed":"entitlement ET-3"}),
    RouteCaseSpec("entitlements.refund", "refund", {"en":"entitlement payment ET-3","ko":"구독 결제 ET-3","es":"pago de suscripción ET-3","ja":"購読支払いET-3","de":"abonnementzahlung ET-3","mixed":"entitlement payment ET-3"}),
    RouteCaseSpec("thermal_conductivity.current", "retrieve", {"en":"thermal-conductivity value","ko":"열전도도 값","es":"valor de conductividad térmica","ja":"熱伝導率","de":"wärmeleitfähigkeitswert","mixed":"thermal-conductivity 값"}, temporal_scope="current"),
    RouteCaseSpec("thermal_conductivity.history", "retrieve", {"en":"thermal-conductivity values","ko":"열전도도 값","es":"valores de conductividad térmica","ja":"熱伝導率","de":"wärmeleitfähigkeitswerte","mixed":"thermal-conductivity 값"}, temporal_scope="historical"),
    RouteCaseSpec("thermal_conductivity.forecast", "forecast", {"en":"thermal-conductivity values","ko":"열전도도 값","es":"valores de conductividad térmica","ja":"熱伝導率","de":"wärmeleitfähigkeitswerte","mixed":"thermal-conductivity 값"}, temporal_scope="future"),
)
