"""Synthetic scaled typed-adapter DEV sources for issue #1428.

Everything here is local and author-visible. This fixture is NOT a real
provider snapshot, independent test, authenticated principal, or agent run.
"""
from __future__ import annotations

from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import (
    _object,
    mcp_tool,
    native_tools,
    openapi_tool,
)
from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

SIZES = (100, 250, 500)
WIDTHS = (24, 32, 40, 48, 56, 64)
FAMILIES = ("openapi", "mcp", "database", "vector", "graph")
DENIED_VIEWER = (
    "billing.payInvoice",
    "research.tag_document",
    "orders.setStatus",
    "vectors.upsert",
    "graph.link",
)
VIEWER_READ = (
    "billing.getInvoice",
    "research.search_documents",
    "orders.lookup",
    "vectors.search",
    "graph.neighbors",
)

# The labels below were explicitly authored for DEV; NEVER score targets
# derived from runtime retrieval. The original 27-case fixture is NOT reused.
SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "invoice-sum-v2", "role": "viewer",
        "route": "billing.getInvoice", "fields": ("invoice_id", "total_amount"),
        "queries": (
            "Inspect the billed total and invoice identifier.",
            "청구 금액의 합계와 청구서 식별자를 조회하세요.",
            "請求合計と請求書識別子を照会してください。",
        ),
    },
    {
        "id": "vector-score-v2", "role": "viewer",
        "route": "vectors.search", "fields": ("distance", "title"),
        "queries": (
            "Retrieve similar article names with distance values.",
            "유사한 자료의 제목과 벡터 거리 값을 찾으세요.",
            "近い論文のタイトルとベクトル距離を取得してください。",
        ),
    },
    {
        "id": "graph-adjacency-v2", "role": "viewer",
        "route": "graph.neighbors", "fields": ("nodes",),
        "queries": (
            "Enumerate neighboring knowledge graph nodes.",
            "지식 그래프에서 인접 노드 목록을 찾아주세요.",
            "知識グラフの隣接ノード一覧を取得してください。",
        ),
    },
    {
        "id": "payment-editor-v2", "role": "editor",
        "route": "billing.payInvoice", "fields": ("payment_id", "status"),
        "queries": (
            "Settle the invoice and verify its payment confirmation.",
            "청구서 결제를 처리한 뒤 결제 확인 결과를 확인하세요.",
            "請求書の支払いを実行し決済確認を取得してください。",
        ),
    },
    {
        "id": "api-ledger-v2", "role": "editor",
        "route": "benchapi.probeApi0003", "fields": ("payload",),
        "queries": (
            "Read synthetic API parcel ledger entry 0003 with payload.",
            "합성 API 택배 원장 0003 항목의 payload를 읽으세요.",
            "合成 API 荷物台帳 0003 の payload を取得してください。",
        ),
    },
    {
        "id": "mcp-ledger-v2", "role": "viewer",
        "route": "benchmcp.probe_mcp_0004", "fields": ("payload",),
        "queries": (
            "Look up MCP parcel ledger item 0004 payload.",
            "MCP 택배 원장 항목 0004 payload를 조회하세요.",
            "MCP 荷物台帳 0004 の payload を照会してください。",
        ),
    },
    {
        "id": "db-ledger-v2", "role": "viewer",
        "route": "benchdb.probe_db_0005", "fields": ("payload",),
        "queries": (
            "Fetch the database parcel ledger record 0005 payload.",
            "DB 택배 원장 0005 레코드의 payload를 조회해 주세요.",
            "データベース荷物台帳 0005 の payload を取得してください。",
        ),
    },
    {
        "id": "readonly-payment-v2", "role": "viewer",
        "route": None, "fields": (),
        "queries": (
            "Pay this invoice with viewer-only permission.",
            "읽기 전용 권한으로 해당 청구서를 결제하세요.",
            "閲覧のみの権限でこの請求書を支払ってください。",
        ),
    },
    {
        "id": "unsupported-flight-v2", "role": "viewer",
        "route": None, "fields": (),
        "queries": (
            "Forecast flight delays tomorrow without an aviation provider.",
            "항공 서비스 연결 없이 내일의 비행 지연을 예측하세요.",
            "航空プロバイダー無しで明日の遅延を予測してください。",
        ),
    },
)


