# ruff: noqa: E501
"""Disjoint 0.13-A catalogs for schema-derived ADB experiment #383."""

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
        "info": {
            "title": "License Service",
            "version": "1.0.0",
            "description": "License record management",
        },
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
    registry.register(tool_from_openapi("licenses_api", licenses_openapi))

    registry.register(
        tool_from_mcp(
            "registry_ops",
            {
                "tools": [
                    {
                        "name": "g17",
                        "description": "Search registry records that match supplied criteria",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "g28",
                        "description": "Retrieve one already-identified registry record",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                    {
                        "name": "g39",
                        "description": "List all currently available registry records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="transfer_hub",
            description="Transfer hub for packet delivery and shared access",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send an existing transfer packet to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an existing transfer packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="artifact_ops",
            description="Artifact transformation and packaging service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export an existing artifact as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate an existing artifact into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple existing artifacts into one resulting artifact",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="control_plane",
            description="Control plane for managed runtime operations",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing managed runtime service",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered managed runtime operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="entitlements",
            description="Entitlement lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a brand-new entitlement request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active entitlement request without deleting its record",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money paid for an entitlement transaction",
                    read_only=False,
                ),
            ],
        )
    )

    voltage_field = FieldSpec(
        name="voltage",
        semantic_id="electrical.voltage",
        description="Measured electrical voltage",
        json_schema={"type": "number"},
        unit="mV",
        unit_normalization=UnitNormalizationSpec(
            dimension="electric_potential",
            canonical_unit="V",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="voltage",
            description="Voltage observation and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current voltage observation",
                    read_only=True,
                    output_fields=[voltage_field],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical voltage observations",
                    read_only=True,
                    output_fields=[voltage_field],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future voltage values",
                    read_only=True,
                    output_fields=[voltage_field],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    certificates_openapi = {
        "openapi": "3.1.0",
        "info": {
            "title": "Certificate Service",
            "version": "1.0.0",
            "description": "Certificate record management",
        },
        "paths": {
            "/certificates/{certificate_id}": {
                "get": {
                    "operationId": "c17",
                    "summary": "Retrieve one already-identified certificate record",
                    "responses": {"200": {"description": "certificate"}},
                },
                "patch": {
                    "operationId": "c28",
                    "summary": "Update fields on an existing certificate record",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/certificates": {
                "post": {
                    "operationId": "c39",
                    "summary": "Create a brand-new certificate record",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("certificates_api", certificates_openapi))

    registry.register(
        tool_from_mcp(
            "reference_ops",
            {
                "tools": [
                    {
                        "name": "r17",
                        "description": "Search reference entries that match supplied criteria",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "r28",
                        "description": "Retrieve one already-identified reference entry",
                        "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}}},
                    },
                    {
                        "name": "r39",
                        "description": "List all currently available reference entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="access_handoff",
            description="Handoff service for message delivery and shared access",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send an existing handoff message to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an existing handoff message with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="media_transform",
            description="Media transformation and analysis service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export existing media content as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize existing media content into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple existing media items for similarities and differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="runtime_jobs",
            description="Control service for managed runtime jobs",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing managed runtime job",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered managed runtime job",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="passes",
            description="Pass record and payment lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified pass record",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active pass without deleting its record",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money paid for a pass transaction",
                    read_only=False,
                ),
            ],
        )
    )

    velocity_field = FieldSpec(
        name="velocity",
        semantic_id="motion.velocity",
        description="Measured linear velocity",
        json_schema={"type": "number"},
        unit="km/h",
        unit_normalization=UnitNormalizationSpec(
            dimension="velocity",
            canonical_unit="m/s",
            scale=1.0 / 3.6,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="velocity",
            description="Velocity observation and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current velocity observation",
                    read_only=True,
                    output_fields=[velocity_field],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical velocity observations",
                    read_only=True,
                    output_fields=[velocity_field],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future velocity values",
                    read_only=True,
                    output_fields=[velocity_field],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("licenses_api.l17", "retrieve", {"en":"license LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"license LIC-8"}),
    RouteCaseSpec("licenses_api.l28", "update", {"en":"license LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"license LIC-8"}),
    RouteCaseSpec("licenses_api.l39", "delete", {"en":"license LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"license LIC-8"}),
    RouteCaseSpec("registry_ops.g17", "search", {"en":"registry records about alloy","ko":"alloy 관련 레지스트리 기록","es":"registros del registro sobre alloy","ja":"alloyに関する登録記録","de":"registereinträge zu alloy","mixed":"alloy 관련 registry records"}),
    RouteCaseSpec("registry_ops.g28", "retrieve", {"en":"registry record G-4","ko":"레지스트리 기록 G-4","es":"registro G-4","ja":"登録記録G-4","de":"registereintrag G-4","mixed":"registry record G-4"}),
    RouteCaseSpec("registry_ops.g39", "list", {"en":"registry records","ko":"레지스트리 기록","es":"registros del registro","ja":"登録記録","de":"registereinträge","mixed":"registry records"}),
    RouteCaseSpec("transfer_hub.send", "send", {"en":"transfer packet TP-5","ko":"전송 패킷 TP-5","es":"paquete de transferencia TP-5","ja":"転送パケットTP-5","de":"transferpaket TP-5","mixed":"transfer packet TP-5"}),
    RouteCaseSpec("transfer_hub.share", "share", {"en":"transfer packet TP-5","ko":"전송 패킷 TP-5","es":"paquete de transferencia TP-5","ja":"転送パケットTP-5","de":"transferpaket TP-5","mixed":"transfer packet TP-5"}),
    RouteCaseSpec("artifact_ops.export", "export", {"en":"artifact ART-3","ko":"아티팩트 ART-3","es":"artefacto ART-3","ja":"アーティファクトART-3","de":"artefakt ART-3","mixed":"artifact ART-3"}),
    RouteCaseSpec("artifact_ops.translate", "translate", {"en":"artifact ART-3","ko":"아티팩트 ART-3","es":"artefacto ART-3","ja":"アーティファクトART-3","de":"artefakt ART-3","mixed":"artifact ART-3"}),
    RouteCaseSpec("artifact_ops.merge", "merge", {"en":"artifacts ART-3 and ART-4","ko":"아티팩트 ART-3과 ART-4","es":"artefactos ART-3 y ART-4","ja":"アーティファクトART-3とART-4","de":"artefakte ART-3 und ART-4","mixed":"artifacts ART-3 ART-4"}),
    RouteCaseSpec("control_plane.restart", "restart", {"en":"runtime service RS-2","ko":"런타임 서비스 RS-2","es":"servicio runtime RS-2","ja":"ランタイムサービスRS-2","de":"runtime-dienst RS-2","mixed":"runtime service RS-2"}),
    RouteCaseSpec("control_plane.execute", "execute", {"en":"runtime operation RS-2","ko":"런타임 작업 RS-2","es":"operación runtime RS-2","ja":"ランタイム操作RS-2","de":"runtime-operation RS-2","mixed":"runtime operation RS-2"}),
    RouteCaseSpec("entitlements.create", "create", {"en":"entitlement","ko":"권한 요청","es":"derecho","ja":"権利申請","de":"berechtigung","mixed":"entitlement"}),
    RouteCaseSpec("entitlements.cancel", "cancel", {"en":"entitlement ENT-7","ko":"권한 요청 ENT-7","es":"derecho ENT-7","ja":"権利申請ENT-7","de":"berechtigung ENT-7","mixed":"entitlement ENT-7"}),
    RouteCaseSpec("entitlements.refund", "refund", {"en":"entitlement payment ENT-7","ko":"권한 결제 ENT-7","es":"pago de derecho ENT-7","ja":"権利支払いENT-7","de":"berechtigungszahlung ENT-7","mixed":"entitlement payment ENT-7"}),
    RouteCaseSpec("voltage.current", "retrieve", {"en":"voltage value","ko":"전압 값","es":"valor de voltaje","ja":"電圧値","de":"spannungswert","mixed":"voltage 값"}, temporal_scope="current"),
    RouteCaseSpec("voltage.history", "retrieve", {"en":"voltage values","ko":"전압 값","es":"valores de voltaje","ja":"電圧値","de":"spannungswerte","mixed":"voltage 값"}, temporal_scope="historical"),
    RouteCaseSpec("voltage.forecast", "forecast", {"en":"voltage values","ko":"전압 값","es":"valores de voltaje","ja":"電圧値","de":"spannungswerte","mixed":"voltage 값"}, temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("certificates_api.c17", "retrieve", {"en":"certificate CERT-6","ko":"인증서 CERT-6","es":"certificado CERT-6","ja":"証明書CERT-6","de":"zertifikat CERT-6","mixed":"certificate CERT-6"}),
    RouteCaseSpec("certificates_api.c28", "update", {"en":"certificate CERT-6","ko":"인증서 CERT-6","es":"certificado CERT-6","ja":"証明書CERT-6","de":"zertifikat CERT-6","mixed":"certificate CERT-6"}),
    RouteCaseSpec("certificates_api.c39", "create", {"en":"certificate","ko":"인증서","es":"certificado","ja":"証明書","de":"zertifikat","mixed":"certificate"}),
    RouteCaseSpec("reference_ops.r17", "search", {"en":"reference entries about catalyst","ko":"catalyst 관련 참조 항목","es":"entradas de referencia sobre catalyst","ja":"catalystに関する参照項目","de":"referenzeinträge zu catalyst","mixed":"catalyst 관련 reference entries"}),
    RouteCaseSpec("reference_ops.r28", "retrieve", {"en":"reference entry R-9","ko":"참조 항목 R-9","es":"entrada de referencia R-9","ja":"参照項目R-9","de":"referenzeintrag R-9","mixed":"reference entry R-9"}),
    RouteCaseSpec("reference_ops.r39", "list", {"en":"reference entries","ko":"참조 항목","es":"entradas de referencia","ja":"参照項目","de":"referenzeinträge","mixed":"reference entries"}),
    RouteCaseSpec("access_handoff.send", "send", {"en":"handoff message HM-2","ko":"인계 메시지 HM-2","es":"mensaje de traspaso HM-2","ja":"引き継ぎメッセージHM-2","de":"übergabenachricht HM-2","mixed":"handoff message HM-2"}),
    RouteCaseSpec("access_handoff.share", "share", {"en":"handoff message HM-2","ko":"인계 메시지 HM-2","es":"mensaje de traspaso HM-2","ja":"引き継ぎメッセージHM-2","de":"übergabenachricht HM-2","mixed":"handoff message HM-2"}),
    RouteCaseSpec("media_transform.export", "export", {"en":"media item M-1","ko":"미디어 항목 M-1","es":"elemento multimedia M-1","ja":"メディア項目M-1","de":"medienelement M-1","mixed":"media item M-1"}),
    RouteCaseSpec("media_transform.summarize", "summarize", {"en":"media item M-1","ko":"미디어 항목 M-1","es":"elemento multimedia M-1","ja":"メディア項目M-1","de":"medienelement M-1","mixed":"media item M-1"}),
    RouteCaseSpec("media_transform.compare", "compare", {"en":"media items M-1 and M-2","ko":"미디어 항목 M-1과 M-2","es":"elementos multimedia M-1 y M-2","ja":"メディア項目M-1とM-2","de":"medienelemente M-1 und M-2","mixed":"media items M-1 M-2"}),
    RouteCaseSpec("runtime_jobs.restart", "restart", {"en":"runtime job J-5","ko":"런타임 작업 J-5","es":"trabajo runtime J-5","ja":"ランタイムジョブJ-5","de":"runtime-job J-5","mixed":"runtime job J-5"}),
    RouteCaseSpec("runtime_jobs.execute", "execute", {"en":"runtime job J-5","ko":"런타임 작업 J-5","es":"trabajo runtime J-5","ja":"ランタイムジョブJ-5","de":"runtime-job J-5","mixed":"runtime job J-5"}),
    RouteCaseSpec("passes.retrieve", "retrieve", {"en":"pass PASS-4","ko":"패스 PASS-4","es":"pase PASS-4","ja":"パスPASS-4","de":"pass PASS-4","mixed":"pass PASS-4"}),
    RouteCaseSpec("passes.cancel", "cancel", {"en":"pass PASS-4","ko":"패스 PASS-4","es":"pase PASS-4","ja":"パスPASS-4","de":"pass PASS-4","mixed":"pass PASS-4"}),
    RouteCaseSpec("passes.refund", "refund", {"en":"pass payment PASS-4","ko":"패스 결제 PASS-4","es":"pago de pase PASS-4","ja":"パス支払いPASS-4","de":"passzahlung PASS-4","mixed":"pass payment PASS-4"}),
    RouteCaseSpec("velocity.current", "retrieve", {"en":"velocity value","ko":"속도 값","es":"valor de velocidad","ja":"速度値","de":"geschwindigkeitswert","mixed":"velocity 값"}, temporal_scope="current"),
    RouteCaseSpec("velocity.history", "retrieve", {"en":"velocity values","ko":"속도 값","es":"valores de velocidad","ja":"速度値","de":"geschwindigkeitswerte","mixed":"velocity 값"}, temporal_scope="historical"),
    RouteCaseSpec("velocity.forecast", "forecast", {"en":"velocity values","ko":"속도 값","es":"valores de velocidad","ja":"速度値","de":"geschwindigkeitswerte","mixed":"velocity 값"}, temporal_scope="future"),
)
