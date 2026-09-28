# ruff: noqa: E501
"""Disjoint 0.12-F catalogs for external zero-shot membership experiment #371."""

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


def _text(name: str, *, identifier: bool = False) -> FieldSpec:
    return FieldSpec(name=name, json_schema={"type": "string"}, identifier=identifier)


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    permits_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Permit Service", "version": "1.0.0"},
        "paths": {
            "/permits/{permit_id}": {
                "get": {
                    "operationId": "p17",
                    "summary": "Retrieve one already-identified permit",
                    "responses": {"200": {"description": "permit"}},
                },
                "patch": {
                    "operationId": "p28",
                    "summary": "Update fields on an existing permit",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "p39",
                    "summary": "Delete an existing permit permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("permits_api", permits_openapi))

    registry.register(
        tool_from_mcp(
            "knowledge_ops",
            {
                "tools": [
                    {
                        "name": "k17",
                        "description": "Search knowledge entries that match a query",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "k28",
                        "description": "Retrieve one already-identified knowledge entry",
                        "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}}},
                    },
                    {
                        "name": "k39",
                        "description": "List all available knowledge entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="handoff",
            description="Packet delivery and access handoff service",
            endpoints=[
                EndpointSpec(name="send", description="Send a packet to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a packet with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="transforms",
            description="Artifact transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export an artifact as an external file", read_only=True),
                EndpointSpec(name="summarize", description="Summarize an artifact into its main points", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple artifacts into one result", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="services",
            description="Managed service control",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing managed service", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered service operation", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="renewals",
            description="Renewal lifecycle and payment service",
            endpoints=[
                EndpointSpec(name="create", description="Create a new renewal request", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active renewal request", read_only=False),
                EndpointSpec(name="refund", description="Refund a paid renewal transaction", read_only=False),
            ],
        )
    )

    temp_field = FieldSpec(
        name="temperature",
        semantic_id="environment.temperature",
        description="Measured temperature",
        json_schema={"type": "number"},
        unit="degC",
        unit_normalization=UnitNormalizationSpec(
            dimension="temperature",
            canonical_unit="K",
            scale=1.0,
            offset=273.15,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="temperature",
            description="Temperature observations and forecast service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current temperature value", read_only=True, output_fields=[temp_field]),
                EndpointSpec(name="history", description="Retrieve historical temperature values", read_only=True, output_fields=[temp_field]),
                EndpointSpec(name="forecast", description="Forecast future temperature values", read_only=True, output_fields=[temp_field]),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    applications_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Application Service", "version": "1.0.0"},
        "paths": {
            "/applications/{application_id}": {
                "get": {
                    "operationId": "a17",
                    "summary": "Retrieve one already-identified application",
                    "responses": {"200": {"description": "application"}},
                },
                "patch": {
                    "operationId": "a28",
                    "summary": "Update an existing application",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/applications": {
                "post": {
                    "operationId": "a39",
                    "summary": "Create a brand-new application",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("applications_api", applications_openapi))

    registry.register(
        tool_from_mcp(
            "evidence_ops",
            {
                "tools": [
                    {
                        "name": "e17",
                        "description": "Search evidence items that match criteria",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "e28",
                        "description": "Retrieve one already-identified evidence item",
                        "inputSchema": {"type": "object", "properties": {"evidence_id": {"type": "string"}}},
                    },
                    {
                        "name": "e39",
                        "description": "List all available evidence items",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="dispatch",
            description="Message dispatch and shared-access service",
            endpoints=[
                EndpointSpec(name="send", description="Send a message to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a message with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="content_tools",
            description="Content transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export content as an external file", read_only=True),
                EndpointSpec(name="translate", description="Translate content into another human language", read_only=True),
                EndpointSpec(name="compare", description="Compare multiple content items for differences", read_only=True),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="processes",
            description="Process runtime control",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing process runtime", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered process workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="rebates",
            description="Rebate lookup and lifecycle service",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve one already-identified rebate", read_only=True),
                EndpointSpec(name="cancel", description="Cancel an active rebate request", read_only=False),
                EndpointSpec(name="refund", description="Refund a paid rebate transaction", read_only=False),
            ],
        )
    )

    pressure_field = FieldSpec(
        name="pressure",
        semantic_id="environment.pressure",
        description="Measured pressure",
        json_schema={"type": "number"},
        unit="kPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1000.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="pressure",
            description="Pressure observations and forecast service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current pressure value", read_only=True, output_fields=[pressure_field]),
                EndpointSpec(name="history", description="Retrieve historical pressure values", read_only=True, output_fields=[pressure_field]),
                EndpointSpec(name="forecast", description="Forecast future pressure values", read_only=True, output_fields=[pressure_field]),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("permits_api.p17","retrieve",{"en":"permit P-8","ko":"허가 P-8","es":"permiso P-8","ja":"許可P-8","de":"genehmigung P-8","mixed":"permit P-8"}),
    RouteCaseSpec("permits_api.p28","update",{"en":"permit P-8","ko":"허가 P-8","es":"permiso P-8","ja":"許可P-8","de":"genehmigung P-8","mixed":"permit P-8"}),
    RouteCaseSpec("permits_api.p39","delete",{"en":"permit P-8","ko":"허가 P-8","es":"permiso P-8","ja":"許可P-8","de":"genehmigung P-8","mixed":"permit P-8"}),
    RouteCaseSpec("knowledge_ops.k17","search",{"en":"knowledge entries about polymer","ko":"polymer 관련 지식 항목","es":"entradas de conocimiento sobre polymer","ja":"polymerに関する知識項目","de":"wissenseinträge zu polymer","mixed":"polymer 관련 knowledge entries"}),
    RouteCaseSpec("knowledge_ops.k28","retrieve",{"en":"knowledge entry K-4","ko":"지식 항목 K-4","es":"entrada de conocimiento K-4","ja":"知識項目K-4","de":"wissenseintrag K-4","mixed":"knowledge entry K-4"}),
    RouteCaseSpec("knowledge_ops.k39","list",{"en":"knowledge entries","ko":"지식 항목","es":"entradas de conocimiento","ja":"知識項目","de":"wissenseinträge","mixed":"knowledge entries"}),
    RouteCaseSpec("handoff.send","send",{"en":"packet PK-5","ko":"패킷 PK-5","es":"paquete PK-5","ja":"パケットPK-5","de":"paket PK-5","mixed":"packet PK-5"}),
    RouteCaseSpec("handoff.share","share",{"en":"packet PK-5","ko":"패킷 PK-5","es":"paquete PK-5","ja":"パケットPK-5","de":"paket PK-5","mixed":"packet PK-5"}),
    RouteCaseSpec("transforms.export","export",{"en":"artifact AR-3","ko":"아티팩트 AR-3","es":"artefacto AR-3","ja":"アーティファクトAR-3","de":"artefakt AR-3","mixed":"artifact AR-3"}),
    RouteCaseSpec("transforms.summarize","summarize",{"en":"artifact AR-3","ko":"아티팩트 AR-3","es":"artefacto AR-3","ja":"アーティファクトAR-3","de":"artefakt AR-3","mixed":"artifact AR-3"}),
    RouteCaseSpec("transforms.merge","merge",{"en":"artifacts AR-3 and AR-4","ko":"아티팩트 AR-3과 AR-4","es":"artefactos AR-3 y AR-4","ja":"アーティファクトAR-3とAR-4","de":"artefakte AR-3 und AR-4","mixed":"artifacts AR-3 AR-4"}),
    RouteCaseSpec("services.restart","restart",{"en":"service S-2","ko":"서비스 S-2","es":"servicio S-2","ja":"サービスS-2","de":"dienst S-2","mixed":"service S-2"}),
    RouteCaseSpec("services.execute","execute",{"en":"service operation S-2","ko":"서비스 작업 S-2","es":"operación de servicio S-2","ja":"サービス操作S-2","de":"dienstoperation S-2","mixed":"service operation S-2"}),
    RouteCaseSpec("renewals.create","create",{"en":"renewal","ko":"갱신 요청","es":"renovación","ja":"更新申請","de":"verlängerung","mixed":"renewal"}),
    RouteCaseSpec("renewals.cancel","cancel",{"en":"renewal R-7","ko":"갱신 요청 R-7","es":"renovación R-7","ja":"更新申請R-7","de":"verlängerung R-7","mixed":"renewal R-7"}),
    RouteCaseSpec("renewals.refund","refund",{"en":"renewal payment R-7","ko":"갱신 결제 R-7","es":"pago de renovación R-7","ja":"更新支払いR-7","de":"verlängerungszahlung R-7","mixed":"renewal payment R-7"}),
    RouteCaseSpec("temperature.current","retrieve",{"en":"temperature value","ko":"온도 값","es":"valor de temperatura","ja":"温度値","de":"temperaturwert","mixed":"temperature 값"},temporal_scope="current"),
    RouteCaseSpec("temperature.history","retrieve",{"en":"temperature values","ko":"온도 값","es":"valores de temperatura","ja":"温度値","de":"temperaturwerte","mixed":"temperature 값"},temporal_scope="historical"),
    RouteCaseSpec("temperature.forecast","forecast",{"en":"temperature values","ko":"온도 값","es":"valores de temperatura","ja":"温度値","de":"temperaturwerte","mixed":"temperature 값"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("applications_api.a17","retrieve",{"en":"application A-6","ko":"신청서 A-6","es":"solicitud A-6","ja":"申請A-6","de":"antrag A-6","mixed":"application A-6"}),
    RouteCaseSpec("applications_api.a28","update",{"en":"application A-6","ko":"신청서 A-6","es":"solicitud A-6","ja":"申請A-6","de":"antrag A-6","mixed":"application A-6"}),
    RouteCaseSpec("applications_api.a39","create",{"en":"application","ko":"신청서","es":"solicitud","ja":"申請","de":"antrag","mixed":"application"}),
    RouteCaseSpec("evidence_ops.e17","search",{"en":"evidence items about catalyst","ko":"catalyst 관련 증거 항목","es":"elementos de evidencia sobre catalyst","ja":"catalystに関する証拠項目","de":"belege zu catalyst","mixed":"catalyst 관련 evidence items"}),
    RouteCaseSpec("evidence_ops.e28","retrieve",{"en":"evidence item E-9","ko":"증거 항목 E-9","es":"elemento de evidencia E-9","ja":"証拠項目E-9","de":"beleg E-9","mixed":"evidence item E-9"}),
    RouteCaseSpec("evidence_ops.e39","list",{"en":"evidence items","ko":"증거 항목","es":"elementos de evidencia","ja":"証拠項目","de":"belege","mixed":"evidence items"}),
    RouteCaseSpec("dispatch.send","send",{"en":"message MSG-2","ko":"메시지 MSG-2","es":"mensaje MSG-2","ja":"メッセージMSG-2","de":"nachricht MSG-2","mixed":"message MSG-2"}),
    RouteCaseSpec("dispatch.share","share",{"en":"message MSG-2","ko":"메시지 MSG-2","es":"mensaje MSG-2","ja":"メッセージMSG-2","de":"nachricht MSG-2","mixed":"message MSG-2"}),
    RouteCaseSpec("content_tools.export","export",{"en":"content C-1","ko":"콘텐츠 C-1","es":"contenido C-1","ja":"コンテンツC-1","de":"inhalt C-1","mixed":"content C-1"}),
    RouteCaseSpec("content_tools.translate","translate",{"en":"content C-1","ko":"콘텐츠 C-1","es":"contenido C-1","ja":"コンテンツC-1","de":"inhalt C-1","mixed":"content C-1"}),
    RouteCaseSpec("content_tools.compare","compare",{"en":"content C-1 and C-2","ko":"콘텐츠 C-1과 C-2","es":"contenidos C-1 y C-2","ja":"コンテンツC-1とC-2","de":"inhalte C-1 und C-2","mixed":"content C-1 C-2"}),
    RouteCaseSpec("processes.restart","restart",{"en":"process P-5","ko":"프로세스 P-5","es":"proceso P-5","ja":"プロセスP-5","de":"prozess P-5","mixed":"process P-5"}),
    RouteCaseSpec("processes.execute","execute",{"en":"process workflow P-5","ko":"프로세스 워크플로 P-5","es":"flujo de proceso P-5","ja":"プロセスワークフローP-5","de":"prozess-workflow P-5","mixed":"process workflow P-5"}),
    RouteCaseSpec("rebates.retrieve","retrieve",{"en":"rebate RB-4","ko":"리베이트 RB-4","es":"reembolso RB-4","ja":"リベートRB-4","de":"rabatt RB-4","mixed":"rebate RB-4"}),
    RouteCaseSpec("rebates.cancel","cancel",{"en":"rebate RB-4","ko":"리베이트 RB-4","es":"reembolso RB-4","ja":"リベートRB-4","de":"rabatt RB-4","mixed":"rebate RB-4"}),
    RouteCaseSpec("rebates.refund","refund",{"en":"rebate payment RB-4","ko":"리베이트 결제 RB-4","es":"pago de reembolso RB-4","ja":"リベート支払いRB-4","de":"rabattzahlung RB-4","mixed":"rebate payment RB-4"}),
    RouteCaseSpec("pressure.current","retrieve",{"en":"pressure value","ko":"압력 값","es":"valor de presión","ja":"圧力値","de":"druckwert","mixed":"pressure 값"},temporal_scope="current"),
    RouteCaseSpec("pressure.history","retrieve",{"en":"pressure values","ko":"압력 값","es":"valores de presión","ja":"圧力値","de":"druckwerte","mixed":"pressure 값"},temporal_scope="historical"),
    RouteCaseSpec("pressure.forecast","forecast",{"en":"pressure values","ko":"압력 값","es":"valores de presión","ja":"圧力値","de":"druckwerte","mixed":"pressure 값"},temporal_scope="future"),
)
