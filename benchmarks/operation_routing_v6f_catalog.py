# ruff: noqa: E501
"""Identity-disjoint V6F catalogs for naturalistic operation-probe experiment #404."""

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
            "waivers_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Waiver Service",
                    "version": "1.0.0",
                    "description": "Waiver record administration service",
                },
                "paths": {
                    "/waivers/{waiver_id}": {
                        "get": {
                            "operationId": "m71",
                            "summary": "Retrieve one already-identified waiver record",
                            "responses": {"200": {"description": "waiver"}},
                        },
                        "patch": {
                            "operationId": "m82",
                            "summary": "Update fields on an existing waiver record",
                            "responses": {"200": {"description": "updated"}},
                        },
                        "delete": {
                            "operationId": "m93",
                            "summary": "Delete an existing waiver record permanently",
                            "responses": {"204": {"description": "deleted"}},
                        },
                    }
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "spectra_index",
            {
                "tools": [
                    {
                        "name": "n71",
                        "description": "Search spectrum index records matching filters or keywords",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "n82",
                        "description": "Retrieve one already-identified spectrum index record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "n93",
                        "description": "List all available spectrum index records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="parcels",
            description="Parcel delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a parcel to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a parcel with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="folios",
            description="Folio document transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a folio document to an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize a folio document into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple folio documents into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="executors",
            description="Executor runtime service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing executor runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a daemon operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="credits",
            description="Credit request lifecycle and payment service",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new credit request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active credit request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed credit request payment",
                    read_only=False,
                ),
            ],
        )
    )

    refractive_index = FieldSpec(
        name="refractive_index",
        semantic_id="material.thermal_refractive_index",
        description="Refractive-index measurement",
        json_schema={"type": "number"},
        unit="1",
        unit_normalization=UnitNormalizationSpec(
            dimension="thermal_refractive_index",
            canonical_unit="1",
            scale=1.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="refractive_index",
            description="Refractive-index observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current refractive-index value",
                    read_only=True,
                    output_fields=[refractive_index],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical refractive-index values",
                    read_only=True,
                    output_fields=[refractive_index],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future refractive-index values",
                    read_only=True,
                    output_fields=[refractive_index],
                ),
            ],
        )
    )

    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    registry.register(
        tool_from_openapi(
            "leases_api",
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Lease Service",
                    "version": "1.0.0",
                    "description": "Lease record administration service",
                },
                "paths": {
                    "/leases/{lease_id}": {
                        "get": {
                            "operationId": "p71",
                            "summary": "Retrieve one already-identified lease",
                            "responses": {"200": {"description": "lease"}},
                        },
                        "patch": {
                            "operationId": "p82",
                            "summary": "Update an existing lease",
                            "responses": {"200": {"description": "updated"}},
                        },
                    },
                    "/leases": {
                        "post": {
                            "operationId": "p93",
                            "summary": "Create a brand-new lease",
                            "responses": {"201": {"description": "created"}},
                        }
                    },
                },
            },
        )
    )

    registry.register(
        tool_from_mcp(
            "formula_index",
            {
                "tools": [
                    {
                        "name": "q71",
                        "description": "Search formula catalog records matching criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "q82",
                        "description": "Retrieve one already-identified formula catalog record",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"record_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "q93",
                        "description": "List all available formula catalog records",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="envelopes",
            description="Envelope delivery and delegated-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a envelope message to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to an envelope message with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="transcripts",
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
                    description="Compare multiple transcripts for similarities or differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="runtimes",
            description="Runtime worker control service",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing runtime worker",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered runtime worker operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="vouchers",
            description="Voucher lookup and lifecycle service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified voucher",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active voucher",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund money for a completed voucher payment",
                    read_only=False,
                ),
            ],
        )
    )

    dielectric_constant = FieldSpec(
        name="dielectric_constant",
        semantic_id="material.specific_dielectric_constant",
        description="Relative-permittivity measurement",
        json_schema={"type": "number"},
        unit="1",
        unit_normalization=UnitNormalizationSpec(
            dimension="specific_dielectric_constant",
            canonical_unit="1",
            scale=1.0,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="dielectric_constant",
            description="Relative-permittivity observations and forecast service",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current dielectric-constant value",
                    read_only=True,
                    output_fields=[dielectric_constant],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical dielectric-constant values",
                    read_only=True,
                    output_fields=[dielectric_constant],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future dielectric-constant values",
                    read_only=True,
                    output_fields=[dielectric_constant],
                ),
            ],
        )
    )

    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("waivers_api.m71", "retrieve", {"en":"waiver WV-5","ko":"면제 기록 WV-5","es":"exención WV-5","ja":"免除記録WV-5","de":"ausnahmeregelung WV-5","mixed":"waiver WV-5"}),
    RouteCaseSpec("waivers_api.m82", "update", {"en":"waiver WV-5","ko":"면제 기록 WV-5","es":"exención WV-5","ja":"免除記録WV-5","de":"ausnahmeregelung WV-5","mixed":"waiver WV-5"}),
    RouteCaseSpec("waivers_api.m93", "delete", {"en":"waiver WV-5","ko":"면제 기록 WV-5","es":"exención WV-5","ja":"免除記録WV-5","de":"ausnahmeregelung WV-5","mixed":"waiver WV-5"}),
    RouteCaseSpec("spectra_index.n71", "search", {"en":"spectrum records about zirconia","ko":"zirconia 관련 문헌 기록","es":"registros bibliográficos sobre zirconia","ja":"zirconiaに関する文献記録","de":"literaturdatensätze zu zirconia","mixed":"zirconia 관련 spectrum records"}),
    RouteCaseSpec("spectra_index.n82", "retrieve", {"en":"spectrum record SP-6","ko":"문헌 기록 SP-6","es":"registro bibliográfico SP-6","ja":"文献記録SP-6","de":"literaturdatensatz SP-6","mixed":"spectrum record SP-6"}),
    RouteCaseSpec("spectra_index.n93", "list", {"en":"spectrum records","ko":"문헌 기록","es":"registros bibliográficos","ja":"文献記録","de":"literaturdatensätze","mixed":"spectrum records"}),
    RouteCaseSpec("parcels.send", "send", {"en":"parcel PC-4","ko":"소포 PC-4","es":"paquete PC-4","ja":"荷物PC-4","de":"paket PC-4","mixed":"parcel PC-4"}),
    RouteCaseSpec("parcels.share", "share", {"en":"parcel PC-4","ko":"소포 PC-4","es":"paquete PC-4","ja":"荷物PC-4","de":"paket PC-4","mixed":"parcel PC-4"}),
    RouteCaseSpec("folios.export", "export", {"en":"folio document FO-7","ko":"폴리오 문서 FO-7","es":"documento folio FO-7","ja":"フォリオ文書FO-7","de":"foliodokument FO-7","mixed":"folio document FO-7"}),
    RouteCaseSpec("folios.summarize", "summarize", {"en":"folio document FO-7","ko":"폴리오 문서 FO-7","es":"documento folio FO-7","ja":"フォリオ文書FO-7","de":"foliodokument FO-7","mixed":"folio document FO-7"}),
    RouteCaseSpec("folios.merge", "merge", {"en":"folio documents FO-7 and FO-8","ko":"폴리오 문서 FO-7과 FO-8","es":"documentos folio FO-7 y FO-8","ja":"フォリオ文書FO-7とFO-8","de":"foliodokumente FO-7 und FO-8","mixed":"folio documents FO-7 FO-8"}),
    RouteCaseSpec("executors.restart", "restart", {"en":"executor EX-9","ko":"실행기 EX-9","es":"ejecutor EX-9","ja":"実行器EX-9","de":"executor EX-9","mixed":"executor EX-9"}),
    RouteCaseSpec("executors.execute", "execute", {"en":"executor operation EX-9","ko":"실행기 작업 EX-9","es":"operación del ejecutor EX-9","ja":"実行器操作EX-9","de":"executor-operation EX-9","mixed":"executor operation EX-9"}),
    RouteCaseSpec("credits.create", "create", {"en":"credit request","ko":"신용 요청","es":"solicitud de crédito","ja":"クレジット申請","de":"kreditantrag","mixed":"credit request"}),
    RouteCaseSpec("credits.cancel", "cancel", {"en":"credit request CR-6","ko":"신용 요청 CR-6","es":"solicitud de crédito CR-6","ja":"クレジット申請CR-6","de":"kreditantrag CR-6","mixed":"credit request CR-6"}),
    RouteCaseSpec("credits.refund", "refund", {"en":"credit request payment CR-6","ko":"신용 요청 결제 CR-6","es":"pago de solicitud de crédito CR-6","ja":"クレジット申請支払いCR-6","de":"kreditantragszahlung CR-6","mixed":"credit request payment CR-6"}),
    RouteCaseSpec("refractive_index.current", "retrieve", {"en":"refractive-index value","ko":"굴절률 값","es":"valor de índice de refracción","ja":"屈折率値","de":"brechungsindex","mixed":"refractive-index 값"}, temporal_scope="current"),
    RouteCaseSpec("refractive_index.history", "retrieve", {"en":"refractive-index values","ko":"굴절률 값","es":"valores de índice de refracción","ja":"屈折率値","de":"brechungsindexe","mixed":"refractive-index 값"}, temporal_scope="historical"),
    RouteCaseSpec("refractive_index.forecast", "forecast", {"en":"refractive-index values","ko":"굴절률 값","es":"valores de índice de refracción","ja":"屈折率値","de":"brechungsindexe","mixed":"refractive-index 값"}, temporal_scope="future"),
)


CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("leases_api.p71", "retrieve", {"en":"lease LS-8","ko":"임대 기록 LS-8","es":"arrendamiento LS-8","ja":"リースLS-8","de":"leasing LS-8","mixed":"lease LS-8"}),
    RouteCaseSpec("leases_api.p82", "update", {"en":"lease LS-8","ko":"임대 기록 LS-8","es":"arrendamiento LS-8","ja":"リースLS-8","de":"leasing LS-8","mixed":"lease LS-8"}),
    RouteCaseSpec("leases_api.p93", "create", {"en":"lease","ko":"임대 기록","es":"arrendamiento","ja":"リース","de":"leasing","mixed":"lease"}),
    RouteCaseSpec("formula_index.q71", "search", {"en":"formula records about alumina","ko":"alumina 관련 조성 기록","es":"registros de fórmula sobre alumina","ja":"aluminaに関する配合記録","de":"formeldatensätze zu alumina","mixed":"alumina 관련 formula records"}),
    RouteCaseSpec("formula_index.q82", "retrieve", {"en":"formula record FM-5","ko":"조성 기록 FM-5","es":"registro de fórmula FM-5","ja":"配合記録FM-5","de":"formeldatensatz FM-5","mixed":"formula record FM-5"}),
    RouteCaseSpec("formula_index.q93", "list", {"en":"formula records","ko":"조성 기록","es":"registros de fórmula","ja":"配合記録","de":"formeldatensätze","mixed":"formula records"}),
    RouteCaseSpec("envelopes.send", "send", {"en":"envelope message EV-4","ko":"봉투 메시지 EV-4","es":"mensaje de sobre EV-4","ja":"封筒メッセージEV-4","de":"umschlagnachricht EV-4","mixed":"envelope message EV-4"}),
    RouteCaseSpec("envelopes.share", "share", {"en":"envelope message EV-4","ko":"봉투 메시지 EV-4","es":"mensaje de sobre EV-4","ja":"封筒メッセージEV-4","de":"umschlagnachricht EV-4","mixed":"envelope message EV-4"}),
    RouteCaseSpec("transcripts.export", "export", {"en":"transcript TR-3","ko":"전사 기록 TR-3","es":"transcripción TR-3","ja":"文字起こしTR-3","de":"transkript TR-3","mixed":"transcript TR-3"}),
    RouteCaseSpec("transcripts.translate", "translate", {"en":"transcript TR-3","ko":"전사 기록 TR-3","es":"transcripción TR-3","ja":"文字起こしTR-3","de":"transkript TR-3","mixed":"transcript TR-3"}),
    RouteCaseSpec("transcripts.compare", "compare", {"en":"transcripts TR-3 and TR-4","ko":"전사 기록 TR-3과 TR-4","es":"transcripciones TR-3 y TR-4","ja":"文字起こしTR-3とTR-4","de":"transkripte TR-3 und TR-4","mixed":"transcripts TR-3 TR-4"}),
    RouteCaseSpec("runtimes.restart", "restart", {"en":"runtime worker RT-7","ko":"런타임 작업자 RT-7","es":"trabajador de ejecución RT-7","ja":"ランタイムワーカーRT-7","de":"laufzeit-worker RT-7","mixed":"runtime worker RT-7"}),
    RouteCaseSpec("runtimes.execute", "execute", {"en":"runtime worker operation RT-7","ko":"엔진 작업 RT-7","es":"operación de ejecución RT-7","ja":"ランタイム操作RT-7","de":"runtime-operation RT-7","mixed":"runtime worker operation RT-7"}),
    RouteCaseSpec("vouchers.retrieve", "retrieve", {"en":"voucher VC-6","ko":"바우처 VC-6","es":"vale VC-6","ja":"バウチャーVC-6","de":"gutschein VC-6","mixed":"voucher VC-6"}),
    RouteCaseSpec("vouchers.cancel", "cancel", {"en":"voucher VC-6","ko":"바우처 VC-6","es":"vale VC-6","ja":"バウチャーVC-6","de":"gutschein VC-6","mixed":"voucher VC-6"}),
    RouteCaseSpec("vouchers.refund", "refund", {"en":"voucher payment VC-6","ko":"바우처 결제 VC-6","es":"pago de vale VC-6","ja":"バウチャー支払いVC-6","de":"gutscheinzahlung VC-6","mixed":"voucher payment VC-6"}),
    RouteCaseSpec("dielectric_constant.current", "retrieve", {"en":"dielectric-constant value","ko":"유전율 값","es":"valor de permitividad relativa","ja":"比誘電率","de":"relative-permittivität","mixed":"dielectric-constant 값"}, temporal_scope="current"),
    RouteCaseSpec("dielectric_constant.history", "retrieve", {"en":"dielectric-constant values","ko":"유전율 값","es":"valores de permitividad relativa","ja":"比誘電率","de":"relative-permittivitäte","mixed":"dielectric-constant 값"}, temporal_scope="historical"),
    RouteCaseSpec("dielectric_constant.forecast", "forecast", {"en":"dielectric-constant values","ko":"유전율 값","es":"valores de permitividad relativa","ja":"比誘電率","de":"relative-permittivitäte","mixed":"dielectric-constant 값"}, temporal_scope="future"),
)
