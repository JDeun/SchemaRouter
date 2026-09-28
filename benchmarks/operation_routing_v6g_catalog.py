# ruff: noqa: E501
"""Identity-disjoint V6G catalogs for conformal E5 membership experiment #412."""

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


def _admin_api(
    *,
    name: str,
    title: str,
    resource: str,
    path_name: str,
    ids: tuple[str, str, str],
) -> ToolSpec:
    get_id, patch_id, delete_id = ids
    return tool_from_openapi(
        name,
        {
            "openapi": "3.1.0",
            "info": {
                "title": title,
                "version": "1.0.0",
                "description": f"{resource.title()} administration service",
            },
            "paths": {
                f"/{path_name}/{{record_id}}": {
                    "get": {
                        "operationId": get_id,
                        "summary": f"Retrieve one already-identified {resource}",
                        "responses": {"200": {"description": resource}},
                    },
                    "patch": {
                        "operationId": patch_id,
                        "summary": f"Update fields on an existing {resource}",
                        "responses": {"200": {"description": "updated"}},
                    },
                    "delete": {
                        "operationId": delete_id,
                        "summary": f"Delete an existing {resource} permanently",
                        "responses": {"204": {"description": "deleted"}},
                    },
                }
            },
        },
    )


def _index_tool(
    *,
    name: str,
    resource: str,
    ids: tuple[str, str, str],
) -> ToolSpec:
    search_id, retrieve_id, list_id = ids
    return tool_from_mcp(
        name,
        {
            "tools": [
                {
                    "name": search_id,
                    "description": f"Search {resource} records matching filters or keywords",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
                {
                    "name": retrieve_id,
                    "description": f"Retrieve one already-identified {resource} record",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"record_id": {"type": "string"}},
                    },
                },
                {
                    "name": list_id,
                    "description": f"List all available {resource} records",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ]
        },
    )


def _transfer_tool(name: str, resource: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{resource.title()} delivery and delegated-access service",
        endpoints=[
            EndpointSpec(
                name="send",
                description=f"Send a {resource} to a destination",
                read_only=False,
            ),
            EndpointSpec(
                name="share",
                description=f"Share access to a {resource} with another user",
                read_only=False,
            ),
        ],
    )


def _transform_tool(
    name: str,
    resource: str,
    middle_leaf: str,
    last_leaf: str,
) -> ToolSpec:
    descriptions = {
        "export": f"Export {resource} content as an external file",
        "summarize": f"Summarize {resource} content into its main points",
        "translate": f"Translate {resource} content into another human language",
        "compare": f"Compare multiple {resource} items for similarities or differences",
        "merge": f"Merge multiple {resource} items into one result",
    }
    return ToolSpec(
        name=name,
        description=f"{resource.title()} transformation service",
        endpoints=[
            EndpointSpec(
                name="export",
                description=descriptions["export"],
                read_only=True,
            ),
            EndpointSpec(
                name=middle_leaf,
                description=descriptions[middle_leaf],
                read_only=True,
            ),
            EndpointSpec(
                name=last_leaf,
                description=descriptions[last_leaf],
                read_only=(last_leaf != "merge"),
            ),
        ],
    )


def _control_tool(name: str, resource: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{resource.title()} runtime control service",
        endpoints=[
            EndpointSpec(
                name="restart",
                description=f"Restart an existing {resource} runtime",
                read_only=False,
            ),
            EndpointSpec(
                name="execute",
                description=f"Execute a registered {resource} operation",
                read_only=False,
            ),
        ],
    )


def _lifecycle_tool(
    name: str,
    resource: str,
    first_leaf: str,
) -> ToolSpec:
    first_description = (
        f"Create a new {resource}"
        if first_leaf == "create"
        else f"Retrieve one already-identified {resource}"
    )
    return ToolSpec(
        name=name,
        description=f"{resource.title()} lifecycle and payment service",
        endpoints=[
            EndpointSpec(
                name=first_leaf,
                description=first_description,
                read_only=(first_leaf == "retrieve"),
            ),
            EndpointSpec(
                name="cancel",
                description=f"Cancel an active {resource}",
                read_only=False,
            ),
            EndpointSpec(
                name="refund",
                description=f"Refund money for a completed {resource} payment",
                read_only=False,
            ),
        ],
    )


