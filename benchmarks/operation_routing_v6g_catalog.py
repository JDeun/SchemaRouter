# ruff: noqa: E501
"""Identity-disjoint V6G catalogs for frozen GTE positive retrieval experiment #409."""

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
            "directives_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Directive Service",
                    "version": "1.0.0",
                    "description": "Directive record administration service",
                },
                "paths": {
                    "/directives/{directive_id}": {
                        "get": {
                            "operationId": "r14",
                            "summary": "Retrieve one already-identified directive record",
                            "responses": {"200": {"description": "directive"}},
                        },
                        "patch": {
                            "operationId": "r25",
                            "summary": "Update fields on an existing directive record",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "r36",
                            "summary": "Delete an existing directive record permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "alloy_catalog",
            {
                "tools": [
                    {
                        "name": "s14",
                        "description": "Search alloy catalog records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "s25",
                        "description": "Retrieve one already-identified alloy catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "s36",
                        "description": "List all available alloy catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="signals",
            description="Signal dispatch and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a signal payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a signal payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="reports",
            description="Report document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a report document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a report document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple report documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="process_units",
            description="Process-unit runtime service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing process-unit runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a process-unit operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="credits",
            description="Credit lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new credit",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active credit",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed credit payment",
                    read_only=False,
                ),
            ],
        )
    )

    shear_modulus = FieldSpec(
        name="shear_modulus",
        semantic_id="material.shear_modulus",
        description="Shear modulus measurement",
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
            name="shear_modulus",
            description="Shear modulus observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current shear modulus value",
                    read_only=True,
                    output_fields=[shear_modulus],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical shear modulus values",
                    read_only=True,
                    output_fields=[shear_modulus],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future shear modulus values",
                    read_only=True,
                    output_fields=[shear_modulus],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "clearances_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Clearance Service",
                    "version": "1.0.0",
                    "description": "Clearance record administration service",
                },
                "paths": {
                    "/clearances/{clearance_id}": {
                        "get": {
                            "operationId": "t14",
                            "summary": "Retrieve one already-identified clearance record",
                            "responses": {"200": {"description": "clearance record"}},
                        },
                        "patch": {
                            "operationId": "t25",
                            "summary": "Update an existing clearance record",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/clearances": {
                        "post": {
                            "operationId": "t36",
                            "summary": "Create a brand-new clearance record",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "mixture_catalog",
            {
                "tools": [
                    {
                        "name": "u14",
                        "description": "Search mixture catalog records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "u25",
                        "description": "Retrieve one already-identified mixture catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "u36",
                        "description": "List all available mixture catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="deliveries",
            description="Delivery dispatch and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a delivery payload to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an delivery payload with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="annotations",
            description="Annotation conversion and analysis service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export annotation content as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate annotation content into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple annotations for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="simulators",
            description="Simulator control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing simulator",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered simulator operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="leases",
            description="Lease lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified lease",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active lease",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed lease payment",
                    read_only=False,
                ),
            ],
        )
    )

    electrical_conductivity = FieldSpec(
        name="electrical_conductivity",
        semantic_id="material.electrical_conductivity",
        description="Electrical conductivity measurement",
        json_schema={"type": "number"},
        unit="mS/cm",
        unit_normalization=UnitNormalizationSpec(
            dimension="electrical_conductivity",
            canonical_unit="mS/cm",
            scale=0.1,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="electrical_conductivity",
            description="Electrical conductivity observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current electrical conductivity value",
                    read_only=True,
                    output_fields=[electrical_conductivity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical electrical conductivity values",
                    read_only=True,
                    output_fields=[electrical_conductivity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future electrical conductivity values",
                    read_only=True,
                    output_fields=[electrical_conductivity],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("directives_api.r14", "retrieve", {"en":"directive DR-5","ko":"지시 기록 DR-5","es":"directiva DR-5","ja":"指示記録DR-5","de":"direktive DR-5","mixed":"directive DR-5"}),
    RouteCaseSpec("directives_api.r25", "update", {"en":"directive DR-5","ko":"지시 기록 DR-5","es":"directiva DR-5","ja":"指示記録DR-5","de":"direktive DR-5","mixed":"directive DR-5"}),
    RouteCaseSpec("directives_api.r36", "delete", {"en":"directive DR-5","ko":"지시 기록 DR-5","es":"directiva DR-5","ja":"指示記録DR-5","de":"direktive DR-5","mixed":"directive DR-5"}),
    RouteCaseSpec("alloy_catalog.s14", "search", {"en":"alloy records about nickel","ko":"니켈 관련 합금 기록","es":"registros de aleaciones sobre níquel","ja":"ニッケルに関する合金記録","de":"legierungsdatensätze zu nickel","mixed":"니켈 관련 alloy records"}),
    RouteCaseSpec("alloy_catalog.s25", "retrieve", {"en":"alloy record AY-6","ko":"합금 기록 AY-6","es":"registro de aleación AY-6","ja":"合金記録AY-6","de":"legierungsdatensatz AY-6","mixed":"alloy record AY-6"}),
    RouteCaseSpec("alloy_catalog.s36", "list", {"en":"alloy records","ko":"합금 기록","es":"registros de aleaciones","ja":"合金記録","de":"legierungsdatensätze","mixed":"alloy records"}),
    RouteCaseSpec("signals.send", "send", {"en":"signal payload SG-4","ko":"신호 페이로드 SG-4","es":"carga de señal SG-4","ja":"信号ペイロードSG-4","de":"signalnutzlast SG-4","mixed":"signal payload SG-4"}),
    RouteCaseSpec("signals.share", "share", {"en":"signal payload SG-4","ko":"신호 페이로드 SG-4","es":"carga de señal SG-4","ja":"信号ペイロードSG-4","de":"signalnutzlast SG-4","mixed":"signal payload SG-4"}),
    RouteCaseSpec("reports.export", "export", {"en":"report RP-7","ko":"보고서 RP-7","es":"informe RP-7","ja":"レポートRP-7","de":"bericht RP-7","mixed":"report RP-7"}),
    RouteCaseSpec("reports.summarize", "summarize", {"en":"report RP-7","ko":"보고서 RP-7","es":"informe RP-7","ja":"レポートRP-7","de":"bericht RP-7","mixed":"report RP-7"}),
    RouteCaseSpec("reports.merge", "merge", {"en":"reports RP-7 and RP-8","ko":"보고서 RP-7과 RP-8","es":"informes RP-7 y RP-8","ja":"レポートRP-7とRP-8","de":"berichte RP-7 und RP-8","mixed":"reports RP-7 RP-8"}),
    RouteCaseSpec("process_units.restart", "restart", {"en":"process unit PU-9","ko":"공정 유닛 PU-9","es":"unidad de proceso PU-9","ja":"プロセスユニットPU-9","de":"prozesseinheit PU-9","mixed":"process unit PU-9"}),
    RouteCaseSpec("process_units.execute", "execute", {"en":"process-unit operation PU-9","ko":"공정 유닛 작업 PU-9","es":"operación de unidad de proceso PU-9","ja":"プロセスユニット操作PU-9","de":"prozesseinheitsoperation PU-9","mixed":"process-unit operation PU-9"}),
    RouteCaseSpec("credits.create", "create", {"en":"credit","ko":"크레딧","es":"crédito","ja":"クレジット","de":"gutschrift","mixed":"credit"}),
    RouteCaseSpec("credits.cancel", "cancel", {"en":"credit CR-6","ko":"크레딧 CR-6","es":"crédito CR-6","ja":"クレジットCR-6","de":"gutschrift CR-6","mixed":"credit CR-6"}),
    RouteCaseSpec("credits.refund", "refund", {"en":"credit payment CR-6","ko":"크레딧 결제 CR-6","es":"pago de crédito CR-6","ja":"クレジット支払いCR-6","de":"gutschriftzahlung CR-6","mixed":"credit payment CR-6"}),
    RouteCaseSpec("shear_modulus.current", "retrieve", {"en":"shear modulus value","ko":"전단 탄성률 값","es":"valor del módulo de corte","ja":"せん断弾性率","de":"schubmodul","mixed":"shear modulus 값"}, temporal_scope="current"),
    RouteCaseSpec("shear_modulus.history", "retrieve", {"en":"shear modulus values","ko":"전단 탄성률 값","es":"valores del módulo de corte","ja":"せん断弾性率","de":"schubmodule","mixed":"shear modulus 값"}, temporal_scope="historical"),
    RouteCaseSpec("shear_modulus.forecast", "forecast", {"en":"shear modulus values","ko":"전단 탄성률 값","es":"valores del módulo de corte","ja":"せん断弾性率","de":"schubmodule","mixed":"shear modulus 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("clearances_api.t14", "retrieve", {"en":"clearance record CL-8","ko":"허가 기록 CL-8","es":"autorización CL-8","ja":"許可記録CL-8","de":"freigabe CL-8","mixed":"clearance record CL-8"}),
    RouteCaseSpec("clearances_api.t25", "update", {"en":"clearance record CL-8","ko":"허가 기록 CL-8","es":"autorización CL-8","ja":"許可記録CL-8","de":"freigabe CL-8","mixed":"clearance record CL-8"}),
    RouteCaseSpec("clearances_api.t36", "create", {"en":"clearance record","ko":"허가 기록","es":"autorización","ja":"許可記録","de":"freigabe","mixed":"clearance record"}),
    RouteCaseSpec("mixture_catalog.u14", "search", {"en":"mixture records about alumina","ko":"알루미나 관련 혼합물 기록","es":"registros de mezclas sobre alúmina","ja":"アルミナに関する混合物記録","de":"mischungsdatensätze zu aluminiumoxid","mixed":"알루미나 관련 mixture records"}),
    RouteCaseSpec("mixture_catalog.u25", "retrieve", {"en":"mixture record MX-5","ko":"혼합물 기록 MX-5","es":"registro de mezcla MX-5","ja":"混合物記録MX-5","de":"mischungsdatensatz MX-5","mixed":"mixture record MX-5"}),
    RouteCaseSpec("mixture_catalog.u36", "list", {"en":"mixture records","ko":"혼합물 기록","es":"registros de mezclas","ja":"混合物記録","de":"mischungsdatensätze","mixed":"mixture records"}),
    RouteCaseSpec("deliveries.send", "send", {"en":"delivery payload DV-4","ko":"배송 페이로드 DV-4","es":"carga de entrega DV-4","ja":"配送ペイロードDV-4","de":"lieferpayload DV-4","mixed":"delivery payload DV-4"}),
    RouteCaseSpec("deliveries.share", "share", {"en":"delivery payload DV-4","ko":"배송 페이로드 DV-4","es":"carga de entrega DV-4","ja":"配送ペイロードDV-4","de":"lieferpayload DV-4","mixed":"delivery payload DV-4"}),
    RouteCaseSpec("annotations.export", "export", {"en":"annotation AN-3","ko":"주석 AN-3","es":"anotación AN-3","ja":"注釈AN-3","de":"annotation AN-3","mixed":"annotation AN-3"}),
    RouteCaseSpec("annotations.translate", "translate", {"en":"annotation AN-3","ko":"주석 AN-3","es":"anotación AN-3","ja":"注釈AN-3","de":"annotation AN-3","mixed":"annotation AN-3"}),
    RouteCaseSpec("annotations.compare", "compare", {"en":"annotations AN-3 and AN-4","ko":"주석 AN-3과 AN-4","es":"anotaciones AN-3 y AN-4","ja":"注釈AN-3とAN-4","de":"annotationen AN-3 und AN-4","mixed":"annotations AN-3 AN-4"}),
    RouteCaseSpec("simulators.restart", "restart", {"en":"simulator SM-7","ko":"시뮬레이터 SM-7","es":"simulador SM-7","ja":"シミュレータSM-7","de":"simulator SM-7","mixed":"simulator SM-7"}),
    RouteCaseSpec("simulators.execute", "execute", {"en":"simulator operation SM-7","ko":"시뮬레이터 작업 SM-7","es":"operación del simulador SM-7","ja":"シミュレータ操作SM-7","de":"simulator-operation SM-7","mixed":"simulator operation SM-7"}),
    RouteCaseSpec("leases.retrieve", "retrieve", {"en":"lease LS-6","ko":"임대 계약 LS-6","es":"arrendamiento LS-6","ja":"リースLS-6","de":"leasingvertrag LS-6","mixed":"lease LS-6"}),
    RouteCaseSpec("leases.cancel", "cancel", {"en":"lease LS-6","ko":"임대 계약 LS-6","es":"arrendamiento LS-6","ja":"リースLS-6","de":"leasingvertrag LS-6","mixed":"lease LS-6"}),
    RouteCaseSpec("leases.refund", "refund", {"en":"lease payment LS-6","ko":"임대 결제 LS-6","es":"pago de arrendamiento LS-6","ja":"リース支払いLS-6","de":"leasingzahlung LS-6","mixed":"lease payment LS-6"}),
    RouteCaseSpec("electrical_conductivity.current", "retrieve", {"en":"electrical conductivity value","ko":"전기 전도도 값","es":"valor de conductividad eléctrica","ja":"電気伝導率","de":"elektrische leitfähigkeit","mixed":"electrical conductivity 값"}, temporal_scope="current"),
    RouteCaseSpec("electrical_conductivity.history", "retrieve", {"en":"electrical conductivity values","ko":"전기 전도도 값","es":"valores de conductividad eléctrica","ja":"電気伝導率","de":"elektrische leitfähigkeitswerte","mixed":"electrical conductivity 값"}, temporal_scope="historical"),
    RouteCaseSpec("electrical_conductivity.forecast", "forecast", {"en":"electrical conductivity values","ko":"전기 전도도 값","es":"valores de conductividad eléctrica","ja":"電気伝導率","de":"elektrische leitfähigkeitswerte","mixed":"electrical conductivity 값"}, temporal_scope="future"),
)
