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
                EndpointSpec(name="export", description="Export a publication asset to an external file", read_only=True),
                EndpointSpec(name="summarize", description="Summarize a publication asset into its main points", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple publication assets into one result", read_only=False),
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
        semantic_id="material.mass_density",
        description="Mass density measurement",
        json_schema={"type": "number"},
        unit="g/cm3",
        unit_normalization=UnitNormalizationSpec(
            dimension="mass_density",
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
    RouteCaseSpec("authorizations_api.au17","retrieve",{"en":"authorization AUTH-8","ko":"승인 AUTH-8","es":"autorización AUTH-8","ja":"認可AUTH-8","de":"genehmigung AUTH-8","mixed":"authorization AUTH-8"}),
    RouteCaseSpec("authorizations_api.au28","update",{"en":"authorization AUTH-8","ko":"승인 AUTH-8","es":"autorización AUTH-8","ja":"認可AUTH-8","de":"genehmigung AUTH-8","mixed":"authorization AUTH-8"}),
    RouteCaseSpec("authorizations_api.au39","delete",{"en":"authorization AUTH-8","ko":"승인 AUTH-8","es":"autorización AUTH-8","ja":"認可AUTH-8","de":"genehmigung AUTH-8","mixed":"authorization AUTH-8"}),
    RouteCaseSpec("ledger_ops.ld17","search",{"en":"ledger entries about silicate","ko":"silicate 관련 원장 항목","es":"registros de libro mayor sobre silicate","ja":"silicateに関する台帳項目","de":"bucheinträge zu silicate","mixed":"silicate 관련 ledger entries"}),
    RouteCaseSpec("ledger_ops.ld28","retrieve",{"en":"ledger entry LD-4","ko":"원장 항목 LD-4","es":"registro de libro mayor LD-4","ja":"台帳項目LD-4","de":"bucheintrag LD-4","mixed":"ledger entry LD-4"}),
    RouteCaseSpec("ledger_ops.ld39","list",{"en":"ledger entries","ko":"원장 항목","es":"registros de libro mayor","ja":"台帳項目","de":"bucheinträge","mixed":"ledger entries"}),
    RouteCaseSpec("packet_delivery.send","send",{"en":"delivery bundle PK-5","ko":"배송 묶음 PK-5","es":"paquete de entrega PK-5","ja":"配送バンドルPK-5","de":"lieferpaket PK-5","mixed":"delivery bundle PK-5"}),
    RouteCaseSpec("packet_delivery.share","share",{"en":"delivery bundle PK-5","ko":"배송 묶음 PK-5","es":"paquete de entrega PK-5","ja":"配送バンドルPK-5","de":"lieferpaket PK-5","mixed":"delivery bundle PK-5"}),
    RouteCaseSpec("publication_ops.export","export",{"en":"publication asset R-3","ko":"출판 자산 R-3","es":"recurso de publicación R-3","ja":"出版アセットR-3","de":"publikationsobjekt R-3","mixed":"publication asset R-3"}),
    RouteCaseSpec("publication_ops.summarize","summarize",{"en":"publication asset R-3","ko":"출판 자산 R-3","es":"recurso de publicación R-3","ja":"出版アセットR-3","de":"publikationsobjekt R-3","mixed":"publication asset R-3"}),
    RouteCaseSpec("publication_ops.merge","merge",{"en":"publication assets R-3 and R-4","ko":"출판 자산 R-3과 R-4","es":"recursos de publicación R-3 y R-4","ja":"出版アセットR-3とR-4","de":"publikationsobjekte R-3 und R-4","mixed":"publication assets R-3 R-4"}),
    RouteCaseSpec("controllers.restart","restart",{"en":"controlador CTRL-2","ko":"컨트롤러 CTRL-2","es":"controlador CTRL-2","ja":"コントローラCTRL-2","de":"controlador CTRL-2","mixed":"controlador CTRL-2"}),
    RouteCaseSpec("controllers.execute","execute",{"en":"controller operation CTRL-2","ko":"컨트롤러 작업 CTRL-2","es":"operación de controlador CTRL-2","ja":"コントローラ操作CTRL-2","de":"controller-operation CTRL-2","mixed":"controller operation CTRL-2"}),
    RouteCaseSpec("service_orders.create","create",{"en":"service order","ko":"서비스 주문","es":"orden de servicio","ja":"サービス注文","de":"serviceauftrag","mixed":"service order"}),
    RouteCaseSpec("service_orders.cancel","cancel",{"en":"service order SO-7","ko":"서비스 주문 SO-7","es":"orden de servicio SO-7","ja":"サービス注文SO-7","de":"serviceauftrag SO-7","mixed":"service order SO-7"}),
    RouteCaseSpec("service_orders.refund","refund",{"en":"service order payment SO-7","ko":"서비스 주문 결제 SO-7","es":"pago de orden de servicio SO-7","ja":"サービス注文支払いSO-7","de":"serviceauftragszahlung SO-7","mixed":"service order payment SO-7"}),
    RouteCaseSpec("density.current","retrieve",{"en":"density value","ko":"밀도 값","es":"valor de densidad","ja":"密度値","de":"dichtewert","mixed":"density 값"},temporal_scope="current"),
    RouteCaseSpec("density.history","retrieve",{"en":"density values","ko":"밀도 값","es":"valores de densidad","ja":"密度値","de":"dichtewerte","mixed":"density 값"},temporal_scope="historical"),
    RouteCaseSpec("density.forecast","forecast",{"en":"density values","ko":"밀도 값","es":"valores de densidad","ja":"密度値","de":"dichtewerte","mixed":"density 값"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("registrations_api.rg17","retrieve",{"en":"registration REG-6","ko":"등록 REG-6","es":"registro REG-6","ja":"登録REG-6","de":"registrierung REG-6","mixed":"registration REG-6"}),
    RouteCaseSpec("registrations_api.rg28","update",{"en":"registration REG-6","ko":"등록 REG-6","es":"registro REG-6","ja":"登録REG-6","de":"registrierung REG-6","mixed":"registration REG-6"}),
    RouteCaseSpec("registrations_api.rg39","create",{"en":"registration","ko":"등록","es":"registro","ja":"登録","de":"registrierung","mixed":"registration"}),
    RouteCaseSpec("observation_ops.ob17","search",{"en":"observation records about cobalt","ko":"cobalt 관련 관측 기록","es":"registros de observación sobre cobalt","ja":"cobaltに関する観測記録","de":"beobachtungsdatensätze zu cobalt","mixed":"cobalt 관련 observation records"}),
    RouteCaseSpec("observation_ops.ob28","retrieve",{"en":"observation record OBS-9","ko":"관측 기록 OBS-9","es":"registro de observación OBS-9","ja":"観測記録OBS-9","de":"beobachtungsdatensatz OBS-9","mixed":"observation record OBS-9"}),
    RouteCaseSpec("observation_ops.ob39","list",{"en":"observation records","ko":"관측 기록","es":"registros de observación","ja":"観測記録","de":"beobachtungsdatensätze","mixed":"observation records"}),
    RouteCaseSpec("notice_delivery.send","send",{"en":"notice packet N-2","ko":"알림 패킷 N-2","es":"paquete de aviso N-2","ja":"通知パケットN-2","de":"hinweispaket N-2","mixed":"notice packet N-2"}),
    RouteCaseSpec("notice_delivery.share","share",{"en":"notice packet N-2","ko":"알림 패킷 N-2","es":"paquete de aviso N-2","ja":"通知パケットN-2","de":"hinweispaket N-2","mixed":"notice packet N-2"}),
    RouteCaseSpec("document_transform.export","export",{"en":"document content C-1","ko":"문서 콘텐츠 C-1","es":"contenido de documento C-1","ja":"文書コンテンツC-1","de":"dokumentinhalt C-1","mixed":"document content C-1"}),
    RouteCaseSpec("document_transform.translate","translate",{"en":"document content C-1","ko":"문서 콘텐츠 C-1","es":"contenido de documento C-1","ja":"文書コンテンツC-1","de":"dokumentinhalt C-1","mixed":"document content C-1"}),
    RouteCaseSpec("document_transform.compare","compare",{"en":"document content C-1 and C-2","ko":"문서 콘텐츠 C-1과 C-2","es":"contenidos de documento C-1 y C-2","ja":"文書コンテンツC-1とC-2","de":"dokumentinhalte C-1 und C-2","mixed":"document content C-1 C-2"}),
    RouteCaseSpec("engines.restart","restart",{"en":"engine ENG-5","ko":"엔진 ENG-5","es":"motor ENG-5","ja":"エンジンENG-5","de":"engine ENG-5","mixed":"engine ENG-5"}),
    RouteCaseSpec("engines.execute","execute",{"en":"engine workflow ENG-5","ko":"엔진 워크플로 ENG-5","es":"flujo de motor ENG-5","ja":"エンジンワークフローENG-5","de":"engine-workflow ENG-5","mixed":"engine workflow ENG-5"}),
    RouteCaseSpec("compensations.retrieve","retrieve",{"en":"compensation COMP-4","ko":"보상 COMP-4","es":"compensación COMP-4","ja":"補償COMP-4","de":"entschädigung COMP-4","mixed":"compensation COMP-4"}),
    RouteCaseSpec("compensations.cancel","cancel",{"en":"compensation COMP-4","ko":"보상 COMP-4","es":"compensación COMP-4","ja":"補償COMP-4","de":"entschädigung COMP-4","mixed":"compensation COMP-4"}),
    RouteCaseSpec("compensations.refund","refund",{"en":"compensation payment COMP-4","ko":"보상 결제 COMP-4","es":"pago de compensación COMP-4","ja":"補償支払いCOMP-4","de":"entschädigungszahlung COMP-4","mixed":"compensation payment COMP-4"}),
    RouteCaseSpec("resistivity.current","retrieve",{"en":"resistivity value","ko":"비저항 값","es":"valor de resistividad","ja":"抵抗率値","de":"widerstandswert","mixed":"resistivity 값"},temporal_scope="current"),
    RouteCaseSpec("resistivity.history","retrieve",{"en":"resistivity values","ko":"비저항 값","es":"valores de resistividad","ja":"抵抗率値","de":"widerstandswerte","mixed":"resistivity 값"},temporal_scope="historical"),
    RouteCaseSpec("resistivity.forecast","forecast",{"en":"resistivity values","ko":"비저항 값","es":"valores de resistividad","ja":"抵抗率値","de":"widerstandswerte","mixed":"resistivity 값"},temporal_scope="future"),
)