def _property_tool(
    *,
    name: str,
    label: str,
    semantic_id: str,
    dimension: str,
    unit: str,
    canonical_unit: str,
    scale: float,
) -> ToolSpec:
    field = FieldSpec(
        name=name,
        semantic_id=semantic_id,
        description=f"{label} measurement",
        json_schema={"type": "number"},
        unit=unit,
        unit_normalization=UnitNormalizationSpec(
            dimension=dimension,
            canonical_unit=canonical_unit,
            scale=scale,
            offset=0.0,
        ),
        qualifiers={"statistic": "instantaneous"},
    )
    return ToolSpec(
        name=name,
        description=f"{label} observations and forecast service",
        endpoints=[
            EndpointSpec(
                name="current",
                description=f"Retrieve the current {label} value",
                read_only=True,
                output_fields=[field],
            ),
            EndpointSpec(
                name="history",
                description=f"Retrieve historical {label} values",
                read_only=True,
                output_fields=[field],
            ),
            EndpointSpec(
                name="forecast",
                description=f"Forecast future {label} values",
                read_only=True,
                output_fields=[field],
            ),
        ],
    )


def calibration_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        _admin_api(
            name="leases_api",
            title="Lease Service",
            resource="lease record",
            path_name="leases",
            ids=("r14", "r25", "r36"),
        )
    )
    registry.register(
        _index_tool(
            name="polymer_index",
            resource="polymer reference",
            ids=("s14", "s25", "s36"),
        )
    )
    registry.register(_transfer_tool("consignments", "consignment"))
    registry.register(_transform_tool("reports", "report", "summarize", "merge"))
    registry.register(_control_tool("robots", "robot"))
    registry.register(_lifecycle_tool("credits", "credit request", "create"))
    registry.register(
        _property_tool(
            name="refractive_index",
            label="refractive index",
            semantic_id="material.refractive_index",
            dimension="refractive_index",
            unit="1",
            canonical_unit="1",
            scale=1.0,
        )
    )
    return registry


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        _admin_api(
            name="approvals_api",
            title="Approval Service",
            resource="approval record",
            path_name="approvals",
            ids=("t14", "t25", "t36"),
        )
    )
    registry.register(
        _index_tool(
            name="alloy_index",
            resource="alloy reference",
            ids=("u14", "u25", "u36"),
        )
    )
    registry.register(_transfer_tool("deliveries", "delivery package"))
    registry.register(_transform_tool("minutes", "meeting minutes", "summarize", "merge"))
    registry.register(_control_tool("furnaces", "furnace"))
    registry.register(_lifecycle_tool("vouchers", "voucher", "create"))
    registry.register(
        _property_tool(
            name="dielectric_constant",
            label="dielectric constant",
            semantic_id="material.dielectric_constant",
            dimension="relative_permittivity",
            unit="1",
            canonical_unit="1",
            scale=1.0,
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        _admin_api(
            name="authorities_api",
            title="Authority Service",
            resource="authority record",
            path_name="authorities",
            ids=("v14", "v25", "v36"),
        )
    )
    registry.register(
        _index_tool(
            name="phase_index",
            resource="phase reference",
            ids=("w14", "w25", "w36"),
        )
    )
    registry.register(_transfer_tool("manifests", "manifest packet"))
    registry.register(_transform_tool("abstracts", "abstract", "translate", "compare"))
    registry.register(_control_tool("chambers", "chamber"))
    registry.register(_lifecycle_tool("policies", "policy", "retrieve"))
    registry.register(
        _property_tool(
            name="poisson_ratio",
            label="Poisson ratio",
            semantic_id="material.poisson_ratio",
            dimension="poisson_ratio",
            unit="1",
            canonical_unit="1",
            scale=1.0,
        )
    )
    return registry


CALIBRATION_ROUTE_SPECS = (
    RouteCaseSpec("leases_api.r14", "retrieve", {"en":"lease record LS-4","ko":"임대 기록 LS-4","es":"registro de arrendamiento LS-4","ja":"賃貸記録LS-4","de":"leasingdatensatz LS-4","mixed":"lease 기록 LS-4"}),
    RouteCaseSpec("leases_api.r25", "update", {"en":"lease record LS-4","ko":"임대 기록 LS-4","es":"registro de arrendamiento LS-4","ja":"賃貸記録LS-4","de":"leasingdatensatz LS-4","mixed":"lease 기록 LS-4"}),
    RouteCaseSpec("leases_api.r36", "delete", {"en":"lease record LS-4","ko":"임대 기록 LS-4","es":"registro de arrendamiento LS-4","ja":"賃貸記録LS-4","de":"leasingdatensatz LS-4","mixed":"lease 기록 LS-4"}),
    RouteCaseSpec("polymer_index.s14", "search", {"en":"polymer references about PEEK","ko":"PEEK 관련 고분자 참고 기록","es":"referencias de polímeros sobre PEEK","ja":"PEEKに関する高分子参照記録","de":"polymerreferenzen zu PEEK","mixed":"PEEK 관련 polymer references"}),
    RouteCaseSpec("polymer_index.s25", "retrieve", {"en":"polymer reference PR-8","ko":"고분자 참고 기록 PR-8","es":"referencia de polímero PR-8","ja":"高分子参照記録PR-8","de":"polymerreferenz PR-8","mixed":"polymer reference PR-8"}),
    RouteCaseSpec("polymer_index.s36", "list", {"en":"polymer references","ko":"고분자 참고 기록","es":"referencias de polímeros","ja":"高分子参照記録","de":"polymerreferenzen","mixed":"polymer references"}),
    RouteCaseSpec("consignments.send", "send", {"en":"consignment CG-5","ko":"위탁 화물 CG-5","es":"envío consignado CG-5","ja":"委託荷物CG-5","de":"konsignationssendung CG-5","mixed":"consignment CG-5"}),
    RouteCaseSpec("consignments.share", "share", {"en":"consignment CG-5","ko":"위탁 화물 CG-5","es":"envío consignado CG-5","ja":"委託荷物CG-5","de":"konsignationssendung CG-5","mixed":"consignment CG-5"}),
    RouteCaseSpec("reports.export", "export", {"en":"report RP-6","ko":"보고서 RP-6","es":"informe RP-6","ja":"報告書RP-6","de":"bericht RP-6","mixed":"report RP-6"}),
    RouteCaseSpec("reports.summarize", "summarize", {"en":"report RP-6","ko":"보고서 RP-6","es":"informe RP-6","ja":"報告書RP-6","de":"bericht RP-6","mixed":"report RP-6"}),
    RouteCaseSpec("reports.merge", "merge", {"en":"reports RP-6 and RP-7","ko":"보고서 RP-6과 RP-7","es":"informes RP-6 y RP-7","ja":"報告書RP-6とRP-7","de":"berichte RP-6 und RP-7","mixed":"reports RP-6 RP-7"}),
    RouteCaseSpec("robots.restart", "restart", {"en":"robot RB-4","ko":"로봇 RB-4","es":"robot RB-4","ja":"ロボットRB-4","de":"roboter RB-4","mixed":"robot RB-4"}),
    RouteCaseSpec("robots.execute", "execute", {"en":"robot operation RB-4","ko":"로봇 작업 RB-4","es":"operación del robot RB-4","ja":"ロボット操作RB-4","de":"roboteroperation RB-4","mixed":"robot operation RB-4"}),
    RouteCaseSpec("credits.create", "create", {"en":"credit request","ko":"크레딧 요청","es":"solicitud de crédito","ja":"クレジット申請","de":"gutschriftsantrag","mixed":"credit request"}),
    RouteCaseSpec("credits.cancel", "cancel", {"en":"credit request CR-5","ko":"크레딧 요청 CR-5","es":"solicitud de crédito CR-5","ja":"クレジット申請CR-5","de":"gutschriftsantrag CR-5","mixed":"credit request CR-5"}),
    RouteCaseSpec("credits.refund", "refund", {"en":"credit payment CR-5","ko":"크레딧 결제 CR-5","es":"pago de crédito CR-5","ja":"クレジット支払いCR-5","de":"gutschriftszahlung CR-5","mixed":"credit payment CR-5"}),
    RouteCaseSpec("refractive_index.current", "retrieve", {"en":"refractive index value","ko":"굴절률 값","es":"valor del índice de refracción","ja":"屈折率","de":"brechungsindex","mixed":"refractive index 값"}, temporal_scope="current"),
    RouteCaseSpec("refractive_index.history", "retrieve", {"en":"refractive index values","ko":"굴절률 값","es":"valores del índice de refracción","ja":"屈折率","de":"brechungsindizes","mixed":"refractive index 값"}, temporal_scope="historical"),
    RouteCaseSpec("refractive_index.forecast", "forecast", {"en":"refractive index values","ko":"굴절률 값","es":"valores del índice de refracción","ja":"屈折率","de":"brechungsindizes","mixed":"refractive index 값"}, temporal_scope="future"),
)

DEV_ROUTE_SPECS = (
    RouteCaseSpec("approvals_api.t14", "retrieve", {"en":"approval record AP-4","ko":"승인 기록 AP-4","es":"registro de aprobación AP-4","ja":"承認記録AP-4","de":"genehmigungsdatensatz AP-4","mixed":"approval 기록 AP-4"}),
    RouteCaseSpec("approvals_api.t25", "update", {"en":"approval record AP-4","ko":"승인 기록 AP-4","es":"registro de aprobación AP-4","ja":"承認記録AP-4","de":"genehmigungsdatensatz AP-4","mixed":"approval 기록 AP-4"}),
    RouteCaseSpec("approvals_api.t36", "delete", {"en":"approval record AP-4","ko":"승인 기록 AP-4","es":"registro de aprobación AP-4","ja":"承認記録AP-4","de":"genehmigungsdatensatz AP-4","mixed":"approval 기록 AP-4"}),
    RouteCaseSpec("alloy_index.u14", "search", {"en":"alloy references about Inconel","ko":"Inconel 관련 합금 참고 기록","es":"referencias de aleaciones sobre Inconel","ja":"Inconelに関する合金参照記録","de":"legierungsreferenzen zu Inconel","mixed":"Inconel 관련 alloy references"}),
    RouteCaseSpec("alloy_index.u25", "retrieve", {"en":"alloy reference AR-8","ko":"합금 참고 기록 AR-8","es":"referencia de aleación AR-8","ja":"合金参照記録AR-8","de":"legierungsreferenz AR-8","mixed":"alloy reference AR-8"}),
    RouteCaseSpec("alloy_index.u36", "list", {"en":"alloy references","ko":"합금 참고 기록","es":"referencias de aleaciones","ja":"合金参照記録","de":"legierungsreferenzen","mixed":"alloy references"}),
    RouteCaseSpec("deliveries.send", "send", {"en":"delivery package DL-5","ko":"배송 패키지 DL-5","es":"paquete de entrega DL-5","ja":"配送パッケージDL-5","de":"lieferpaket DL-5","mixed":"delivery package DL-5"}),
    RouteCaseSpec("deliveries.share", "share", {"en":"delivery package DL-5","ko":"배송 패키지 DL-5","es":"paquete de entrega DL-5","ja":"配送パッケージDL-5","de":"lieferpaket DL-5","mixed":"delivery package DL-5"}),
    RouteCaseSpec("minutes.export", "export", {"en":"meeting minutes MN-6","ko":"회의록 MN-6","es":"acta de reunión MN-6","ja":"議事録MN-6","de":"sitzungsprotokoll MN-6","mixed":"meeting minutes MN-6"}),
    RouteCaseSpec("minutes.summarize", "summarize", {"en":"meeting minutes MN-6","ko":"회의록 MN-6","es":"acta de reunión MN-6","ja":"議事録MN-6","de":"sitzungsprotokoll MN-6","mixed":"meeting minutes MN-6"}),
    RouteCaseSpec("minutes.merge", "merge", {"en":"meeting minutes MN-6 and MN-7","ko":"회의록 MN-6과 MN-7","es":"actas MN-6 y MN-7","ja":"議事録MN-6とMN-7","de":"sitzungsprotokolle MN-6 und MN-7","mixed":"meeting minutes MN-6 MN-7"}),
    RouteCaseSpec("furnaces.restart", "restart", {"en":"furnace FN-4","ko":"가열로 FN-4","es":"horno FN-4","ja":"炉FN-4","de":"ofen FN-4","mixed":"furnace FN-4"}),
    RouteCaseSpec("furnaces.execute", "execute", {"en":"furnace operation FN-4","ko":"가열로 작업 FN-4","es":"operación del horno FN-4","ja":"炉操作FN-4","de":"ofenoperation FN-4","mixed":"furnace operation FN-4"}),
    RouteCaseSpec("vouchers.create", "create", {"en":"voucher","ko":"바우처","es":"vale","ja":"バウチャー","de":"gutschein","mixed":"voucher"}),
    RouteCaseSpec("vouchers.cancel", "cancel", {"en":"voucher VC-5","ko":"바우처 VC-5","es":"vale VC-5","ja":"バウチャーVC-5","de":"gutschein VC-5","mixed":"voucher VC-5"}),
    RouteCaseSpec("vouchers.refund", "refund", {"en":"voucher payment VC-5","ko":"바우처 결제 VC-5","es":"pago de vale VC-5","ja":"バウチャー支払いVC-5","de":"gutscheinzahlung VC-5","mixed":"voucher payment VC-5"}),
    RouteCaseSpec("dielectric_constant.current", "retrieve", {"en":"dielectric constant value","ko":"유전율 값","es":"valor de constante dieléctrica","ja":"誘電率","de":"dielektrizitätskonstante","mixed":"dielectric constant 값"}, temporal_scope="current"),
    RouteCaseSpec("dielectric_constant.history", "retrieve", {"en":"dielectric constant values","ko":"유전율 값","es":"valores de constante dieléctrica","ja":"誘電率","de":"dielektrizitätskonstanten","mixed":"dielectric constant 값"}, temporal_scope="historical"),
    RouteCaseSpec("dielectric_constant.forecast", "forecast", {"en":"dielectric constant values","ko":"유전율 값","es":"valores de constante dieléctrica","ja":"誘電率","de":"dielektrizitätskonstanten","mixed":"dielectric constant 값"}, temporal_scope="future"),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("authorities_api.v14", "retrieve", {"en":"authority record AU-4","ko":"권한 기록 AU-4","es":"registro de autoridad AU-4","ja":"権限記録AU-4","de":"berechtigungsdatensatz AU-4","mixed":"authority 기록 AU-4"}),
    RouteCaseSpec("authorities_api.v25", "update", {"en":"authority record AU-4","ko":"권한 기록 AU-4","es":"registro de autoridad AU-4","ja":"権限記録AU-4","de":"berechtigungsdatensatz AU-4","mixed":"authority 기록 AU-4"}),
    RouteCaseSpec("authorities_api.v36", "delete", {"en":"authority record AU-4","ko":"권한 기록 AU-4","es":"registro de autoridad AU-4","ja":"権限記録AU-4","de":"berechtigungsdatensatz AU-4","mixed":"authority 기록 AU-4"}),
    RouteCaseSpec("phase_index.w14", "search", {"en":"phase references about spinel","ko":"spinel 관련 상 참고 기록","es":"referencias de fases sobre spinel","ja":"spinelに関する相参照記録","de":"phasenreferenzen zu spinel","mixed":"spinel 관련 phase references"}),
    RouteCaseSpec("phase_index.w25", "retrieve", {"en":"phase reference PH-8","ko":"상 참고 기록 PH-8","es":"referencia de fase PH-8","ja":"相参照記録PH-8","de":"phasenreferenz PH-8","mixed":"phase reference PH-8"}),
    RouteCaseSpec("phase_index.w36", "list", {"en":"phase references","ko":"상 참고 기록","es":"referencias de fases","ja":"相参照記録","de":"phasenreferenzen","mixed":"phase references"}),
    RouteCaseSpec("manifests.send", "send", {"en":"manifest packet MF-5","ko":"적하 목록 패킷 MF-5","es":"paquete de manifiesto MF-5","ja":"マニフェストパケットMF-5","de":"manifestpaket MF-5","mixed":"manifest packet MF-5"}),
    RouteCaseSpec("manifests.share", "share", {"en":"manifest packet MF-5","ko":"적하 목록 패킷 MF-5","es":"paquete de manifiesto MF-5","ja":"マニフェストパケットMF-5","de":"manifestpaket MF-5","mixed":"manifest packet MF-5"}),
    RouteCaseSpec("abstracts.export", "export", {"en":"abstract AB-6","ko":"초록 AB-6","es":"resumen AB-6","ja":"抄録AB-6","de":"abstract AB-6","mixed":"abstract AB-6"}),
    RouteCaseSpec("abstracts.translate", "translate", {"en":"abstract AB-6","ko":"초록 AB-6","es":"resumen AB-6","ja":"抄録AB-6","de":"abstract AB-6","mixed":"abstract AB-6"}),
    RouteCaseSpec("abstracts.compare", "compare", {"en":"abstracts AB-6 and AB-7","ko":"초록 AB-6과 AB-7","es":"resúmenes AB-6 y AB-7","ja":"抄録AB-6とAB-7","de":"abstracts AB-6 und AB-7","mixed":"abstracts AB-6 AB-7"}),
    RouteCaseSpec("chambers.restart", "restart", {"en":"chamber CH-4","ko":"챔버 CH-4","es":"cámara CH-4","ja":"チャンバーCH-4","de":"kammer CH-4","mixed":"chamber CH-4"}),
    RouteCaseSpec("chambers.execute", "execute", {"en":"chamber operation CH-4","ko":"챔버 작업 CH-4","es":"operación de cámara CH-4","ja":"チャンバー操作CH-4","de":"kammeroperation CH-4","mixed":"chamber operation CH-4"}),
    RouteCaseSpec("policies.retrieve", "retrieve", {"en":"policy PL-5","ko":"정책 PL-5","es":"póliza PL-5","ja":"ポリシーPL-5","de":"police PL-5","mixed":"policy PL-5"}),
    RouteCaseSpec("policies.cancel", "cancel", {"en":"policy PL-5","ko":"정책 PL-5","es":"póliza PL-5","ja":"ポリシーPL-5","de":"police PL-5","mixed":"policy PL-5"}),
    RouteCaseSpec("policies.refund", "refund", {"en":"policy payment PL-5","ko":"정책 결제 PL-5","es":"pago de póliza PL-5","ja":"ポリシー支払いPL-5","de":"policenzahlung PL-5","mixed":"policy payment PL-5"}),
    RouteCaseSpec("poisson_ratio.current", "retrieve", {"en":"Poisson ratio value","ko":"푸아송비 값","es":"valor de razón de Poisson","ja":"ポアソン比","de":"poissonzahl","mixed":"Poisson ratio 값"}, temporal_scope="current"),
    RouteCaseSpec("poisson_ratio.history", "retrieve", {"en":"Poisson ratio values","ko":"푸아송비 값","es":"valores de razón de Poisson","ja":"ポアソン比","de":"poissonzahlen","mixed":"Poisson ratio 값"}, temporal_scope="historical"),
    RouteCaseSpec("poisson_ratio.forecast", "forecast", {"en":"Poisson ratio values","ko":"푸아송비 값","es":"valores de razón de Poisson","ja":"ポアソン比","de":"poissonzahlen","mixed":"Poisson ratio 값"}, temporal_scope="future"),
)
