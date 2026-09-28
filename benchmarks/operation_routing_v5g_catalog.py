# ruff: noqa: E501
"""Disjoint 0.12-G catalogs for set-conditioned entailment experiment #374."""

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

    licenses_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "License Records", "version": "1.0.0"},
        "paths": {
            "/licenses/{license_id}": {
                "get": {
                    "operationId": "l17",
                    "summary": "Retrieve one already-identified license record",
                    "responses": {"200": {"description": "license"}},
                },
                "patch": {
                    "operationId": "l28",
                    "summary": "Update fields on an existing license record",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "l39",
                    "summary": "Delete an existing license record permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("license_records_api", licenses_openapi))

    registry.register(
        tool_from_mcp(
            "knowledge_corpus_ops",
            {
                "tools": [
                    {
                        "name": "c17",
                        "description": "Search corpus entries that match criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "c28",
                        "description": "Retrieve one already-identified corpus entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"entry_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "c39",
                        "description": "List all available corpus entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="packet_courier",
            description="Packet delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a packet to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="artifact_transform",
            description="Artifact transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export an artifact as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate an artifact into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple artifacts into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="daemon_control",
            description="Daemon runtime control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing daemon",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered daemon operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="service_credits",
            description="Service-credit lifecycle and reimbursement",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new service-credit request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active service-credit request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid service-credit transaction",
                    read_only=False,
                ),
            ],
        )
    )

    humidity = FieldSpec(
        name="relative_humidity",
        semantic_id="environment.relative_humidity",
        description="Measured relative humidity",
        json_schema={"type": "number"},
        unit="percent",
        unit_normalization=UnitNormalizationSpec(
            dimension="relative_humidity",
            canonical_unit="1",
            scale=0.01,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="humidity_probe",
            description="Humidity observations and forecast",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current relative humidity value",
                    read_only=True,
                    output_fields=[humidity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical relative humidity values",
                    read_only=True,
                    output_fields=[humidity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future relative humidity values",
                    read_only=True,
                    output_fields=[humidity],
                ),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registrations_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Registration Records", "version": "1.0.0"},
        "paths": {
            "/registrations/{registration_id}": {
                "get": {
                    "operationId": "r17",
                    "summary": "Retrieve one already-identified registration record",
                    "responses": {"200": {"description": "registration"}},
                },
                "patch": {
                    "operationId": "r28",
                    "summary": "Update an existing registration record",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/registrations": {
                "post": {
                    "operationId": "r39",
                    "summary": "Create a brand-new registration record",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(
        tool_from_openapi("registration_records_api", registrations_openapi)
    )

    registry.register(
        tool_from_mcp(
            "archive_catalog_ops",
            {
                "tools": [
                    {
                        "name": "a17",
                        "description": "Search archive catalog entries that match criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "a28",
                        "description": "Retrieve one already-identified archive catalog entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"entry_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "a39",
                        "description": "List all available archive catalog entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="message_relay",
            description="Message delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a message to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a message with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="media_transform",
            description="Media transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export media as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize media content into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple media items for differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="scheduler_control",
            description="Scheduler runtime control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing scheduler runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered scheduler workflow",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="deposit_claims",
            description="Deposit claim and reimbursement service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified deposit claim",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active deposit claim",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid deposit claim amount",
                    read_only=False,
                ),
            ],
        )
    )

    velocity = FieldSpec(
        name="velocity",
        semantic_id="motion.velocity",
        description="Measured velocity",
        json_schema={"type": "number"},
        unit="km/h",
        unit_normalization=UnitNormalizationSpec(
            dimension="speed",
            canonical_unit="m/s",
            scale=0.2777777777777778,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="velocity_probe",
            description="Velocity observations and forecast",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current velocity value",
                    read_only=True,
                    output_fields=[velocity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical velocity values",
                    read_only=True,
                    output_fields=[velocity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future velocity values",
                    read_only=True,
                    output_fields=[velocity],
                ),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("license_records_api.l17","retrieve",{"en":"license L-8","ko":"라이선스 L-8","es":"licencia L-8","ja":"ライセンスL-8","de":"lizenz L-8","mixed":"license L-8"}),
    RouteCaseSpec("license_records_api.l28","update",{"en":"license L-8","ko":"라이선스 L-8","es":"licencia L-8","ja":"ライセンスL-8","de":"lizenz L-8","mixed":"license L-8"}),
    RouteCaseSpec("license_records_api.l39","delete",{"en":"license L-8","ko":"라이선스 L-8","es":"licencia L-8","ja":"ライセンスL-8","de":"lizenz L-8","mixed":"license L-8"}),
    RouteCaseSpec("knowledge_corpus_ops.c17","search",{"en":"corpus entries about composite","ko":"composite 관련 코퍼스 항목","es":"entradas del corpus sobre composite","ja":"compositeに関するコーパス項目","de":"korpuseinträge zu composite","mixed":"composite 관련 corpus entries"}),
    RouteCaseSpec("knowledge_corpus_ops.c28","retrieve",{"en":"corpus entry C-4","ko":"코퍼스 항목 C-4","es":"entrada del corpus C-4","ja":"コーパス項目C-4","de":"korpuseintrag C-4","mixed":"corpus entry C-4"}),
    RouteCaseSpec("knowledge_corpus_ops.c39","list",{"en":"corpus entries","ko":"코퍼스 항목","es":"entradas del corpus","ja":"コーパス項目","de":"korpuseinträge","mixed":"corpus entries"}),
    RouteCaseSpec("packet_courier.send","send",{"en":"packet PX-5","ko":"패킷 PX-5","es":"paquete PX-5","ja":"パケットPX-5","de":"paket PX-5","mixed":"packet PX-5"}),
    RouteCaseSpec("packet_courier.share","share",{"en":"packet PX-5","ko":"패킷 PX-5","es":"paquete PX-5","ja":"パケットPX-5","de":"paket PX-5","mixed":"packet PX-5"}),
    RouteCaseSpec("artifact_transform.export","export",{"en":"artifact AF-3","ko":"아티팩트 AF-3","es":"artefacto AF-3","ja":"アーティファクトAF-3","de":"artefakt AF-3","mixed":"artifact AF-3"}),
    RouteCaseSpec("artifact_transform.translate","translate",{"en":"artifact AF-3","ko":"아티팩트 AF-3","es":"artefacto AF-3","ja":"アーティファクトAF-3","de":"artefakt AF-3","mixed":"artifact AF-3"}),
    RouteCaseSpec("artifact_transform.merge","merge",{"en":"artifacts AF-3 and AF-4","ko":"아티팩트 AF-3과 AF-4","es":"artefactos AF-3 y AF-4","ja":"アーティファクトAF-3とAF-4","de":"artefakte AF-3 und AF-4","mixed":"artifacts AF-3 AF-4"}),
    RouteCaseSpec("daemon_control.restart","restart",{"en":"daemon D-2","ko":"데몬 D-2","es":"daemon D-2","ja":"デーモンD-2","de":"daemon D-2","mixed":"daemon D-2"}),
    RouteCaseSpec("daemon_control.execute","execute",{"en":"daemon operation D-2","ko":"데몬 작업 D-2","es":"operación daemon D-2","ja":"デーモン操作D-2","de":"daemon-operation D-2","mixed":"daemon operation D-2"}),
    RouteCaseSpec("service_credits.create","create",{"en":"service-credit request","ko":"서비스 크레딧 요청","es":"solicitud de crédito de servicio","ja":"サービスクレジット申請","de":"servicegutschrift-antrag","mixed":"service credit request"}),
    RouteCaseSpec("service_credits.cancel","cancel",{"en":"service-credit request SC-7","ko":"서비스 크레딧 요청 SC-7","es":"solicitud de crédito SC-7","ja":"サービスクレジット申請SC-7","de":"servicegutschrift SC-7","mixed":"service credit SC-7"}),
    RouteCaseSpec("service_credits.refund","refund",{"en":"service-credit payment SC-7","ko":"서비스 크레딧 결제 SC-7","es":"pago de crédito SC-7","ja":"サービスクレジット支払いSC-7","de":"servicegutschrift-zahlung SC-7","mixed":"service credit payment SC-7"}),
    RouteCaseSpec("humidity_probe.current","retrieve",{"en":"relative humidity","ko":"상대습도","es":"humedad relativa","ja":"相対湿度","de":"relative luftfeuchte","mixed":"relative humidity"},temporal_scope="current"),
    RouteCaseSpec("humidity_probe.history","retrieve",{"en":"relative humidity values","ko":"상대습도 값","es":"valores de humedad relativa","ja":"相対湿度値","de":"werte der relativen luftfeuchte","mixed":"relative humidity values"},temporal_scope="historical"),
    RouteCaseSpec("humidity_probe.forecast","forecast",{"en":"relative humidity values","ko":"상대습도 값","es":"valores de humedad relativa","ja":"相対湿度値","de":"werte der relativen luftfeuchte","mixed":"relative humidity values"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("registration_records_api.r17","retrieve",{"en":"registration R-6","ko":"등록 R-6","es":"registro R-6","ja":"登録R-6","de":"registrierung R-6","mixed":"registration R-6"}),
    RouteCaseSpec("registration_records_api.r28","update",{"en":"registration R-6","ko":"등록 R-6","es":"registro R-6","ja":"登録R-6","de":"registrierung R-6","mixed":"registration R-6"}),
    RouteCaseSpec("registration_records_api.r39","create",{"en":"registration","ko":"등록","es":"registro","ja":"登録","de":"registrierung","mixed":"registration"}),
    RouteCaseSpec("archive_catalog_ops.a17","search",{"en":"archive entries about coating","ko":"coating 관련 아카이브 항목","es":"entradas de archivo sobre coating","ja":"coatingに関するアーカイブ項目","de":"archiveinträge zu coating","mixed":"coating 관련 archive entries"}),
    RouteCaseSpec("archive_catalog_ops.a28","retrieve",{"en":"archive entry A-9","ko":"아카이브 항목 A-9","es":"entrada de archivo A-9","ja":"アーカイブ項目A-9","de":"archiveintrag A-9","mixed":"archive entry A-9"}),
    RouteCaseSpec("archive_catalog_ops.a39","list",{"en":"archive entries","ko":"아카이브 항목","es":"entradas de archivo","ja":"アーカイブ項目","de":"archiveinträge","mixed":"archive entries"}),
    RouteCaseSpec("message_relay.send","send",{"en":"message MR-2","ko":"메시지 MR-2","es":"mensaje MR-2","ja":"メッセージMR-2","de":"nachricht MR-2","mixed":"message MR-2"}),
    RouteCaseSpec("message_relay.share","share",{"en":"message MR-2","ko":"메시지 MR-2","es":"mensaje MR-2","ja":"メッセージMR-2","de":"nachricht MR-2","mixed":"message MR-2"}),
    RouteCaseSpec("media_transform.export","export",{"en":"media M-1","ko":"미디어 M-1","es":"medio M-1","ja":"メディアM-1","de":"medium M-1","mixed":"media M-1"}),
    RouteCaseSpec("media_transform.summarize","summarize",{"en":"media M-1","ko":"미디어 M-1","es":"medio M-1","ja":"メディアM-1","de":"medium M-1","mixed":"media M-1"}),
    RouteCaseSpec("media_transform.compare","compare",{"en":"media M-1 and M-2","ko":"미디어 M-1과 M-2","es":"medios M-1 y M-2","ja":"メディアM-1とM-2","de":"medien M-1 und M-2","mixed":"media M-1 M-2"}),
    RouteCaseSpec("scheduler_control.restart","restart",{"en":"scheduler S-5","ko":"스케줄러 S-5","es":"planificador S-5","ja":"スケジューラS-5","de":"scheduler S-5","mixed":"scheduler S-5"}),
    RouteCaseSpec("scheduler_control.execute","execute",{"en":"scheduler workflow S-5","ko":"스케줄러 워크플로 S-5","es":"flujo del planificador S-5","ja":"スケジューラワークフローS-5","de":"scheduler-workflow S-5","mixed":"scheduler workflow S-5"}),
    RouteCaseSpec("deposit_claims.retrieve","retrieve",{"en":"deposit claim DP-4","ko":"보증금 청구 DP-4","es":"reclamo de depósito DP-4","ja":"デポジット請求DP-4","de":"einlagenanspruch DP-4","mixed":"deposit claim DP-4"}),
    RouteCaseSpec("deposit_claims.cancel","cancel",{"en":"deposit claim DP-4","ko":"보증금 청구 DP-4","es":"reclamo de depósito DP-4","ja":"デポジット請求DP-4","de":"einlagenanspruch DP-4","mixed":"deposit claim DP-4"}),
    RouteCaseSpec("deposit_claims.refund","refund",{"en":"deposit payment DP-4","ko":"보증금 결제 DP-4","es":"pago de depósito DP-4","ja":"デポジット支払いDP-4","de":"einlagenzahlung DP-4","mixed":"deposit payment DP-4"}),
    RouteCaseSpec("velocity_probe.current","retrieve",{"en":"velocity","ko":"속도","es":"velocidad","ja":"速度","de":"geschwindigkeit","mixed":"velocity"},temporal_scope="current"),
    RouteCaseSpec("velocity_probe.history","retrieve",{"en":"velocity values","ko":"속도 값","es":"valores de velocidad","ja":"速度値","de":"geschwindigkeitswerte","mixed":"velocity values"},temporal_scope="historical"),
    RouteCaseSpec("velocity_probe.forecast","forecast",{"en":"velocity values","ko":"속도 값","es":"valores de velocidad","ja":"速度値","de":"geschwindigkeitswerte","mixed":"velocity values"},temporal_scope="future"),
)
