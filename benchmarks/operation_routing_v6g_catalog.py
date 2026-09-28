# ruff: noqa: E501
"""Identity-disjoint V6G catalogs for non-parametric kNN retrieval experiment #408."""

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
            "mandate_records_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Mandate Service",
                    "version": "1.0.0",
                    "description": "Mandate record administration service",
                },
                "paths": {
                    "/mandates/{mandate_id}": {
                        "get": {
                            "operationId": "m14",
                            "summary": "Retrieve one already-identified mandate record",
                            "responses": {"200": {"description": "mandate"}},
                        },
                        "patch": {
                            "operationId": "m25",
                            "summary": "Update fields on an existing mandate record",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "m36",
                            "summary": "Delete an existing mandate record permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "catalyst_archive",
            {
                "tools": [
                    {
                        "name": "n14",
                        "description": "Search catalyst index records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "n25",
                        "description": "Retrieve one already-identified catalyst index record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "n36",
                        "description": "List all available catalyst index records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="parcel_delivery",
            description="Parcel delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a parcel parcel to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a parcel parcel with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="brief_transform",
            description="Brief document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a brief document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a brief document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple brief documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="workcell_control",
            description="Workcell runtime service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing workcell runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a workcell operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="allocation_lifecycle",
            description="Allocation lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new allocation",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active allocation",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed allocation payment",
                    read_only=False,
                ),
            ],
        )
    )

    modulus_observatory = FieldSpec(
        name="youngs_modulus",
        semantic_id="material.youngs_modulus",
        description="Young's modulus measurement",
        json_schema={"type": "number"},
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="elastic_modulus",
            canonical_unit="Pa",
            scale=1_000_000_000.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="modulus_observatory",
            description="Young's modulus observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current Young's modulus value",
                    read_only=True,
                    output_fields=[modulus_observatory],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical Young's modulus values",
                    read_only=True,
                    output_fields=[modulus_observatory],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future Young's modulus values",
                    read_only=True,
                    output_fields=[modulus_observatory],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "grant_records_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Grant Service",
                    "version": "1.0.0",
                    "description": "Grant record administration service",
                },
                "paths": {
                    "/grants/{grant_id}": {
                        "get": {
                            "operationId": "p14",
                            "summary": "Retrieve one already-identified grant record",
                            "responses": {"200": {"description": "grant record"}},
                        },
                        "patch": {
                            "operationId": "p25",
                            "summary": "Update an existing grant record",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/grants": {
                        "post": {
                            "operationId": "p36",
                            "summary": "Create a brand-new grant record",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "powder_index",
            {
                "tools": [
                    {
                        "name": "q14",
                        "description": "Search powder catalog records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "q25",
                        "description": "Retrieve one already-identified powder catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "q36",
                        "description": "List all available powder catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="shipment_delivery",
            description="Shipment delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a shipment payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an shipment payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="transcript_transform",
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
                    description="Compare multiple transcript_transform for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="reactor_control",
            description="Reactor control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing reactor",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered reactor operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="agreement_lifecycle",
            description="Agreement lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified agreement",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active agreement",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed agreement payment",
                    read_only=False,
                ),
            ],
        )
    )

    resistivity_observatory = FieldSpec(
        name="electrical_resistivity",
        semantic_id="material.electrical_resistivity",
        description="Electrical resistivity measurement",
        json_schema={"type": "number"},
        unit="Ω·m",
        unit_normalization=UnitNormalizationSpec(
            dimension="electrical_resistivity",
            canonical_unit="Ω·m",
            scale=1.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="resistivity_observatory",
            description="Electrical resistivity observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current electrical resistivity value",
                    read_only=True,
                    output_fields=[resistivity_observatory],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical electrical resistivity values",
                    read_only=True,
                    output_fields=[resistivity_observatory],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future electrical resistivity values",
                    read_only=True,
                    output_fields=[resistivity_observatory],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("mandate_records_api.m14", "retrieve", {"en":"mandate MD-5","ko":"승인 기록 MD-5","es":"autorización MD-5","ja":"認可記録MD-5","de":"autorisierung MD-5","mixed":"mandate MD-5"}),
    RouteCaseSpec("mandate_records_api.m25", "update", {"en":"mandate MD-5","ko":"승인 기록 MD-5","es":"autorización MD-5","ja":"認可記録MD-5","de":"autorisierung MD-5","mixed":"mandate MD-5"}),
    RouteCaseSpec("mandate_records_api.m36", "delete", {"en":"mandate MD-5","ko":"승인 기록 MD-5","es":"autorización MD-5","ja":"認可記録MD-5","de":"autorisierung MD-5","mixed":"mandate MD-5"}),
    RouteCaseSpec("catalyst_archive.n14", "search", {"en":"catalyst records about titania","ko":"titania 관련 문헌 기록","es":"registros bibliográficos sobre titania","ja":"titaniaに関する文献記録","de":"literaturdatensätze zu titania","mixed":"titania 관련 catalyst records"}),
    RouteCaseSpec("catalyst_archive.n25", "retrieve", {"en":"catalyst record CT-6","ko":"문헌 기록 CT-6","es":"registro bibliográfico CT-6","ja":"文献記録CT-6","de":"literaturdatensatz CT-6","mixed":"catalyst record CT-6"}),
    RouteCaseSpec("catalyst_archive.n36", "list", {"en":"catalyst records","ko":"문헌 기록","es":"registros bibliográficos","ja":"文献記録","de":"literaturdatensätze","mixed":"catalyst records"}),
    RouteCaseSpec("parcel_delivery.send", "send", {"en":"transfer parcel PC-4","ko":"전송 패킷 PC-4","es":"paquete de transferencia PC-4","ja":"転送パケットPC-4","de":"übertragungspaket PC-4","mixed":"transfer parcel PC-4"}),
    RouteCaseSpec("parcel_delivery.share", "share", {"en":"transfer parcel PC-4","ko":"전송 패킷 PC-4","es":"paquete de transferencia PC-4","ja":"転送パケットPC-4","de":"übertragungspaket PC-4","mixed":"transfer parcel PC-4"}),
    RouteCaseSpec("brief_transform.export", "export", {"en":"brief document BR-7","ko":"메모 문서 BR-7","es":"documento brief BR-7","ja":"メモ文書BR-7","de":"briefdokument BR-7","mixed":"brief document BR-7"}),
    RouteCaseSpec("brief_transform.summarize", "summarize", {"en":"brief document BR-7","ko":"메모 문서 BR-7","es":"documento brief BR-7","ja":"メモ文書BR-7","de":"briefdokument BR-7","mixed":"brief document BR-7"}),
    RouteCaseSpec("brief_transform.merge", "merge", {"en":"brief documents BR-7 and BR-8","ko":"메모 문서 BR-7과 BR-8","es":"documentos brief BR-7 y BR-8","ja":"メモ文書BR-7とBR-8","de":"briefdokumente BR-7 und BR-8","mixed":"brief documents BR-7 BR-8"}),
    RouteCaseSpec("workcell_control.restart", "restart", {"en":"workcell WC-9","ko":"스케줄러 WC-9","es":"planificador WC-9","ja":"スケジューラWC-9","de":"workcell WC-9","mixed":"workcell WC-9"}),
    RouteCaseSpec("workcell_control.execute", "execute", {"en":"workcell operation WC-9","ko":"스케줄러 작업 WC-9","es":"operación del planificador WC-9","ja":"スケジューラ操作WC-9","de":"workcell-operation WC-9","mixed":"workcell operation WC-9"}),
    RouteCaseSpec("allocation_lifecycle.create", "create", {"en":"allocation","ko":"견적서","es":"cotización","ja":"見積書","de":"angebot","mixed":"allocation"}),
    RouteCaseSpec("allocation_lifecycle.cancel", "cancel", {"en":"allocation AL-6","ko":"견적서 AL-6","es":"cotización AL-6","ja":"見積書AL-6","de":"angebot AL-6","mixed":"allocation AL-6"}),
    RouteCaseSpec("allocation_lifecycle.refund", "refund", {"en":"allocation payment AL-6","ko":"견적 결제 AL-6","es":"pago de cotización AL-6","ja":"見積支払いAL-6","de":"angebotszahlung AL-6","mixed":"allocation payment AL-6"}),
    RouteCaseSpec("modulus_observatory.current", "retrieve", {"en":"Young's modulus value","ko":"영률 값","es":"valor del módulo de Young","ja":"ヤング率","de":"young-modul","mixed":"Young's modulus 값"}, temporal_scope="current"),
    RouteCaseSpec("modulus_observatory.history", "retrieve", {"en":"Young's modulus values","ko":"영률 값","es":"valores del módulo de Young","ja":"ヤング率","de":"young-module","mixed":"Young's modulus 값"}, temporal_scope="historical"),
    RouteCaseSpec("modulus_observatory.forecast", "forecast", {"en":"Young's modulus values","ko":"영률 값","es":"valores del módulo de Young","ja":"ヤング率","de":"young-module","mixed":"Young's modulus 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("grant_records_api.p14", "retrieve", {"en":"grant record GR-8","ko":"자격 증명 GR-8","es":"credencial GR-8","ja":"資格情報GR-8","de":"zugangsnachweis GR-8","mixed":"grant record GR-8"}),
    RouteCaseSpec("grant_records_api.p25", "update", {"en":"grant record GR-8","ko":"자격 증명 GR-8","es":"credencial GR-8","ja":"資格情報GR-8","de":"zugangsnachweis GR-8","mixed":"grant record GR-8"}),
    RouteCaseSpec("grant_records_api.p36", "create", {"en":"grant record","ko":"자격 증명","es":"credencial","ja":"資格情報","de":"zugangsnachweis","mixed":"grant record"}),
    RouteCaseSpec("powder_index.q14", "search", {"en":"powder sample records about ceria","ko":"ceria 관련 시료 기록","es":"registros de muestras sobre ceria","ja":"ceriaに関する試料記録","de":"probendatensätze zu ceria","mixed":"ceria 관련 powder sample records"}),
    RouteCaseSpec("powder_index.q25", "retrieve", {"en":"powder sample record PW-5","ko":"시료 기록 PW-5","es":"registro de muestra PW-5","ja":"試料記録PW-5","de":"probendatensatz PW-5","mixed":"powder sample record PW-5"}),
    RouteCaseSpec("powder_index.q36", "list", {"en":"powder sample records","ko":"시료 기록","es":"registros de muestras","ja":"試料記録","de":"probendatensätze","mixed":"powder sample records"}),
    RouteCaseSpec("shipment_delivery.send", "send", {"en":"shipment payload NT-4","ko":"알림 페이로드 NT-4","es":"carga de aviso NT-4","ja":"通知ペイロードNT-4","de":"hinweispayload NT-4","mixed":"shipment payload NT-4"}),
    RouteCaseSpec("shipment_delivery.share", "share", {"en":"shipment payload NT-4","ko":"알림 페이로드 NT-4","es":"carga de aviso NT-4","ja":"通知ペイロードNT-4","de":"hinweispayload NT-4","mixed":"shipment payload NT-4"}),
    RouteCaseSpec("transcript_transform.export", "export", {"en":"transcript DS-3","ko":"원고 DS-3","es":"manuscrito DS-3","ja":"原稿DS-3","de":"manuskript DS-3","mixed":"transcript DS-3"}),
    RouteCaseSpec("transcript_transform.translate", "translate", {"en":"transcript DS-3","ko":"원고 DS-3","es":"manuscrito DS-3","ja":"原稿DS-3","de":"manuskript DS-3","mixed":"transcript DS-3"}),
    RouteCaseSpec("transcript_transform.compare", "compare", {"en":"transcript_transform DS-3 and DS-4","ko":"원고 DS-3과 DS-4","es":"manuscritos DS-3 y DS-4","ja":"原稿DS-3とDS-4","de":"manuskripte DS-3 und DS-4","mixed":"transcript_transform DS-3 DS-4"}),
    RouteCaseSpec("reactor_control.restart", "restart", {"en":"reactor AC-7","ko":"처리 엔진 AC-7","es":"motor de procesamiento AC-7","ja":"処理エンジンAC-7","de":"verarbeitungsengine AC-7","mixed":"reactor AC-7"}),
    RouteCaseSpec("reactor_control.execute", "execute", {"en":"reactor operation AC-7","ko":"엔진 작업 AC-7","es":"operación de motor AC-7","ja":"エンジン操作AC-7","de":"engine-operation AC-7","mixed":"reactor operation AC-7"}),
    RouteCaseSpec("agreement_lifecycle.retrieve", "retrieve", {"en":"agreement MB-6","ko":"구독 MB-6","es":"suscripción MB-6","ja":"購読MB-6","de":"abonnement MB-6","mixed":"agreement MB-6"}),
    RouteCaseSpec("agreement_lifecycle.cancel", "cancel", {"en":"agreement MB-6","ko":"구독 MB-6","es":"suscripción MB-6","ja":"購読MB-6","de":"abonnement MB-6","mixed":"agreement MB-6"}),
    RouteCaseSpec("agreement_lifecycle.refund", "refund", {"en":"agreement payment MB-6","ko":"구독 결제 MB-6","es":"pago de suscripción MB-6","ja":"購読支払いMB-6","de":"abonnementzahlung MB-6","mixed":"agreement payment MB-6"}),
    RouteCaseSpec("resistivity_observatory.current", "retrieve", {"en":"electrical resistivity value","ko":"전기 비저항 값","es":"valor de resistividad eléctrica","ja":"電気抵抗率","de":"elektrischer spezifischer widerstand","mixed":"electrical resistivity 값"}, temporal_scope="current"),
    RouteCaseSpec("resistivity_observatory.history", "retrieve", {"en":"electrical resistivity values","ko":"전기 비저항 값","es":"valores de resistividad eléctrica","ja":"電気抵抗率","de":"elektrische spezifische widerstände","mixed":"electrical resistivity 값"}, temporal_scope="historical"),
    RouteCaseSpec("resistivity_observatory.forecast", "forecast", {"en":"electrical resistivity values","ko":"전기 비저항 값","es":"valores de resistividad eléctrica","ja":"電気抵抗率","de":"elektrische spezifische widerstände","mixed":"electrical resistivity 값"}, temporal_scope="future"),
)
