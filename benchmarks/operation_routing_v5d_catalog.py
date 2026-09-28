# ruff: noqa: E501
"""Disjoint 0.12-D catalogs for asymmetric ontology-veto experiment #358."""

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


def _field(name: str, *, identifier: bool = False, unit: str | None = None) -> FieldSpec:
    return FieldSpec(
        name=name,
        json_schema={"type": "number" if unit else "string"},
        unit=unit,
        identifier=identifier,
    )


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    incidents = {
        "openapi": "3.1.0",
        "info": {"title": "Incident Service", "version": "1.0.0"},
        "paths": {
            "/incidents/{incident_id}": {
                "get": {
                    "operationId": "i17",
                    "summary": "Retrieve one existing incident by identifier",
                    "responses": {"200": {"description": "incident"}},
                },
                "patch": {
                    "operationId": "i28",
                    "summary": "Update fields on an existing incident",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "i39",
                    "summary": "Delete an existing incident permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("incidents_api", incidents))

    registry.register(
        tool_from_mcp(
            "repository_ops",
            {
                "tools": [
                    {"name":"r11","description":"Search repository entries matching a query","inputSchema":{"type":"object","properties":{"query":{"type":"string"}}}},
                    {"name":"r22","description":"Retrieve one already-identified repository entry","inputSchema":{"type":"object","properties":{"entry_id":{"type":"string"}}}},
                    {"name":"r33","description":"List all repository entries","inputSchema":{"type":"object","properties":{}}},
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="handoff",
            description="Packet delivery and access handoff",
            endpoints=[
                EndpointSpec(name="send", description="Send a packet to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a packet with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="artifact_ops",
            description="Artifact transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export an artifact to an external file", read_only=True),
                EndpointSpec(name="translate", description="Translate an artifact into another human language", read_only=True),
                EndpointSpec(name="summarize", description="Summarize an artifact into its main points", read_only=True),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="processes",
            description="Managed process control",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing managed process", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered process workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="enrollments",
            description="Enrollment lifecycle and payment service",
            endpoints=[
                EndpointSpec(name="create", description="Create a new enrollment", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active enrollment", read_only=False),
                EndpointSpec(name="refund", description="Refund a paid enrollment charge", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="traffic",
            description="Traffic observations and forecasting",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve current traffic level", read_only=True, output_fields=[_field("level", unit="vehicles/hour")]),
                EndpointSpec(name="history", description="Retrieve historical traffic levels", read_only=True, output_fields=[_field("level", unit="vehicles/hour")]),
                EndpointSpec(name="forecast", description="Forecast future traffic levels", read_only=True, output_fields=[_field("level", unit="vehicles/hour")]),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    records = {
        "openapi": "3.1.0",
        "info": {"title": "Record Service", "version": "1.0.0"},
        "paths": {
            "/records/{record_id}": {
                "get": {
                    "operationId": "z17",
                    "summary": "Retrieve one existing record",
                    "responses": {"200": {"description": "record"}},
                },
                "patch": {
                    "operationId": "z28",
                    "summary": "Update an existing record",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/records": {
                "post": {
                    "operationId": "z39",
                    "summary": "Create a brand-new record",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("records_api", records))

    registry.register(
        tool_from_mcp(
            "inventory_ops",
            {
                "tools": [
                    {"name":"v11","description":"Search inventory items matching filters","inputSchema":{"type":"object","properties":{"query":{"type":"string"}}}},
                    {"name":"v22","description":"Retrieve one already-identified inventory item","inputSchema":{"type":"object","properties":{"item_id":{"type":"string"}}}},
                    {"name":"v33","description":"List all inventory items","inputSchema":{"type":"object","properties":{}}},
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="collaboration",
            description="Resource delivery and access sharing",
            endpoints=[
                EndpointSpec(name="send", description="Send a resource to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a resource with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="content_pipeline",
            description="Content transformation pipeline",
            endpoints=[
                EndpointSpec(name="export", description="Export content into an external file", read_only=True),
                EndpointSpec(name="compare", description="Compare content items for similarities and differences", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple content items into one", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="runtime_jobs",
            description="Runtime job control",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing runtime job", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered runtime job", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="warranties",
            description="Warranty lifecycle and reimbursement",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve an existing warranty", read_only=True),
                EndpointSpec(name="cancel", description="Cancel an active warranty", read_only=False),
                EndpointSpec(name="refund", description="Refund a paid warranty amount", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="load",
            description="System load observations and forecasting",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve current system load", read_only=True),
                EndpointSpec(name="history", description="Retrieve historical system load", read_only=True),
                EndpointSpec(name="forecast", description="Forecast future system load", read_only=True),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("incidents_api.i17","retrieve",{"en":"incident INC-8","ko":"인시던트 INC-8","es":"incidente INC-8","ja":"インシデントINC-8","de":"vorfall INC-8","mixed":"incident INC-8"}),
    RouteCaseSpec("incidents_api.i28","update",{"en":"incident INC-8","ko":"인시던트 INC-8","es":"incidente INC-8","ja":"インシデントINC-8","de":"vorfall INC-8","mixed":"incident INC-8"}),
    RouteCaseSpec("incidents_api.i39","delete",{"en":"incident INC-8","ko":"인시던트 INC-8","es":"incidente INC-8","ja":"インシデントINC-8","de":"vorfall INC-8","mixed":"incident INC-8"}),
    RouteCaseSpec("repository_ops.r11","search",{"en":"repository entries about polymer","ko":"polymer 관련 저장소 항목","es":"entradas del repositorio sobre polymer","ja":"polymerに関するリポジトリ項目","de":"repository-einträge zu polymer","mixed":"polymer 관련 repository entries"}),
    RouteCaseSpec("repository_ops.r22","retrieve",{"en":"repository entry R-4","ko":"저장소 항목 R-4","es":"entrada del repositorio R-4","ja":"リポジトリ項目R-4","de":"repository-eintrag R-4","mixed":"repository entry R-4"}),
    RouteCaseSpec("repository_ops.r33","list",{"en":"repository entries","ko":"저장소 항목","es":"entradas del repositorio","ja":"リポジトリ項目","de":"repository-einträge","mixed":"repository entries"}),
    RouteCaseSpec("handoff.send","send",{"en":"packet P-5","ko":"패킷 P-5","es":"paquete P-5","ja":"パケットP-5","de":"paket P-5","mixed":"packet P-5"}),
    RouteCaseSpec("handoff.share","share",{"en":"packet P-5","ko":"패킷 P-5","es":"paquete P-5","ja":"パケットP-5","de":"paket P-5","mixed":"packet P-5"}),
    RouteCaseSpec("artifact_ops.export","export",{"en":"artifact ART-3","ko":"아티팩트 ART-3","es":"artefacto ART-3","ja":"アーティファクトART-3","de":"artefakt ART-3","mixed":"artifact ART-3"}),
    RouteCaseSpec("artifact_ops.translate","translate",{"en":"artifact ART-3","ko":"아티팩트 ART-3","es":"artefacto ART-3","ja":"アーティファクトART-3","de":"artefakt ART-3","mixed":"artifact ART-3"}),
    RouteCaseSpec("artifact_ops.summarize","summarize",{"en":"artifact ART-3","ko":"아티팩트 ART-3","es":"artefacto ART-3","ja":"アーティファクトART-3","de":"artefakt ART-3","mixed":"artifact ART-3"}),
    RouteCaseSpec("processes.restart","restart",{"en":"process PROC-2","ko":"프로세스 PROC-2","es":"proceso PROC-2","ja":"プロセスPROC-2","de":"prozess PROC-2","mixed":"process PROC-2"}),
    RouteCaseSpec("processes.execute","execute",{"en":"process workflow PROC-2","ko":"프로세스 워크플로 PROC-2","es":"flujo de proceso PROC-2","ja":"プロセスワークフローPROC-2","de":"prozess-workflow PROC-2","mixed":"process workflow PROC-2"}),
    RouteCaseSpec("enrollments.create","create",{"en":"enrollment","ko":"등록","es":"inscripción","ja":"登録","de":"einschreibung","mixed":"enrollment"}),
    RouteCaseSpec("enrollments.cancel","cancel",{"en":"enrollment E-7","ko":"등록 E-7","es":"inscripción E-7","ja":"登録E-7","de":"einschreibung E-7","mixed":"enrollment E-7"}),
    RouteCaseSpec("enrollments.refund","refund",{"en":"enrollment charge E-7","ko":"등록 결제 E-7","es":"cargo de inscripción E-7","ja":"登録料金E-7","de":"einschreibungsgebühr E-7","mixed":"enrollment charge E-7"}),
    RouteCaseSpec("traffic.current","retrieve",{"en":"traffic level","ko":"교통량","es":"nivel de tráfico","ja":"交通量","de":"verkehrsaufkommen","mixed":"traffic level"},temporal_scope="current"),
    RouteCaseSpec("traffic.history","retrieve",{"en":"traffic levels","ko":"교통량","es":"niveles de tráfico","ja":"交通量","de":"verkehrsaufkommen","mixed":"traffic levels"},temporal_scope="historical"),
    RouteCaseSpec("traffic.forecast","forecast",{"en":"traffic levels","ko":"교통량","es":"niveles de tráfico","ja":"交通量","de":"verkehrsaufkommen","mixed":"traffic levels"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("records_api.z17","retrieve",{"en":"record Z-6","ko":"레코드 Z-6","es":"registro Z-6","ja":"レコードZ-6","de":"datensatz Z-6","mixed":"record Z-6"}),
    RouteCaseSpec("records_api.z28","update",{"en":"record Z-6","ko":"레코드 Z-6","es":"registro Z-6","ja":"レコードZ-6","de":"datensatz Z-6","mixed":"record Z-6"}),
    RouteCaseSpec("records_api.z39","create",{"en":"record","ko":"레코드","es":"registro","ja":"レコード","de":"datensatz","mixed":"record"}),
    RouteCaseSpec("inventory_ops.v11","search",{"en":"inventory items about ceramic","ko":"ceramic 관련 재고 항목","es":"artículos de inventario sobre ceramic","ja":"ceramicに関する在庫項目","de":"inventareinträge zu ceramic","mixed":"ceramic 관련 inventory items"}),
    RouteCaseSpec("inventory_ops.v22","retrieve",{"en":"inventory item V-9","ko":"재고 항목 V-9","es":"artículo de inventario V-9","ja":"在庫項目V-9","de":"inventareintrag V-9","mixed":"inventory item V-9"}),
    RouteCaseSpec("inventory_ops.v33","list",{"en":"inventory items","ko":"재고 항목","es":"artículos de inventario","ja":"在庫項目","de":"inventareinträge","mixed":"inventory items"}),
    RouteCaseSpec("collaboration.send","send",{"en":"resource RES-2","ko":"리소스 RES-2","es":"recurso RES-2","ja":"リソースRES-2","de":"ressource RES-2","mixed":"resource RES-2"}),
    RouteCaseSpec("collaboration.share","share",{"en":"resource RES-2","ko":"리소스 RES-2","es":"recurso RES-2","ja":"リソースRES-2","de":"ressource RES-2","mixed":"resource RES-2"}),
    RouteCaseSpec("content_pipeline.export","export",{"en":"content CNT-1","ko":"콘텐츠 CNT-1","es":"contenido CNT-1","ja":"コンテンツCNT-1","de":"inhalt CNT-1","mixed":"content CNT-1"}),
    RouteCaseSpec("content_pipeline.compare","compare",{"en":"content CNT-1 and CNT-2","ko":"콘텐츠 CNT-1과 CNT-2","es":"contenidos CNT-1 y CNT-2","ja":"コンテンツCNT-1とCNT-2","de":"inhalte CNT-1 und CNT-2","mixed":"content CNT-1 CNT-2"}),
    RouteCaseSpec("content_pipeline.merge","merge",{"en":"content CNT-1 and CNT-2","ko":"콘텐츠 CNT-1과 CNT-2","es":"contenidos CNT-1 y CNT-2","ja":"コンテンツCNT-1とCNT-2","de":"inhalte CNT-1 und CNT-2","mixed":"content CNT-1 CNT-2"}),
    RouteCaseSpec("runtime_jobs.restart","restart",{"en":"runtime job J-5","ko":"런타임 작업 J-5","es":"trabajo de runtime J-5","ja":"ランタイムジョブJ-5","de":"runtime-job J-5","mixed":"runtime job J-5"}),
    RouteCaseSpec("runtime_jobs.execute","execute",{"en":"runtime job J-5","ko":"런타임 작업 J-5","es":"trabajo de runtime J-5","ja":"ランタイムジョブJ-5","de":"runtime-job J-5","mixed":"runtime job J-5"}),
    RouteCaseSpec("warranties.retrieve","retrieve",{"en":"warranty W-4","ko":"보증 W-4","es":"garantía W-4","ja":"保証W-4","de":"garantie W-4","mixed":"warranty W-4"}),
    RouteCaseSpec("warranties.cancel","cancel",{"en":"warranty W-4","ko":"보증 W-4","es":"garantía W-4","ja":"保証W-4","de":"garantie W-4","mixed":"warranty W-4"}),
    RouteCaseSpec("warranties.refund","refund",{"en":"warranty payment W-4","ko":"보증 결제 W-4","es":"pago de garantía W-4","ja":"保証支払いW-4","de":"garantiezahlung W-4","mixed":"warranty payment W-4"}),
    RouteCaseSpec("load.current","retrieve",{"en":"system load","ko":"시스템 부하","es":"carga del sistema","ja":"システム負荷","de":"systemlast","mixed":"system load"},temporal_scope="current"),
    RouteCaseSpec("load.history","retrieve",{"en":"system load values","ko":"시스템 부하 값","es":"valores de carga del sistema","ja":"システム負荷値","de":"systemlastwerte","mixed":"system load values"},temporal_scope="historical"),
    RouteCaseSpec("load.forecast","forecast",{"en":"system load values","ko":"시스템 부하 값","es":"valores de carga del sistema","ja":"システム負荷値","de":"systemlastwerte","mixed":"system load values"},temporal_scope="future"),
)
