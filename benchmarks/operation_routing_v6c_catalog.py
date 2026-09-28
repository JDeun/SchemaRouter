# ruff: noqa: E501
"""Identity-disjoint V6C catalogs for density-ratio experiment #397."""

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
                "info": {
                    "title": "Authorization Service",
                    "version": "1.0.0",
                    "description": "Authorization record administration service",
                },
                "paths": {
                    "/authorizations/{authorization_id}": {
                        "get": {
                            "operationId": "u71",
                            "summary": "Retrieve one already-identified authorization record",
                            "responses": {"200": {"description": "authorization"}},
                        },
                        "patch": {
                            "operationId": "u82",
                            "summary": "Update fields on an existing authorization record",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "u93",
                            "summary": "Delete an existing authorization record permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "literature_index",
            {
                "tools": [
                    {
                        "name": "l71",
                        "description": "Search literature index records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "l82",
                        "description": "Retrieve one already-identified literature index record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "l93",
                        "description": "List all available literature index records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="handoffs",
            description="Handoff packet delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a handoff packet to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a handoff packet with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="memos",
            description="Memo document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a memo document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a memo document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple memo documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="services",
            description="Registered service control system",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing registered service",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered service operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="orders",
            description="Purchase order lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new purchase order",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active purchase order",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed order payment",
                    read_only=False,
                ),
            ],
        )
    )

    pressure = FieldSpec(
        name="pressure",
        semantic_id="environment.pressure",
        description="Pressure measurement",
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
                EndpointSpec(
                    name="current",
                    description="Retrieve the current pressure value",
                    read_only=True,
                    output_fields=[pressure],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical pressure values",
                    read_only=True,
                    output_fields=[pressure],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future pressure values",
                    read_only=True,
                    output_fields=[pressure],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "credentials_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Credential Service",
                    "version": "1.0.0",
                    "description": "Credential record administration service",
                },
                "paths": {
                    "/credentials/{credential_id}": {
                        "get": {
                            "operationId": "c71",
                            "summary": "Retrieve one already-identified credential",
                            "responses": {"200": {"description": "credential"}},
                        },
                        "patch": {
                            "operationId": "c82",
                            "summary": "Update an existing credential",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/credentials": {
                        "post": {
                            "operationId": "c93",
                            "summary": "Create a brand-new credential",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "sample_catalog",
            {
                "tools": [
                    {
                        "name": "s71",
                        "description": "Search sample catalog records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "s82",
                        "description": "Retrieve one already-identified sample catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "s93",
                        "description": "List all available sample catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="alerts",
            description="Alert delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send an alert payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an alert payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="manuscripts",
            description="Manuscript conversion and analysis service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export manuscript content as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate manuscript content into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple manuscripts for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="engines",
            description="Processing engine control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing processing engine",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered processing engine operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="subscriptions",
            description="Subscription lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified subscription",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active subscription",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed subscription payment",
                    read_only=False,
                ),
            ],
        )
    )

    flow_rate = FieldSpec(
        name="volumetric_flow_rate",
        semantic_id="process.volumetric_flow_rate",
        description="Volumetric flow-rate measurement",
        json_schema={"type": "number"},
        unit="L/min",
        unit_normalization=UnitNormalizationSpec(
            dimension="volumetric_flow_rate",
            canonical_unit="m^3/s",
            scale=1.6666666666666667e-5,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="flow_rate",
            description="Flow-rate observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current volumetric flow-rate value",
                    read_only=True,
                    output_fields=[flow_rate],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical volumetric flow-rate values",
                    read_only=True,
                    output_fields=[flow_rate],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future volumetric flow-rate values",
                    read_only=True,
                    output_fields=[flow_rate],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("authorizations_api.u71", "retrieve", {"en":"authorization AU-5","ko":"승인 기록 AU-5","es":"autorización AU-5","ja":"認可記録AU-5","de":"autorisierung AU-5","mixed":"authorization AU-5"}),
    RouteCaseSpec("authorizations_api.u82", "update", {"en":"authorization AU-5","ko":"승인 기록 AU-5","es":"autorización AU-5","ja":"認可記録AU-5","de":"autorisierung AU-5","mixed":"authorization AU-5"}),
    RouteCaseSpec("authorizations_api.u93", "delete", {"en":"authorization AU-5","ko":"승인 기록 AU-5","es":"autorización AU-5","ja":"認可記録AU-5","de":"autorisierung AU-5","mixed":"authorization AU-5"}),
    RouteCaseSpec("literature_index.l71", "search", {"en":"literature records about spinel","ko":"spinel 관련 문헌 기록","es":"registros bibliográficos sobre spinel","ja":"spinelに関する文献記録","de":"literaturdatensätze zu spinel","mixed":"spinel 관련 literature records"}),
    RouteCaseSpec("literature_index.l82", "retrieve", {"en":"literature record LT-4","ko":"문헌 기록 LT-4","es":"registro bibliográfico LT-4","ja":"文献記録LT-4","de":"literaturdatensatz LT-4","mixed":"literature record LT-4"}),
    RouteCaseSpec("literature_index.l93", "list", {"en":"literature records","ko":"문헌 기록","es":"registros bibliográficos","ja":"文献記録","de":"literaturdatensätze","mixed":"literature records"}),
    RouteCaseSpec("handoffs.send", "send", {"en":"handoff packet HF-8","ko":"인계 패킷 HF-8","es":"paquete de traspaso HF-8","ja":"引継ぎパケットHF-8","de":"übergabepaket HF-8","mixed":"handoff packet HF-8"}),
    RouteCaseSpec("handoffs.share", "share", {"en":"handoff packet HF-8","ko":"인계 패킷 HF-8","es":"paquete de traspaso HF-8","ja":"引継ぎパケットHF-8","de":"übergabepaket HF-8","mixed":"handoff packet HF-8"}),
    RouteCaseSpec("memos.export", "export", {"en":"memo document MM-3","ko":"메모 문서 MM-3","es":"documento memo MM-3","ja":"メモ文書MM-3","de":"memodokument MM-3","mixed":"memo document MM-3"}),
    RouteCaseSpec("memos.summarize", "summarize", {"en":"memo document MM-3","ko":"메모 문서 MM-3","es":"documento memo MM-3","ja":"メモ文書MM-3","de":"memodokument MM-3","mixed":"memo document MM-3"}),
    RouteCaseSpec("memos.merge", "merge", {"en":"memo documents MM-3 and MM-4","ko":"메모 문서 MM-3과 MM-4","es":"documentos memo MM-3 y MM-4","ja":"メモ文書MM-3とMM-4","de":"memodokumente MM-3 und MM-4","mixed":"memo documents MM-3 MM-4"}),
    RouteCaseSpec("services.restart", "restart", {"en":"registered service SV-2","ko":"등록 서비스 SV-2","es":"servicio registrado SV-2","ja":"登録サービスSV-2","de":"registrierter dienst SV-2","mixed":"registered service SV-2"}),
    RouteCaseSpec("services.execute", "execute", {"en":"service operation SV-2","ko":"서비스 작업 SV-2","es":"operación de servicio SV-2","ja":"サービス操作SV-2","de":"dienstoperation SV-2","mixed":"service operation SV-2"}),
    RouteCaseSpec("orders.create", "create", {"en":"purchase order","ko":"구매 주문","es":"orden de compra","ja":"購入注文","de":"bestellung","mixed":"purchase order"}),
    RouteCaseSpec("orders.cancel", "cancel", {"en":"purchase order OD-7","ko":"구매 주문 OD-7","es":"orden OD-7","ja":"購入注文OD-7","de":"bestellung OD-7","mixed":"purchase order OD-7"}),
    RouteCaseSpec("orders.refund", "refund", {"en":"order payment OD-7","ko":"주문 결제 OD-7","es":"pago de pedido OD-7","ja":"注文支払いOD-7","de":"bestellzahlung OD-7","mixed":"order payment OD-7"}),
    RouteCaseSpec("pressure.current", "retrieve", {"en":"pressure value","ko":"압력 값","es":"valor de presión","ja":"圧力値","de":"druckwert","mixed":"pressure 값"}, temporal_scope="current"),
    RouteCaseSpec("pressure.history", "retrieve", {"en":"pressure values","ko":"압력 값","es":"valores de presión","ja":"圧力値","de":"druckwerte","mixed":"pressure 값"}, temporal_scope="historical"),
    RouteCaseSpec("pressure.forecast", "forecast", {"en":"pressure values","ko":"압력 값","es":"valores de presión","ja":"圧力値","de":"druckwerte","mixed":"pressure 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("credentials_api.c71", "retrieve", {"en":"credential CR-6","ko":"자격 증명 CR-6","es":"credencial CR-6","ja":"資格情報CR-6","de":"zugangsnachweis CR-6","mixed":"credential CR-6"}),
    RouteCaseSpec("credentials_api.c82", "update", {"en":"credential CR-6","ko":"자격 증명 CR-6","es":"credencial CR-6","ja":"資格情報CR-6","de":"zugangsnachweis CR-6","mixed":"credential CR-6"}),
    RouteCaseSpec("credentials_api.c93", "create", {"en":"credential","ko":"자격 증명","es":"credencial","ja":"資格情報","de":"zugangsnachweis","mixed":"credential"}),
    RouteCaseSpec("sample_catalog.s71", "search", {"en":"sample records about zirconia","ko":"zirconia 관련 시료 기록","es":"registros de muestras sobre zirconia","ja":"zirconiaに関する試料記録","de":"probendatensätze zu zirconia","mixed":"zirconia 관련 sample records"}),
    RouteCaseSpec("sample_catalog.s82", "retrieve", {"en":"sample record SP-9","ko":"시료 기록 SP-9","es":"registro de muestra SP-9","ja":"試料記録SP-9","de":"probendatensatz SP-9","mixed":"sample record SP-9"}),
    RouteCaseSpec("sample_catalog.s93", "list", {"en":"sample records","ko":"시료 기록","es":"registros de muestras","ja":"試料記録","de":"probendatensätze","mixed":"sample records"}),
    RouteCaseSpec("alerts.send", "send", {"en":"alert payload AL-2","ko":"경보 페이로드 AL-2","es":"carga de alerta AL-2","ja":"アラートペイロードAL-2","de":"alarmpayload AL-2","mixed":"alert payload AL-2"}),
    RouteCaseSpec("alerts.share", "share", {"en":"alert payload AL-2","ko":"경보 페이로드 AL-2","es":"carga de alerta AL-2","ja":"アラートペイロードAL-2","de":"alarmpayload AL-2","mixed":"alert payload AL-2"}),
    RouteCaseSpec("manuscripts.export", "export", {"en":"manuscript MS-1","ko":"원고 MS-1","es":"manuscrito MS-1","ja":"原稿MS-1","de":"manuskript MS-1","mixed":"manuscript MS-1"}),
    RouteCaseSpec("manuscripts.translate", "translate", {"en":"manuscript MS-1","ko":"원고 MS-1","es":"manuscrito MS-1","ja":"原稿MS-1","de":"manuskript MS-1","mixed":"manuscript MS-1"}),
    RouteCaseSpec("manuscripts.compare", "compare", {"en":"manuscripts MS-1 and MS-2","ko":"원고 MS-1과 MS-2","es":"manuscritos MS-1 y MS-2","ja":"原稿MS-1とMS-2","de":"manuskripte MS-1 und MS-2","mixed":"manuscripts MS-1 MS-2"}),
    RouteCaseSpec("engines.restart", "restart", {"en":"processing engine EN-5","ko":"처리 엔진 EN-5","es":"motor de procesamiento EN-5","ja":"処理エンジンEN-5","de":"verarbeitungsengine EN-5","mixed":"processing engine EN-5"}),
    RouteCaseSpec("engines.execute", "execute", {"en":"engine operation EN-5","ko":"엔진 작업 EN-5","es":"operación de motor EN-5","ja":"エンジン操作EN-5","de":"engine-operation EN-5","mixed":"engine operation EN-5"}),
    RouteCaseSpec("subscriptions.retrieve", "retrieve", {"en":"subscription SB-4","ko":"구독 SB-4","es":"suscripción SB-4","ja":"購読SB-4","de":"abonnement SB-4","mixed":"subscription SB-4"}),
    RouteCaseSpec("subscriptions.cancel", "cancel", {"en":"subscription SB-4","ko":"구독 SB-4","es":"suscripción SB-4","ja":"購読SB-4","de":"abonnement SB-4","mixed":"subscription SB-4"}),
    RouteCaseSpec("subscriptions.refund", "refund", {"en":"subscription payment SB-4","ko":"구독 결제 SB-4","es":"pago de suscripción SB-4","ja":"購読支払いSB-4","de":"abonnementzahlung SB-4","mixed":"subscription payment SB-4"}),
    RouteCaseSpec("flow_rate.current", "retrieve", {"en":"flow-rate value","ko":"유량 값","es":"valor de caudal","ja":"流量値","de":"durchflusswert","mixed":"flow-rate 값"}, temporal_scope="current"),
    RouteCaseSpec("flow_rate.history", "retrieve", {"en":"flow-rate values","ko":"유량 값","es":"valores de caudal","ja":"流量値","de":"durchflusswerte","mixed":"flow-rate 값"}, temporal_scope="historical"),
    RouteCaseSpec("flow_rate.forecast", "forecast", {"en":"flow-rate values","ko":"유량 값","es":"valores de caudal","ja":"流量値","de":"durchflusswerte","mixed":"flow-rate 값"}, temporal_scope="future"),
)
