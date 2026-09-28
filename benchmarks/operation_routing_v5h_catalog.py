# ruff: noqa: E501
"""Disjoint 0.12-H catalogs for independent capability entailment experiment #377."""

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

    certificates_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Certificate Records", "version": "1.0.0"},
        "paths": {
            "/certificates/{certificate_id}": {
                "get": {
                    "operationId": "z17",
                    "summary": "Retrieve one already-identified certificate record",
                    "responses": {"200": {"description": "certificate"}},
                },
                "patch": {
                    "operationId": "z28",
                    "summary": "Update fields on an existing certificate record",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "z39",
                    "summary": "Delete an existing certificate record permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("certificate_records_api", certificates_openapi))

    registry.register(
        tool_from_mcp(
            "reference_index_ops",
            {
                "tools": [
                    {
                        "name": "i17",
                        "description": "Search reference entries that match criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "i28",
                        "description": "Retrieve one already-identified reference entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"entry_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "i39",
                        "description": "List all available reference entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="bundle_delivery",
            description="Bundle delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a bundle to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a bundle with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="dossier_transform",
            description="Dossier transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export a dossier as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="translate",
                    description="Translate a dossier into another human language",
                    read_only=True,
                ),
                EndpointSpec(
                    name="merge",
                    description="Merge multiple dossiers into one result",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="engine_control",
            description="Engine runtime control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing engine",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered engine operation",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="voucher_requests",
            description="Voucher-request lifecycle and reimbursement",
            endpoints=[
                EndpointSpec(
                    name="create",
                    description="Create a new voucher request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active voucher request",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid voucher transaction",
                    read_only=False,
                ),
            ],
        )
    )

    humidity = FieldSpec(
        name="density",
        semantic_id="materials.density",
        description="Measured density",
        json_schema={"type": "number"},
        unit="kg/m3",
        unit_normalization=UnitNormalizationSpec(
            dimension="density",
            canonical_unit="g/cm3",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="density_probe",
            description="Density observations and forecast",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current density value",
                    read_only=True,
                    output_fields=[humidity],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical density values",
                    read_only=True,
                    output_fields=[humidity],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future density values",
                    read_only=True,
                    output_fields=[humidity],
                ),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    approvals_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Approval Records", "version": "1.0.0"},
        "paths": {
            "/approvals/{approval_id}": {
                "get": {
                    "operationId": "u17",
                    "summary": "Retrieve one already-identified approval record",
                    "responses": {"200": {"description": "approval"}},
                },
                "patch": {
                    "operationId": "u28",
                    "summary": "Update an existing approval record",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/approvals": {
                "post": {
                    "operationId": "u39",
                    "summary": "Create a brand-new approval record",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(
        tool_from_openapi("approval_records_api", approvals_openapi)
    )

    registry.register(
        tool_from_mcp(
            "specimen_index_ops",
            {
                "tools": [
                    {
                        "name": "s17",
                        "description": "Search specimen index entries that match criteria",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                    {
                        "name": "s28",
                        "description": "Retrieve one already-identified specimen index entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"entry_id": {"type": "string"}},
                        },
                    },
                    {
                        "name": "s39",
                        "description": "List all available specimen index entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="notice_dispatch",
            description="Notice delivery and shared-access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a notice to a destination",
                    read_only=False,
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a notice with another user",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="report_transform",
            description="Report transformation service",
            endpoints=[
                EndpointSpec(
                    name="export",
                    description="Export report as an external file",
                    read_only=True,
                ),
                EndpointSpec(
                    name="summarize",
                    description="Summarize report content into its main points",
                    read_only=True,
                ),
                EndpointSpec(
                    name="compare",
                    description="Compare multiple reports for differences",
                    read_only=True,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="pipeline_control",
            description="Pipeline runtime control",
            endpoints=[
                EndpointSpec(
                    name="restart",
                    description="Restart an existing pipeline runtime",
                    read_only=False,
                ),
                EndpointSpec(
                    name="execute",
                    description="Execute a registered pipeline workflow",
                    read_only=False,
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="billing_adjustments",
            description="Billing adjustment and reimbursement service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified billing adjustment",
                    read_only=True,
                ),
                EndpointSpec(
                    name="cancel",
                    description="Cancel an active billing adjustment",
                    read_only=False,
                ),
                EndpointSpec(
                    name="refund",
                    description="Refund a paid billing adjustment amount",
                    read_only=False,
                ),
            ],
        )
    )

    masa = FieldSpec(
        name="mass",
        semantic_id="physical.mass",
        description="Measured masa",
        json_schema={"type": "number"},
        unit="g",
        unit_normalization=UnitNormalizationSpec(
            dimension="mass",
            canonical_unit="kg",
            scale=0.001,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    registry.register(
        ToolSpec(
            name="mass_probe",
            description="Mass observations and forecast",
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Retrieve the current masa value",
                    read_only=True,
                    output_fields=[masa],
                ),
                EndpointSpec(
                    name="history",
                    description="Retrieve historical masa values",
                    read_only=True,
                    output_fields=[masa],
                ),
                EndpointSpec(
                    name="forecast",
                    description="Forecast future masa values",
                    read_only=True,
                    output_fields=[masa],
                ),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("certificate_records_api.z17","retrieve",{"en":"certificate L-8","ko":"인증서 L-8","es":"certificado L-8","ja":"証明書L-8","de":"zertifikat L-8","mixed":"certificate L-8"}),
    RouteCaseSpec("certificate_records_api.z28","update",{"en":"certificate L-8","ko":"인증서 L-8","es":"certificado L-8","ja":"証明書L-8","de":"zertifikat L-8","mixed":"certificate L-8"}),
    RouteCaseSpec("certificate_records_api.z39","delete",{"en":"certificate L-8","ko":"인증서 L-8","es":"certificado L-8","ja":"証明書L-8","de":"zertifikat L-8","mixed":"certificate L-8"}),
    RouteCaseSpec("reference_index_ops.i17","search",{"en":"reference entries about composite","ko":"composite 관련 참조 항목","es":"entradas de referencia sobre composite","ja":"compositeに関する参照項目","de":"referenzeinträge zu composite","mixed":"composite 관련 reference entries"}),
    RouteCaseSpec("reference_index_ops.i28","retrieve",{"en":"reference entry C-4","ko":"참조 항목 C-4","es":"entrada de referencia C-4","ja":"参照項目C-4","de":"referenzeintrag C-4","mixed":"reference entry C-4"}),
    RouteCaseSpec("reference_index_ops.i39","list",{"en":"reference entries","ko":"참조 항목","es":"entradas de referencia","ja":"参照項目","de":"referenzeinträge","mixed":"reference entries"}),
    RouteCaseSpec("bundle_delivery.send","send",{"en":"bundle PX-5","ko":"번들 PX-5","es":"paquete de datos PX-5","ja":"バンドルPX-5","de":"datenbündel PX-5","mixed":"bundle PX-5"}),
    RouteCaseSpec("bundle_delivery.share","share",{"en":"bundle PX-5","ko":"번들 PX-5","es":"paquete de datos PX-5","ja":"バンドルPX-5","de":"datenbündel PX-5","mixed":"bundle PX-5"}),
    RouteCaseSpec("dossier_transform.export","export",{"en":"dossier AF-3","ko":"도시어 AF-3","es":"expediente AF-3","ja":"ドシエAF-3","de":"dossier AF-3","mixed":"dossier AF-3"}),
    RouteCaseSpec("dossier_transform.translate","translate",{"en":"dossier AF-3","ko":"도시어 AF-3","es":"expediente AF-3","ja":"ドシエAF-3","de":"dossier AF-3","mixed":"dossier AF-3"}),
    RouteCaseSpec("dossier_transform.merge","merge",{"en":"dossiers AF-3 and AF-4","ko":"도시어 AF-3과 AF-4","es":"expedientes AF-3 y AF-4","ja":"ドシエAF-3とAF-4","de":"dossiers AF-3 und AF-4","mixed":"dossiers AF-3 AF-4"}),
    RouteCaseSpec("engine_control.restart","restart",{"en":"engine D-2","ko":"엔진 D-2","es":"engine D-2","ja":"エンジンD-2","de":"engine D-2","mixed":"engine D-2"}),
    RouteCaseSpec("engine_control.execute","execute",{"en":"engine operation D-2","ko":"엔진 작업 D-2","es":"operación de motor D-2","ja":"エンジン操作D-2","de":"motor-operation D-2","mixed":"engine operation D-2"}),
    RouteCaseSpec("voucher_requests.create","create",{"en":"voucher request","ko":"바우처 요청","es":"solicitud de vale","ja":"バウチャー申請","de":"gutschein-antrag","mixed":"voucher request"}),
    RouteCaseSpec("voucher_requests.cancel","cancel",{"en":"voucher request SC-7","ko":"바우처 요청 SC-7","es":"solicitud de vale SC-7","ja":"バウチャー申請SC-7","de":"gutschein SC-7","mixed":"voucher SC-7"}),
    RouteCaseSpec("voucher_requests.refund","refund",{"en":"voucher payment SC-7","ko":"바우처 결제 SC-7","es":"pago de vale SC-7","ja":"バウチャー支払いSC-7","de":"gutschein-zahlung SC-7","mixed":"voucher payment SC-7"}),
    RouteCaseSpec("density_probe.current","retrieve",{"en":"density","ko":"밀도","es":"densidad","ja":"密度","de":"dichte","mixed":"density"},temporal_scope="current"),
    RouteCaseSpec("density_probe.history","retrieve",{"en":"density values","ko":"밀도 값","es":"valores de densidad","ja":"密度値","de":"dichtewerte","mixed":"density values"},temporal_scope="historical"),
    RouteCaseSpec("density_probe.forecast","forecast",{"en":"density values","ko":"밀도 값","es":"valores de densidad","ja":"密度値","de":"dichtewerte","mixed":"density values"},temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("approval_records_api.u17","retrieve",{"en":"approval R-6","ko":"승인 R-6","es":"aprobación R-6","ja":"承認R-6","de":"genehmigung R-6","mixed":"approval R-6"}),
    RouteCaseSpec("approval_records_api.u28","update",{"en":"approval R-6","ko":"승인 R-6","es":"aprobación R-6","ja":"承認R-6","de":"genehmigung R-6","mixed":"approval R-6"}),
    RouteCaseSpec("approval_records_api.u39","create",{"en":"approval","ko":"승인","es":"aprobación","ja":"承認","de":"genehmigung","mixed":"approval"}),
    RouteCaseSpec("specimen_index_ops.s17","search",{"en":"specimen entries about coating","ko":"coating 관련 표본 항목","es":"elementos de espécimen sobre coating","ja":"coatingに関する標本項目","de":"specimeninträge zu coating","mixed":"coating 관련 specimen entries"}),
    RouteCaseSpec("specimen_index_ops.s28","retrieve",{"en":"specimen entry A-9","ko":"표본 항목 A-9","es":"elemento de espécimen A-9","ja":"標本項目A-9","de":"specimenintrag A-9","mixed":"specimen entry A-9"}),
    RouteCaseSpec("specimen_index_ops.s39","list",{"en":"specimen entries","ko":"표본 항목","es":"elementos de espécimen","ja":"標本項目","de":"specimeninträge","mixed":"specimen entries"}),
    RouteCaseSpec("notice_dispatch.send","send",{"en":"notice MR-2","ko":"공지 MR-2","es":"aviso MR-2","ja":"通知MR-2","de":"mitteilung MR-2","mixed":"notice MR-2"}),
    RouteCaseSpec("notice_dispatch.share","share",{"en":"notice MR-2","ko":"공지 MR-2","es":"aviso MR-2","ja":"通知MR-2","de":"mitteilung MR-2","mixed":"notice MR-2"}),
    RouteCaseSpec("report_transform.export","export",{"en":"report M-1","ko":"보고서 M-1","es":"informe M-1","ja":"レポートM-1","de":"bericht M-1","mixed":"report M-1"}),
    RouteCaseSpec("report_transform.summarize","summarize",{"en":"report M-1","ko":"보고서 M-1","es":"informe M-1","ja":"レポートM-1","de":"bericht M-1","mixed":"report M-1"}),
    RouteCaseSpec("report_transform.compare","compare",{"en":"report M-1 and M-2","ko":"보고서 M-1과 M-2","es":"informes M-1 y M-2","ja":"レポートM-1とM-2","de":"berichte M-1 und M-2","mixed":"report M-1 M-2"}),
    RouteCaseSpec("pipeline_control.restart","restart",{"en":"pipeline S-5","ko":"파이프라인 S-5","es":"pipeline S-5","ja":"パイプラインS-5","de":"pipeline S-5","mixed":"pipeline S-5"}),
    RouteCaseSpec("pipeline_control.execute","execute",{"en":"pipeline workflow S-5","ko":"파이프라인 워크플로 S-5","es":"flujo del pipeline S-5","ja":"パイプラインワークフローS-5","de":"pipeline-workflow S-5","mixed":"pipeline workflow S-5"}),
    RouteCaseSpec("billing_adjustments.retrieve","retrieve",{"en":"billing adjustment DP-4","ko":"청구 조정 DP-4","es":"ajuste de facturación DP-4","ja":"請求調整DP-4","de":"abrechnungsanpassung DP-4","mixed":"billing adjustment DP-4"}),
    RouteCaseSpec("billing_adjustments.cancel","cancel",{"en":"billing adjustment DP-4","ko":"청구 조정 DP-4","es":"ajuste de facturación DP-4","ja":"請求調整DP-4","de":"abrechnungsanpassung DP-4","mixed":"billing adjustment DP-4"}),
    RouteCaseSpec("billing_adjustments.refund","refund",{"en":"billing payment DP-4","ko":"청구 결제 DP-4","es":"pago de facturación DP-4","ja":"請求支払いDP-4","de":"abrechnungszahlung DP-4","mixed":"billing payment DP-4"}),
    RouteCaseSpec("mass_probe.current","retrieve",{"en":"mass","ko":"질량","es":"masa","ja":"質量","de":"masse","mixed":"mass"},temporal_scope="current"),
    RouteCaseSpec("mass_probe.history","retrieve",{"en":"mass values","ko":"질량 값","es":"valores de masa","ja":"質量値","de":"massenwerte","mixed":"mass values"},temporal_scope="historical"),
    RouteCaseSpec("mass_probe.forecast","forecast",{"en":"mass values","ko":"질량 값","es":"valores de masa","ja":"質量値","de":"massenwerte","mixed":"mass values"},temporal_scope="future"),
)
