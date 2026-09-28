# ruff: noqa: E501
"""Disjoint V6B catalogs for schema-derived hard-negative experiment #393."""

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
            "authorizations_api",
            {
                "openapi": "3.1.0",
                "info": {"title": "Authorization Service", "version": "1.0.0", "description": "Authorization record management service"},
                "paths": {
                    "/authorizations/{authorization_id}": {
                        "get": {
                            "operationId": "au17",
                            "summary": "Retrieve one already-identified authorization",
                            "responses": {"200": {"description": "authorization"}},
                        },
                        "patch": {
                            "operationId": "au28",
                            "summary": "Update fields on an existing authorization",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "au39",
                            "summary": "Delete an existing authorization permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "ledger_ops",
            {
                "tools": [
                    {
                        "name": "ld17",
                        "description": "Search ledger entries matching filters or keywords",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "ld28",
                        "description": "Retrieve one already-identified ledger entry",
                        "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}}},
                    },
                    {
                        "name": "ld39",
                        "description": "List all available ledger entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="packet_delivery",
            description="Delivery bundle transfer and shared-access service",
            endpoints=[
                EndpointSpec(name="send", description="Send a delivery bundle to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a delivery bundle with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="publication_ops",
            description="Publication asset transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export a publication_ops artifact to an external file", read_only=True),
                EndpointSpec(name="summarize", description="Summarize a publication_ops artifact into its main points", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple publication_ops artifacts into one result", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="controllers",
            description="Controller runtime control service",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing background controller", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered controller operation", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="service_orders",
            description="Service order lifecycle and payment service",
            endpoints=[
                EndpointSpec(name="create", description="Create a new service order request", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active service order request", read_only=False),
                EndpointSpec(name="refund", description="Refund money for a completed service order transaction", read_only=False),
            ],
        )
    )

    density = FieldSpec(
        name="relative_density",
        semantic_id="environment.relative_density",
        description="Relative density measurement",
        json_schema={"type": "number"},
        unit="g/cm3",
        unit_normalization=UnitNormalizationSpec(
            dimension="relative_density",
            canonical_unit="kg/m3",
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
                EndpointSpec(name="current", description="Retrieve the current density value", read_only=True, output_fields=[density]),
                EndpointSpec(name="history", description="Retrieve historical density values", read_only=True, output_fields=[density]),
                EndpointSpec(name="forecast", description="Forecast future density values", read_only=True, output_fields=[density]),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "registrations_api",
            {
                "openapi": "3.1.0",
                "info": {"title": "Registration Service", "version": "1.0.0", "description": "Registration record management service"},
                "paths": {
                    "/registrations/{registration_id}": {
                        "get": {
                            "operationId": "rg17",
                            "summary": "Retrieve one already-identified registration",
                            "responses": {"200": {"description": "registration"}},
                        },
                        "patch": {
                            "operationId": "rg28",
                            "summary": "Update an existing registration",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/registrations": {
                        "post": {
                            "operationId": "rg39",
                            "summary": "Create a brand-new registration",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "observation_ops",
            {
                "tools": [
                    {
                        "name": "ob17",
                        "description": "Search observation records matching criteria",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "ob28",
                        "description": "Retrieve one already-identified observation record",
                        "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}},
                    },
                    {
                        "name": "ob39",
                        "description": "List all available observation records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="notice_delivery",
            description="Notice delivery and shared-access service",
            endpoints=[
                EndpointSpec(name="send", description="Send a notice packet to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a notice packet with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="document_transform",
            description="Content document_transform and analysis service",
            endpoints=[
                EndpointSpec(name="export", description="Export document content as an external file", read_only=True),
                EndpointSpec(name="translate", description="Translate content into another human language", read_only=True),
                EndpointSpec(name="compare", description="Compare multiple content items for similarities or differences", read_only=True),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="engines",
            description="Engine runtime control service",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing compute engine", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered engine workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="compensations",
            description="Compensation lookup and lifecycle service",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve one already-identified compensation", read_only=True),
                EndpointSpec(name="cancel", description="Cancel an active compensation request", read_only=False),
                EndpointSpec(name="refund", description="Refund money for a completed compensation transaction", read_only=False),
            ],
        )
    )

    resistivity = FieldSpec(
        name="resistivity",
        semantic_id="material.electrical_resistivity",
        description="Electrical resistivity measurement",
        json_schema={"type": "number"},
        unit="mOhm*m",
        unit_normalization=UnitNormalizationSpec(
            dimension="electrical_resistivity",
            canonical_unit="Ohm*m",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="resistivity",
            description="Resistivity observations and forecast service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current resistivity value", read_only=True, output_fields=[resistivity]),
                EndpointSpec(name="history", description="Retrieve historical resistivity values", read_only=True, output_fields=[resistivity]),
                EndpointSpec(name="forecast", description="Forecast future resistivity values", read_only=True, output_fields=[resistivity]),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("authorizations_api.au17","retrieve",{"en":"authorization LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"authorization LIC-8"}),
    RouteCaseSpec("authorizations_api.au28","update",{"en":"authorization LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"authorization LIC-8"}),
    RouteCaseSpec("authorizations_api.au39","delete",{"en":"authorization LIC-8","ko":"라이선스 LIC-8","es":"licencia LIC-8","ja":"ライセンスLIC-8","de":"lizenz LIC-8","mixed":"authorization LIC-8"}),
    RouteCaseSpec("ledger_ops.ld17","search",{"en":"ledger entries about silicate","ko":"silicate 관련 레지스트리 항목","es":"entradas de registro sobre silicate","ja":"silicateに関する登録項目","de":"registereinträge zu silicate","mixed":"silicate 관련 ledger entries"}),
    RouteCaseSpec("ledger_ops.ld28","retrieve",{"en":"ledger entry G-4","ko":"레지스트리 항목 G-4","es":"entrada de registro G-4","ja":"登録項目G-4","de":"registereintrag G-4","mixed":"ledger entry G-4"}),
    RouteCaseSpec("ledger_ops.ld39","list",{"en":"ledger entries","ko":"레지스트리 항목","es":"entradas de registro","ja":"登録項目","de":"registereinträge","mixed":"ledger entries"}),
    RouteCaseSpec("packet_delivery.send","send",{"en":"delivery bundle PK-5","ko":"소포 패킷 PK-5","es":"paquete PK-5","ja":"小包パケットPK-5","de":"paket PK-5","mixed":"delivery bundle PK-5"}),
    RouteCaseSpec("packet_delivery.share","share",{"en":"delivery bundle PK-5","ko":"소포 패킷 PK-5","es":"paquete PK-5","ja":"小包パケットPK-5","de":"paket PK-5","mixed":"delivery bundle PK-5"}),
    RouteCaseSpec("publication_ops.export","export",{"en":"publication_ops artifact R-3","ko":"렌더링 아티팩트 R-3","es":"artefacto de renderizado R-3","ja":"レンダリング成果物R-3","de":"publication_ops-artefakt R-3","mixed":"publication_ops artifact R-3"}),
    RouteCaseSpec("publication_ops.summarize","summarize",{"en":"publication_ops artifact R-3","ko":"렌더링 아티팩트 R-3","es":"artefacto de renderizado R-3","ja":"レンダリング成果物R-3","de":"publication_ops-artefakt R-3","mixed":"publication_ops artifact R-3"}),
    RouteCaseSpec("publication_ops.merge","merge",{"en":"publication_ops artifacts R-3 and R-4","ko":"렌더링 아티팩트 R-3과 R-4","es":"artefactos R-3 y R-4","ja":"レンダリング成果物R-3とR-4","de":"publication_ops-artefakte R-3 und R-4","mixed":"publication_ops artifacts R-3 R-4"}),
    RouteCaseSpec("controllers.restart","restart",{"en":"controller D-2","ko":"데몬 D-2","es":"controller D-2","ja":"デーモンD-2","de":"controller D-2","mixed":"controller D-2"}),
    RouteCaseSpec("controllers.execute","execute",{"en":"controller operation D-2","ko":"데몬 작업 D-2","es":"operación de controller D-2","ja":"デーモン操作D-2","de":"controller-operation D-2","mixed":"controller operation D-2"}),
    RouteCaseSpec("service_orders.create","create",{"en":"service order","ko":"상환 요청","es":"reembolso","ja":"償還申請","de":"erstattungsantrag","mixed":"service order"}),
    RouteCaseSpec("service_orders.cancel","cancel",{"en":"service order RB-7","ko":"상환 요청 RB-7","es":"reembolso RB-7","ja":"償還申請RB-7","de":"erstattungsantrag RB-7","mixed":"service order RB-7"}),
    RouteCaseSpec("service_orders.refund","refund",{"en":"service order payment RB-7","ko":"상환 결제 RB-7","es":"pago de reembolso RB-7","ja":"償還支払いRB-7","de":"erstattungszahlung RB-7","mixed":"service order payment RB-7"}),
    RouteCaseSpec("density.current","retrieve",{"en":"density value","ko":"습도 값","es":"valor de humedad","ja":"湿度値","de":"luftfeuchtigkeitswert","mixed":"density 값"},temporal_scope="current"),
    RouteCaseSpec("density.history","retrieve",{"en":"density values","ko":"습도 값","es":"valores de humedad","ja":"湿度値","de":"luftfeuchtigkeitswerte","mixed":"density 값"},temporal_scope="historical"),
    RouteCaseSpec("density.forecast","forecast",{"en":"density values","ko":"습도 값","es":"valores de humedad","ja":"湿度値","de":"luftfeuchtigkeitswerte","mixed":"density 값"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("registrations_api.rg17","retrieve",{"en":"registration CERT-6","ko":"인증서 CERT-6","es":"certificado CERT-6","ja":"証明書CERT-6","de":"zertifikat CERT-6","mixed":"registration CERT-6"}),
    RouteCaseSpec("registrations_api.rg28","update",{"en":"registration CERT-6","ko":"인증서 CERT-6","es":"certificado CERT-6","ja":"証明書CERT-6","de":"zertifikat CERT-6","mixed":"registration CERT-6"}),
    RouteCaseSpec("registrations_api.rg39","create",{"en":"registration","ko":"인증서","es":"certificado","ja":"証明書","de":"zertifikat","mixed":"registration"}),
    RouteCaseSpec("observation_ops.ob17","search",{"en":"observation records about cobalt","ko":"cobalt 관련 카탈로그 레코드","es":"registros de catálogo sobre cobalt","ja":"cobaltに関するカタログ記録","de":"katalogdatensätze zu cobalt","mixed":"cobalt 관련 observation records"}),
    RouteCaseSpec("observation_ops.ob28","retrieve",{"en":"observation record Q-9","ko":"카탈로그 레코드 Q-9","es":"registro de catálogo Q-9","ja":"カタログ記録Q-9","de":"katalogdatensatz Q-9","mixed":"observation record Q-9"}),
    RouteCaseSpec("observation_ops.ob39","list",{"en":"observation records","ko":"카탈로그 레코드","es":"registros de catálogo","ja":"カタログ記録","de":"katalogdatensätze","mixed":"observation records"}),
    RouteCaseSpec("notice_delivery.send","send",{"en":"notice packet M-2","ko":"메시지 페이로드 M-2","es":"carga de mensaje M-2","ja":"メッセージペイロードM-2","de":"nachrichtenpayload M-2","mixed":"notice packet M-2"}),
    RouteCaseSpec("notice_delivery.share","share",{"en":"notice packet M-2","ko":"메시지 페이로드 M-2","es":"carga de mensaje M-2","ja":"メッセージペイロードM-2","de":"nachrichtenpayload M-2","mixed":"notice packet M-2"}),
    RouteCaseSpec("document_transform.export","export",{"en":"document content C-1","ko":"변환 콘텐츠 C-1","es":"contenido convertido C-1","ja":"変換コンテンツC-1","de":"konvertierter inhalt C-1","mixed":"document content C-1"}),
    RouteCaseSpec("document_transform.translate","translate",{"en":"document content C-1","ko":"변환 콘텐츠 C-1","es":"contenido convertido C-1","ja":"変換コンテンツC-1","de":"konvertierter inhalt C-1","mixed":"document content C-1"}),
    RouteCaseSpec("document_transform.compare","compare",{"en":"document content C-1 and C-2","ko":"변환 콘텐츠 C-1과 C-2","es":"contenidos C-1 y C-2","ja":"変換コンテンツC-1とC-2","de":"konvertierte inhalte C-1 und C-2","mixed":"document content C-1 C-2"}),
    RouteCaseSpec("engines.restart","restart",{"en":"engine CL-5","ko":"클러스터 CL-5","es":"clúster CL-5","ja":"クラスタCL-5","de":"engine CL-5","mixed":"engine CL-5"}),
    RouteCaseSpec("engines.execute","execute",{"en":"engine workflow CL-5","ko":"클러스터 워크플로 CL-5","es":"flujo de clúster CL-5","ja":"クラスタワークフローCL-5","de":"engine-workflow CL-5","mixed":"engine workflow CL-5"}),
    RouteCaseSpec("compensations.retrieve","retrieve",{"en":"compensation ST-4","ko":"정산 ST-4","es":"liquidación ST-4","ja":"決済ST-4","de":"abrechnung ST-4","mixed":"compensation ST-4"}),
    RouteCaseSpec("compensations.cancel","cancel",{"en":"compensation ST-4","ko":"정산 ST-4","es":"liquidación ST-4","ja":"決済ST-4","de":"abrechnung ST-4","mixed":"compensation ST-4"}),
    RouteCaseSpec("compensations.refund","refund",{"en":"compensation payment ST-4","ko":"정산 결제 ST-4","es":"pago de liquidación ST-4","ja":"決済支払いST-4","de":"abrechnungszahlung ST-4","mixed":"compensation payment ST-4"}),
    RouteCaseSpec("resistivity.current","retrieve",{"en":"resistivity value","ko":"전도도 값","es":"valor de conductividad","ja":"導電率値","de":"leitfähigkeitswert","mixed":"resistivity 값"},temporal_scope="current"),
    RouteCaseSpec("resistivity.history","retrieve",{"en":"resistivity values","ko":"전도도 값","es":"valores de conductividad","ja":"導電率値","de":"leitfähigkeitswerte","mixed":"resistivity 값"},temporal_scope="historical"),
    RouteCaseSpec("resistivity.forecast","forecast",{"en":"resistivity values","ko":"전도도 값","es":"valores de conductividad","ja":"導電率値","de":"leitfähigkeitswerte","mixed":"resistivity 값"},temporal_scope="future"),
)
