# ruff: noqa: E501
"""Identity-disjoint V6E catalogs for non-parametric kNN experiment #401."""

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
            "consents_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Consent Service",
                    "version": "1.0.0",
                    "description": "Consent record administration service",
                },
                "paths": {
                    "/consents/{consent_id}": {
                        "get": {
                            "operationId": "g41",
                            "summary": "Retrieve one already-identified consent record",
                            "responses": {"200": {"description": "consent"}},
                        },
                        "patch": {
                            "operationId": "g52",
                            "summary": "Update fields on an existing consent record",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "g63",
                            "summary": "Delete an existing consent record permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "assay_index",
            {
                "tools": [
                    {
                        "name": "h41",
                        "description": "Search assay index records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "h52",
                        "description": "Retrieve one already-identified assay index record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "h63",
                        "description": "List all available assay index records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="packets",
            description="Packet packet delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a packet packet to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a packet packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="ledgers",
            description="Ledger document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a ledger document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a ledger document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple ledger documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="schedulers",
            description="Scheduler runtime service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing scheduler runtime",
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
            name="quotations",
            description="Quotation lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new quotation",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active quotation",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed quotation payment",
                    read_only=False,
                ),
            ],
        )
    )

    expansion_coefficient = FieldSpec(
        name="expansion_coefficient",
        semantic_id="material.expansion_coefficient",
        description="Thermal-expansion coefficient measurement",
        json_schema={"type": "number"},
        unit="1/K",
        unit_normalization=UnitNormalizationSpec(
            dimension="expansion_coefficient",
            canonical_unit="1/K",
            scale=1.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="expansion_coefficient",
            description="Thermal-expansion coefficient observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current thermal-expansion coefficient value",
                    read_only=True,
                    output_fields=[expansion_coefficient],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical thermal-expansion coefficient values",
                    read_only=True,
                    output_fields=[expansion_coefficient],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future thermal-expansion coefficient values",
                    read_only=True,
                    output_fields=[expansion_coefficient],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "tokens_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Access token Service",
                    "version": "1.0.0",
                    "description": "Access token record administration service",
                },
                "paths": {
                    "/tokens/{token_id}": {
                        "get": {
                            "operationId": "j41",
                            "summary": "Retrieve one already-identified access token",
                            "responses": {"200": {"description": "access token"}},
                        },
                        "patch": {
                            "operationId": "j52",
                            "summary": "Update an existing access token",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/tokens": {
                        "post": {
                            "operationId": "j63",
                            "summary": "Create a brand-new access token",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "batch_index",
            {
                "tools": [
                    {
                        "name": "k41",
                        "description": "Search batch catalog records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "k52",
                        "description": "Retrieve one already-identified batch catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "k63",
                        "description": "List all available batch catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="notices",
            description="Notice delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send an notice payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an notice payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="dossiers",
            description="Dossier conversion and analysis service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export dossier content as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate dossier content into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple dossiers for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="actuators",
            description="Actuator control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing actuator",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered actuator operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="memberships",
            description="Membership lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified membership",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active membership",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed membership payment",
                    read_only=False,
                ),
            ],
        )
    )

    heat_capacity = FieldSpec(
        name="heat_capacity",
        semantic_id="material.specific_heat_capacity",
        description="Specific heat-capacity measurement",
        json_schema={"type": "number"},
        unit="J/(kg·K)",
        unit_normalization=UnitNormalizationSpec(
            dimension="specific_heat_capacity",
            canonical_unit="J/(kg·K)",
            scale=1.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="heat_capacity",
            description="Specific heat-capacity observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current heat-capacity value",
                    read_only=True,
                    output_fields=[heat_capacity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical heat-capacity values",
                    read_only=True,
                    output_fields=[heat_capacity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future heat-capacity values",
                    read_only=True,
                    output_fields=[heat_capacity],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("consents_api.g41", "retrieve", {"en":"consent CN-5","ko":"승인 기록 CN-5","es":"autorización CN-5","ja":"認可記録CN-5","de":"autorisierung CN-5","mixed":"consent CN-5"}),
    RouteCaseSpec("consents_api.g52", "update", {"en":"consent CN-5","ko":"승인 기록 CN-5","es":"autorización CN-5","ja":"認可記録CN-5","de":"autorisierung CN-5","mixed":"consent CN-5"}),
    RouteCaseSpec("consents_api.g63", "delete", {"en":"consent CN-5","ko":"승인 기록 CN-5","es":"autorización CN-5","ja":"認可記録CN-5","de":"autorisierung CN-5","mixed":"consent CN-5"}),
    RouteCaseSpec("assay_index.h41", "search", {"en":"assay records about titania","ko":"titania 관련 문헌 기록","es":"registros bibliográficos sobre titania","ja":"titaniaに関する文献記録","de":"literaturdatensätze zu titania","mixed":"titania 관련 assay records"}),
    RouteCaseSpec("assay_index.h52", "retrieve", {"en":"assay record AY-6","ko":"문헌 기록 AY-6","es":"registro bibliográfico AY-6","ja":"文献記録AY-6","de":"literaturdatensatz AY-6","mixed":"assay record AY-6"}),
    RouteCaseSpec("assay_index.h63", "list", {"en":"assay records","ko":"문헌 기록","es":"registros bibliográficos","ja":"文献記録","de":"literaturdatensätze","mixed":"assay records"}),
    RouteCaseSpec("packets.send", "send", {"en":"packet packet PK-4","ko":"인계 패킷 PK-4","es":"paquete de traspaso PK-4","ja":"引継ぎパケットPK-4","de":"übergabepaket PK-4","mixed":"packet packet PK-4"}),
    RouteCaseSpec("packets.share", "share", {"en":"packet packet PK-4","ko":"인계 패킷 PK-4","es":"paquete de traspaso PK-4","ja":"引継ぎパケットPK-4","de":"übergabepaket PK-4","mixed":"packet packet PK-4"}),
    RouteCaseSpec("ledgers.export", "export", {"en":"ledger document LG-7","ko":"메모 문서 LG-7","es":"documento ledger LG-7","ja":"メモ文書LG-7","de":"ledgerdokument LG-7","mixed":"ledger document LG-7"}),
    RouteCaseSpec("ledgers.summarize", "summarize", {"en":"ledger document LG-7","ko":"메모 문서 LG-7","es":"documento ledger LG-7","ja":"メモ文書LG-7","de":"ledgerdokument LG-7","mixed":"ledger document LG-7"}),
    RouteCaseSpec("ledgers.merge", "merge", {"en":"ledger documents LG-7 and LG-8","ko":"메모 문서 LG-7과 LG-8","es":"documentos ledger LG-7 y LG-8","ja":"メモ文書LG-7とLG-8","de":"ledgerdokumente LG-7 und LG-8","mixed":"ledger documents LG-7 LG-8"}),
    RouteCaseSpec("schedulers.restart", "restart", {"en":"controller SC-9","ko":"등록 서비스 DM-4","es":"servicio registrado DM-4","ja":"登録サービスDM-4","de":"registrierter dienst DM-4","mixed":"controller SC-9"}),
    RouteCaseSpec("schedulers.execute", "execute", {"en":"scheduler operation SC-9","ko":"서비스 작업 DM-4","es":"operación de servicio DM-4","ja":"サービス操作DM-4","de":"dienstoperation DM-4","mixed":"scheduler operation SC-9"}),
    RouteCaseSpec("quotations.create", "create", {"en":"quotation","ko":"구매 주문","es":"orden de compra","ja":"購入注文","de":"bestellung","mixed":"quotation"}),
    RouteCaseSpec("quotations.cancel", "cancel", {"en":"quotation QT-6","ko":"구매 주문 QT-6","es":"orden QT-6","ja":"購入注文QT-6","de":"bestellung QT-6","mixed":"quotation QT-6"}),
    RouteCaseSpec("quotations.refund", "refund", {"en":"quotation payment QT-6","ko":"주문 결제 QT-6","es":"pago de pedido QT-6","ja":"注文支払いQT-6","de":"bestellzahlung QT-6","mixed":"quotation payment QT-6"}),
    RouteCaseSpec("expansion_coefficient.current", "retrieve", {"en":"thermal-expansion coefficient value","ko":"열팽창계수 값","es":"valor de coeficiente de expansión térmica","ja":"熱膨張係数値","de":"wärmeausdehnungskoeffizient","mixed":"thermal-expansion coefficient 값"}, temporal_scope="current"),
    RouteCaseSpec("expansion_coefficient.history", "retrieve", {"en":"thermal-expansion coefficient values","ko":"열팽창계수 값","es":"valores de coeficiente de expansión térmica","ja":"熱膨張係数値","de":"wärmeausdehnungskoeffiziente","mixed":"thermal-expansion coefficient 값"}, temporal_scope="historical"),
    RouteCaseSpec("expansion_coefficient.forecast", "forecast", {"en":"thermal-expansion coefficient values","ko":"열팽창계수 값","es":"valores de coeficiente de expansión térmica","ja":"熱膨張係数値","de":"wärmeausdehnungskoeffiziente","mixed":"thermal-expansion coefficient 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("tokens_api.j41", "retrieve", {"en":"access token TK-8","ko":"자격 증명 TK-8","es":"credencial TK-8","ja":"資格情報TK-8","de":"zugangsnachweis TK-8","mixed":"access token TK-8"}),
    RouteCaseSpec("tokens_api.j52", "update", {"en":"access token TK-8","ko":"자격 증명 TK-8","es":"credencial TK-8","ja":"資格情報TK-8","de":"zugangsnachweis TK-8","mixed":"access token TK-8"}),
    RouteCaseSpec("tokens_api.j63", "create", {"en":"access token","ko":"자격 증명","es":"credencial","ja":"資格情報","de":"zugangsnachweis","mixed":"access token"}),
    RouteCaseSpec("batch_index.k41", "search", {"en":"batch records about ceria","ko":"ceria 관련 시료 기록","es":"registros de muestras sobre ceria","ja":"ceriaに関する試料記録","de":"probendatensätze zu ceria","mixed":"ceria 관련 batch records"}),
    RouteCaseSpec("batch_index.k52", "retrieve", {"en":"batch record BT-5","ko":"시료 기록 BT-5","es":"registro de muestra BT-5","ja":"試料記録BT-5","de":"probendatensatz BT-5","mixed":"batch record BT-5"}),
    RouteCaseSpec("batch_index.k63", "list", {"en":"batch records","ko":"시료 기록","es":"registros de muestras","ja":"試料記録","de":"probendatensätze","mixed":"batch records"}),
    RouteCaseSpec("notices.send", "send", {"en":"notice payload NT-4","ko":"경보 페이로드 NT-4","es":"carga de noticea NT-4","ja":"アラートペイロードNT-4","de":"alarmpayload NT-4","mixed":"notice payload NT-4"}),
    RouteCaseSpec("notices.share", "share", {"en":"notice payload NT-4","ko":"경보 페이로드 NT-4","es":"carga de noticea NT-4","ja":"アラートペイロードNT-4","de":"alarmpayload NT-4","mixed":"notice payload NT-4"}),
    RouteCaseSpec("dossiers.export", "export", {"en":"dossier DS-3","ko":"원고 DS-3","es":"manuscrito DS-3","ja":"原稿DS-3","de":"manuskript DS-3","mixed":"dossier DS-3"}),
    RouteCaseSpec("dossiers.translate", "translate", {"en":"dossier DS-3","ko":"원고 DS-3","es":"manuscrito DS-3","ja":"原稿DS-3","de":"manuskript DS-3","mixed":"dossier DS-3"}),
    RouteCaseSpec("dossiers.compare", "compare", {"en":"dossiers DS-3 and DS-4","ko":"원고 DS-3과 DS-4","es":"manuscritos DS-3 y DS-4","ja":"原稿DS-3とDS-4","de":"manuskripte DS-3 und DS-4","mixed":"dossiers DS-3 DS-4"}),
    RouteCaseSpec("actuators.restart", "restart", {"en":"actuator AC-7","ko":"처리 엔진 AC-7","es":"motor de procesamiento AC-7","ja":"処理エンジンAC-7","de":"verarbeitungsengine AC-7","mixed":"actuator AC-7"}),
    RouteCaseSpec("actuators.execute", "execute", {"en":"actuator operation AC-7","ko":"엔진 작업 AC-7","es":"operación de motor AC-7","ja":"エンジン操作AC-7","de":"engine-operation AC-7","mixed":"actuator operation AC-7"}),
    RouteCaseSpec("memberships.retrieve", "retrieve", {"en":"membership MB-6","ko":"구독 MB-6","es":"suscripción MB-6","ja":"購読MB-6","de":"abonnement MB-6","mixed":"membership MB-6"}),
    RouteCaseSpec("memberships.cancel", "cancel", {"en":"membership MB-6","ko":"구독 MB-6","es":"suscripción MB-6","ja":"購読MB-6","de":"abonnement MB-6","mixed":"membership MB-6"}),
    RouteCaseSpec("memberships.refund", "refund", {"en":"membership payment MB-6","ko":"구독 결제 MB-6","es":"pago de suscripción MB-6","ja":"購読支払いMB-6","de":"abonnementzahlung MB-6","mixed":"membership payment MB-6"}),
    RouteCaseSpec("heat_capacity.current", "retrieve", {"en":"heat-capacity value","ko":"비열용량 값","es":"valor de capacidad calorífica específica","ja":"比熱容量","de":"spezifischer-wärmekapazitätswert","mixed":"heat-capacity 값"}, temporal_scope="current"),
    RouteCaseSpec("heat_capacity.history", "retrieve", {"en":"heat-capacity values","ko":"비열용량 값","es":"valores de capacidad calorífica específica","ja":"比熱容量","de":"spezifischer-wärmekapazitätswerte","mixed":"heat-capacity 값"}, temporal_scope="historical"),
    RouteCaseSpec("heat_capacity.forecast", "forecast", {"en":"heat-capacity values","ko":"비열용량 값","es":"valores de capacidad calorífica específica","ja":"比熱容量","de":"spezifischer-wärmekapazitätswerte","mixed":"heat-capacity 값"}, temporal_scope="future"),
)
