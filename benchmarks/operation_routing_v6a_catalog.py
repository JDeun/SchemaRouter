# ruff: noqa: E501
"""Disjoint V6A catalogs for schema-derived ADB experiment #384."""

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
            "licenses_api",
            {
                "openapi": "3.1.0",
                "info": {"title": "License Service", "version": "1.0.0", "description": "License record management service"},
                "paths": {
                    "/licenses/{license_id}": {
                        "get": {
                            "operationId": "l17",
                            "summary": "Retrieve one already-identified license",
                            "responses": {"200": {"description": "license"}},
                        },
                        "patch": {
                            "operationId": "l28",
                            "summary": "Update fields on an existing license",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "l39",
                            "summary": "Delete an existing license permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "registry_ops",
            {
                "tools": [
                    {
                        "name": "g17",
                        "description": "Search registry entries matching filters or keywords",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "g28",
                        "description": "Retrieve one already-identified registry entry",
                        "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}}},
                    },
                    {
                        "name": "g39",
                        "description": "List all available registry entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="courier",
            description="Parcel delivery and shared-access service",
            endpoints=[
                EndpointSpec(name="send", description="Send a parcel packet to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a parcel packet with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="rendering",
            description="Rendering artifact transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export a rendering artifact to an external file", read_only=True),
                EndpointSpec(name="summarize", description="Summarize a rendering artifact into its main points", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple rendering artifacts into one result", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="daemons",
            description="Background daemon control service",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing background daemon", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered daemon operation", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="reimbursements",
            description="Reimbursement lifecycle and payment service",
            endpoints=[
                EndpointSpec(name="create", description="Create a new reimbursement request", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active reimbursement request", read_only=False),
                EndpointSpec(name="refund", description="Refund money for a completed reimbursement transaction", read_only=False),
            ],
        )
    )

    humidity = FieldSpec(
        name="relative_humidity",
        semantic_id="environment.relative_humidity",
        description="Relative humidity measurement",
        json_schema={"type": "number"},
        unit="%RH",
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
            name="humidity",
            description="Humidity observations and forecast service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current humidity value", read_only=True, output_fields=[humidity]),
                EndpointSpec(name="history", description="Retrieve historical humidity values", read_only=True, output_fields=[humidity]),
                EndpointSpec(name="forecast", description="Forecast future humidity values", read_only=True, output_fields=[humidity]),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "certificates_api",
            {
                "openapi": "3.1.0",
                "info": {"title": "Certificate Service", "version": "1.0.0", "description": "Certificate record management service"},
                "paths": {
                    "/certificates/{certificate_id}": {
                        "get": {
                            "operationId": "c17",
                            "summary": "Retrieve one already-identified certificate",
                            "responses": {"200": {"description": "certificate"}},
                        },
                        "patch": {
                            "operationId": "c28",
                            "summary": "Update an existing certificate",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/certificates": {
                        "post": {
                            "operationId": "c39",
                            "summary": "Create a brand-new certificate",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "catalogue_ops",
            {
                "tools": [
                    {
                        "name": "q17",
                        "description": "Search catalogue records matching criteria",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "q28",
                        "description": "Retrieve one already-identified catalogue record",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                    {
                        "name": "q39",
                        "description": "List all available catalogue records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="messenger",
            description="Message delivery and shared-access service",
            endpoints=[
                EndpointSpec(name="send", description="Send a message payload to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a message payload with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="conversion",
            description="Content conversion and analysis service",
            endpoints=[
                EndpointSpec(name="export", description="Export converted content as an external file", read_only=True),
                EndpointSpec(name="translate", description="Translate content into another human language", read_only=True),
                EndpointSpec(name="compare", description="Compare multiple content items for similarities or differences", read_only=True),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="clusters",
            description="Compute cluster control service",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing compute cluster", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered cluster workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="settlements",
            description="Settlement lookup and lifecycle service",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve one already-identified settlement", read_only=True),
                EndpointSpec(name="cancel", description="Cancel an active settlement request", read_only=False),
                EndpointSpec(name="refund", description="Refund money for a completed settlement transaction", read_only=False),
            ],
        )
    )

    conductivity = FieldSpec(
        name="conductivity",
        semantic_id="material.electrical_conductivity",
        description="Electrical conductivity measurement",
        json_schema={"type": "number"},
        unit="mS/cm",
        unit_normalization=UnitNormalizationSpec(
            dimension="electrical_conductivity",
            canonical_unit="S/m",
            scale=0.1,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="conductivity",
            description="Conductivity observations and forecast service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current conductivity value", read_only=True, output_fields=[conductivity]),
                EndpointSpec(name="history", description="Retrieve historical conductivity values", read_only=True, output_fields=[conductivity]),
                EndpointSpec(name="forecast", description="Forecast future conductivity values", read_only=True, output_fields=[conductivity]),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("licenses_api.l17","retrieve",{"en":"license LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"license LIC-8"}),
    RouteCaseSpec("licenses_api.l28","update",{"en":"license LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"license LIC-8"}),
    RouteCaseSpec("licenses_api.l39","delete",{"en":"license LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"license LIC-8"}),
    RouteCaseSpec("registry_ops.g17","search",{"en":"registry entries about graphene","ko":"graphene 관련 레지스트리 항목","es":"entradas de registro sobre graphene","ja":"grapheneに関する登録項目","de":"registereinträge zu graphene","mixed":"graphene 관련 registry entries"}),
    RouteCaseSpec("registry_ops.g28","retrieve",{"en":"registry entry G-4","ko":"레지스트리 항목 G-4","es":"entrada de registro G-4","ja":"登録項目G-4","de":"registereintrag G-4","mixed":"registry entry G-4"}),
    RouteCaseSpec("registry_ops.g39","list",{"en":"registry entries","ko":"레지스트리 항목","es":"entradas de registro","ja":"登録項目","de":"registereinträge","mixed":"registry entries"}),
    RouteCaseSpec("courier.send","send",{"en":"parcel packet PK-5","ko":"소포 패킷 PK-5","es":"paquete PK-5","ja":"小包パケットPK-5","de":"paket PK-5","mixed":"parcel packet PK-5"}),
    RouteCaseSpec("courier.share","share",{"en":"parcel packet PK-5","ko":"소포 패킷 PK-5","es":"paquete PK-5","ja":"小包パケットPK-5","de":"paket PK-5","mixed":"parcel packet PK-5"}),
    RouteCaseSpec("rendering.export","export",{"en":"rendering artifact R-3","ko":"렌더링 아티팩트 R-3","es":"artefacto de renderizado R-3","ja":"レンダリング成果物R-3","de":"rendering-artefakt R-3","mixed":"rendering artifact R-3"}),
    RouteCaseSpec("rendering.summarize","summarize",{"en":"rendering artifact R-3","ko":"렌더링 아티팩트 R-3","es":"artefacto de renderizado R-3","ja":"レンダリング成果物R-3","de":"rendering-artefakt R-3","mixed":"rendering artifact R-3"}),
    RouteCaseSpec("rendering.merge","merge",{"en":"rendering artifacts R-3 and R-4","ko":"렌더링 아티팩트 R-3과 R-4","es":"artefactos R-3 y R-4","ja":"レンダリング成果物R-3とR-4","de":"rendering-artefakte R-3 und R-4","mixed":"rendering artifacts R-3 R-4"}),
    RouteCaseSpec("daemons.restart","restart",{"en":"daemon D-2","ko":"데몬 D-2","es":"daemon D-2","ja":"デーモンD-2","de":"daemon D-2","mixed":"daemon D-2"}),
    RouteCaseSpec("daemons.execute","execute",{"en":"daemon operation D-2","ko":"데몬 작업 D-2","es":"operación de daemon D-2","ja":"デーモン操作D-2","de":"daemon-operation D-2","mixed":"daemon operation D-2"}),
    RouteCaseSpec("reimbursements.create","create",{"en":"reimbursement","ko":"상환 요청","es":"reembolso","ja":"償還申請","de":"erstattungsantrag","mixed":"reimbursement"}),
    RouteCaseSpec("reimbursements.cancel","cancel",{"en":"reimbursement RB-7","ko":"상환 요청 RB-7","es":"reembolso RB-7","ja":"償還申請RB-7","de":"erstattungsantrag RB-7","mixed":"reimbursement RB-7"}),
    RouteCaseSpec("reimbursements.refund","refund",{"en":"reimbursement payment RB-7","ko":"상환 결제 RB-7","es":"pago de reembolso RB-7","ja":"償還支払いRB-7","de":"erstattungszahlung RB-7","mixed":"reimbursement payment RB-7"}),
    RouteCaseSpec("humidity.current","retrieve",{"en":"humidity value","ko":"습도 값","es":"valor de humedad","ja":"湿度値","de":"luftfeuchtigkeitswert","mixed":"humidity 값"},temporal_scope="current"),
    RouteCaseSpec("humidity.history","retrieve",{"en":"humidity values","ko":"습도 값","es":"valores de humedad","ja":"湿度値","de":"luftfeuchtigkeitswerte","mixed":"humidity 값"},temporal_scope="historical"),
    RouteCaseSpec("humidity.forecast","forecast",{"en":"humidity values","ko":"습도 값","es":"valores de humedad","ja":"湿度値","de":"luftfeuchtigkeitswerte","mixed":"humidity 값"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("certificates_api.c17","retrieve",{"en":"certificate CERT-6","ko":"인증서 CERT-6","es":"certificado CERT-6","ja":"証明書CERT-6","de":"zertifikat CERT-6","mixed":"certificate CERT-6"}),
    RouteCaseSpec("certificates_api.c28","update",{"en":"certificate CERT-6","ko":"인증서 CERT-6","es":"certificado CERT-6","ja":"証明書CERT-6","de":"zertifikat CERT-6","mixed":"certificate CERT-6"}),
    RouteCaseSpec("certificates_api.c39","create",{"en":"certificate","ko":"인증서","es":"certificado","ja":"証明書","de":"zertifikat","mixed":"certificate"}),
    RouteCaseSpec("catalogue_ops.q17","search",{"en":"catalogue records about ceramic","ko":"ceramic 관련 카탈로그 레코드","es":"registros de catálogo sobre ceramic","ja":"ceramicに関するカタログ記録","de":"katalogdatensätze zu ceramic","mixed":"ceramic 관련 catalogue records"}),
    RouteCaseSpec("catalogue_ops.q28","retrieve",{"en":"catalogue record Q-9","ko":"카탈로그 레코드 Q-9","es":"registro de catálogo Q-9","ja":"カタログ記録Q-9","de":"katalogdatensatz Q-9","mixed":"catalogue record Q-9"}),
    RouteCaseSpec("catalogue_ops.q39","list",{"en":"catalogue records","ko":"카탈로그 레코드","es":"registros de catálogo","ja":"カタログ記録","de":"katalogdatensätze","mixed":"catalogue records"}),
    RouteCaseSpec("messenger.send","send",{"en":"message payload M-2","ko":"메시지 페이로드 M-2","es":"carga de mensaje M-2","ja":"メッセージペイロードM-2","de":"nachrichtenpayload M-2","mixed":"message payload M-2"}),
    RouteCaseSpec("messenger.share","share",{"en":"message payload M-2","ko":"메시지 페이로드 M-2","es":"carga de mensaje M-2","ja":"メッセージペイロードM-2","de":"nachrichtenpayload M-2","mixed":"message payload M-2"}),
    RouteCaseSpec("conversion.export","export",{"en":"converted content C-1","ko":"변환 콘텐츠 C-1","es":"contenido convertido C-1","ja":"変換コンテンツC-1","de":"konvertierter inhalt C-1","mixed":"converted content C-1"}),
    RouteCaseSpec("conversion.translate","translate",{"en":"converted content C-1","ko":"변환 콘텐츠 C-1","es":"contenido convertido C-1","ja":"変換コンテンツC-1","de":"konvertierter inhalt C-1","mixed":"converted content C-1"}),
    RouteCaseSpec("conversion.compare","compare",{"en":"converted content C-1 and C-2","ko":"변환 콘텐츠 C-1과 C-2","es":"contenidos C-1 y C-2","ja":"変換コンテンツC-1とC-2","de":"konvertierte inhalte C-1 und C-2","mixed":"converted content C-1 C-2"}),
    RouteCaseSpec("clusters.restart","restart",{"en":"cluster CL-5","ko":"클러스터 CL-5","es":"clúster CL-5","ja":"クラスタCL-5","de":"cluster CL-5","mixed":"cluster CL-5"}),
    RouteCaseSpec("clusters.execute","execute",{"en":"cluster workflow CL-5","ko":"클러스터 워크플로 CL-5","es":"flujo de clúster CL-5","ja":"クラスタワークフローCL-5","de":"cluster-workflow CL-5","mixed":"cluster workflow CL-5"}),
    RouteCaseSpec("settlements.retrieve","retrieve",{"en":"settlement ST-4","ko":"정산 ST-4","es":"liquidación ST-4","ja":"決済ST-4","de":"abrechnung ST-4","mixed":"settlement ST-4"}),
    RouteCaseSpec("settlements.cancel","cancel",{"en":"settlement ST-4","ko":"정산 ST-4","es":"liquidación ST-4","ja":"決済ST-4","de":"abrechnung ST-4","mixed":"settlement ST-4"}),
    RouteCaseSpec("settlements.refund","refund",{"en":"settlement payment ST-4","ko":"정산 결제 ST-4","es":"pago de liquidación ST-4","ja":"決済支払いST-4","de":"abrechnungszahlung ST-4","mixed":"settlement payment ST-4"}),
    RouteCaseSpec("conductivity.current","retrieve",{"en":"conductivity value","ko":"전도도 값","es":"valor de conductividad","ja":"導電率値","de":"leitfähigkeitswert","mixed":"conductivity 값"},temporal_scope="current"),
    RouteCaseSpec("conductivity.history","retrieve",{"en":"conductivity values","ko":"전도도 값","es":"valores de conductividad","ja":"導電率値","de":"leitfähigkeitswerte","mixed":"conductivity 값"},temporal_scope="historical"),
    RouteCaseSpec("conductivity.forecast","forecast",{"en":"conductivity values","ko":"전도도 값","es":"valores de conductividad","ja":"導電率値","de":"leitfähigkeitswerte","mixed":"conductivity 값"},temporal_scope="future"),
)