def authored_tasks() -> list[dict[str, Any]]:
    languages = ("en", "ko", "ja")
    return [
        {
            "id": f"{scenario['id']}-{language}",
            "scenario": scenario["id"],
            "language": language,
            "query": query,
            "role": scenario["role"],
            "gold_route": scenario["route"],
            "gold_fields": list(scenario["fields"]),
        }
        for scenario in SCENARIOS
        for language, query in zip(languages, scenario["queries"], strict=True)
    ]


def _generated_tools(extra: int) -> list[ToolSpec]:
    """Generate deterministic near-neighbor route contracts in all 5 families."""
    paths: dict[str, Any] = {}
    mcp_entries: list[dict[str, Any]] = []
    native: dict[str, list[EndpointSpec]] = {
        "database": [], "vector": [], "graph": [],
    }
    for n in range(extra):
        family = FAMILIES[n % len(FAMILIES)]
        index = n // len(FAMILIES)
        stem = f"parcel ledger synthetic {family} record {index:04d}"
        response = _object({"payload": "string", "audit_tag": "string"})
        if family == "openapi":
            paths[f"/bench/parcel/{index:04d}"] = {
                "get": {
                    "operationId": f"probeApi{index:04d}",
                    "summary": f"Read API {stem}",
                    "responses": {
                        "200": {
                            "description": "Synthetic local response only",
                            "content": {"application/json": {"schema": response}},
                        }
                    },
                }
            }
        elif family == "mcp":
            mcp_entries.append({
                "name": f"probe_mcp_{index:04d}",
                "description": f"Read MCP {stem}",
                "inputSchema": _object({"record": "string"}),
                "outputSchema": response,
            })
        else:
            native[family].append(EndpointSpec(
                name=f"probe_{'db' if family == 'database' else family}_{index:04d}",
                description=f"Read {stem}",
                read_only=True,
                output_fields=[
                    FieldSpec(name="payload", description="Synthetic parcel data",
                              json_schema={"type": "string"}),
                    FieldSpec(name="audit_tag", description="Internal audit marker",
                              json_schema={"type": "string"}),
                ],
            ))
    result: list[ToolSpec] = []
    if paths:
        document = {
            "openapi": "3.1.0",
            "info": {"title": "Local synthetic scale fixture", "version": "1.0"},
            "paths": paths,
        }
        result.append(tool_from_openapi("benchapi", document))
    if mcp_entries:
        result.append(tool_from_mcp("benchmcp", {"tools": mcp_entries}))
    for provider, tool_name in (
        ("database", "benchdb"),
        ("vector", "benchvector"),
        ("graph", "benchgraph"),
    ):
        if native[provider]:
            result.append(ToolSpec(
                name=tool_name, provider=provider,
                description=f"Synthetic typed {provider} parcel ledger",
                endpoints=native[provider],
            ))
    return result


def build_fixture(size: int) -> tuple[SchemaRouter, AuthorizationPolicy]:
    if type(size) is not int or size not in SIZES:
        raise ValueError("unregistered scaled DEV catalog size")
    registry = InMemoryRegistry()
    registry.update_many([
        openapi_tool(), mcp_tool(), *native_tools(),
        *_generated_tools(size - 10),
    ])
    existing = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools() for endpoint in tool.endpoints
    }
    if len(existing) != size:
        raise ValueError("scaled fixture did not register exact unique endpoints")
    rules = tuple(
        AuthorizationRule(
            name=f"viewer-deny-{index}", effect="deny",
            operation=route, roles_any=("viewer",),
        )
        for index, route in enumerate(DENIED_VIEWER)
    ) + tuple(
        AuthorizationRule(
            name=f"viewer-existing-read-{index}", effect="allow",
            operation=route, roles_any=("viewer",),
        )
        for index, route in enumerate(VIEWER_READ)
    ) + (
        AuthorizationRule(
            name="viewer-bench-read", effect="allow",
            operation="bench*.*", roles_any=("viewer",),
        ),
        AuthorizationRule(
            name="editor-allow-local-dev", effect="allow",
            operation="*", roles_any=("editor",),
        ),
    )
    policy = AuthorizationPolicy(
        rules=rules, default_effect="deny",
        data_rules=(
            DataScopeRule(
                name="viewer-hide-local-audit", operation="bench*.*",
                roles_any=("viewer",), hidden_fields=("audit_tag",),
            ),
        ),
    )
    return SchemaRouter(registry=registry, authorization_policy=policy), policy
