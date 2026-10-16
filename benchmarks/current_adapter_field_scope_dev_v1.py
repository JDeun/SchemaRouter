"""New, independently written *development* fixture for current adapters (#1412).

Local OpenAPI and MCP documents are manually authored protocol-shaped
fixtures, NOT third-party/live provider snapshots. SQL/vector/graph are
current-schema native typed ToolSpecs; no backends are invoked.
Gold field/route/role expectations are reviewed DEV labels, not blind tests.
"""
from __future__ import annotations

from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "ja")
SOURCE_CLASS = "newly_authored_local_protocol_shaped_development_only"
PROVIDERS = ("openapi", "mcp", "database", "vector", "graph")


def _object(properties: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            name: {"type": type_name, "description": name.replace("_", " ")}
            for name, type_name in properties.items()
        },
    }


def openapi_tool() -> ToolSpec:
    response = _object({
        "invoice_id": "string", "total_amount": "number",
        "currency": "string", "status": "string",
    })
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Example invoicing source", "version": "1.0.0"},
        "paths": {
            "/invoices/{invoice_id}": {
                "get": {
                    "operationId": "getInvoice",
                    "summary": "Read invoice totals, currency and payment status",
                    "parameters": [{
                        "name": "invoice_id", "in": "path", "required": True,
                        "schema": {"type": "string"},
                    }],
                    "responses": {"200": {
                        "description": "Invoice details",
                        "content": {"application/json": {"schema": response}},
                    }},
                },
                "post": {
                    "operationId": "payInvoice",
                    "summary": "Pay the specified invoice, changing its status",
                    "responses": {"200": {
                        "description": "Updated payment",
                        "content": {"application/json": {
                            "schema": _object({"payment_id": "string", "status": "string"})
                        }},
                    }},
                },
            }
        },
    }
    return tool_from_openapi("billing", document)


def mcp_tool() -> ToolSpec:
    tools = {
        "tools": [
            {
                "name": "search_documents",
                "description": "Search scientific documents by words",
                "inputSchema": _object({"query": "string"}),
                "outputSchema": _object({"hits": "array", "count": "integer"}),
            },
            {
                "name": "tag_document",
                "description": "Modify the tags on a research document",
                "inputSchema": _object({"document_id": "string", "tag": "string"}),
                "outputSchema": _object({"document_id": "string", "tags": "array"}),
            },
        ]
    }
    return tool_from_mcp("research", tools)


def _field(name: str, description: str, type_name: str = "string") -> FieldSpec:
    return FieldSpec(
        name=name,
        semantic_id=f"research.{name}",
        description=description,
        json_schema={"type": type_name},
    )


def typed_tool(
    name: str, provider: str, endpoints: list[EndpointSpec],
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        description=f"Typed {provider} capability repository",
        endpoints=endpoints,
    )


def native_tools() -> list[ToolSpec]:
    return [
        typed_tool("orders", "database", [
            EndpointSpec(
                name="lookup", description="Read order status from SQL store",
                read_only=True,
                output_fields=[_field("order_id", "Order ID"), _field("status", "Order state")],
            ),
            EndpointSpec(
                name="setStatus", description="Write SQL order status",
                read_only=False,
                output_fields=[
                    _field("order_id", "Order ID"),
                    _field("updated", "Change confirmation"),
                ],
            ),
        ]),
        typed_tool("vectors", "vector", [
            EndpointSpec(
                name="search", description="Semantic vector search of articles",
                read_only=True,
                output_fields=[_field("distance", "Vector distance", "number"),
                               _field("title", "Document title")],
            ),
            EndpointSpec(
                name="upsert", description="Change vector document embeddings",
                read_only=False,
                output_fields=[_field("id", "Vector ID")],
            ),
        ]),
        typed_tool("graph", "graph", [
            EndpointSpec(
                name="neighbors", description="Read knowledge graph neighboring nodes",
                read_only=True,
                output_fields=[_field("nodes", "Neighbor node list", "array")],
            ),
            EndpointSpec(
                name="link", description="Create new knowledge graph connection",
                read_only=False,
                output_fields=[_field("edge_id", "New graph edge ID")],
            ),
        ]),
    ]


def registry_and_policy() -> tuple[InMemoryRegistry, AuthorizationPolicy]:
    registry = InMemoryRegistry()
    registry.update_many([openapi_tool(), mcp_tool(), *native_tools()])
    rules = (
        AuthorizationRule(
            name="editor-all-existing-contracts",
            effect="allow", operation="*", roles_any=("editor",),
        ),
        *(
            AuthorizationRule(
                name=f"viewer-{operation}", effect="allow",
                operation=operation, roles_any=("viewer",),
            )
            for operation in (
                "billing.getInvoice",
                "research.search_documents",
                "orders.lookup",
                "vectors.search",
                "graph.neighbors",
            )
        ),
    )
    return registry, AuthorizationPolicy(rules=tuple(rules))


def router_and_policy() -> tuple[SchemaRouter, AuthorizationPolicy]:
    registry, policy = registry_and_policy()
    return SchemaRouter(registry=registry, authorization_policy=policy), policy


def principal(role: str) -> PrincipalContext:
    if role not in ("viewer", "editor"):
        raise ValueError("invalid synthetic principal role")
    return PrincipalContext(subject=f"synthetic-{role}", roles=(role,))


# Manually written queries; route/field gold is an explicitly authored DEV
# contract, not inferred from the retrieved ranking or scoring output.
SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "invoice_read", "role": "viewer", "route": "billing.getInvoice",
        "fields": ("invoice_id", "total_amount"),
        "queries": {
            "en": "Read invoice total amount and invoice ID.",
            "ko": "청구서의 총금액과 청구서 번호를 조회해 주세요.",
            "ja": "請求書の合計金額と請求書番号を取得してください。",
        },
    },
    {
        "id": "document_search", "role": "viewer", "route": "research.search_documents",
        "fields": ("hits", "count"),
        "queries": {
            "en": "Search research documents and show matching count.",
            "ko": "연구 문서를 검색하고 검색 결과 수를 표시해 주세요.",
            "ja": "研究文書を検索し、検索結果件数を表示してください。",
        },
    },
    {
        "id": "order_read", "role": "viewer", "route": "orders.lookup",
        "fields": ("order_id", "status"),
        "queries": {
            "en": "Find the order ID and current order status in the SQL database.",
            "ko": "SQL 데이터베이스에서 주문 번호와 상태를 조회해 주세요.",
            "ja": "SQL データベースの注文 ID と状態を照会してください。",
        },
    },
    {
        "id": "vector_search", "role": "viewer", "route": "vectors.search",
        "fields": ("distance", "title"),
        "queries": {
            "en": "Search similar articles by vector and include title and distance.",
            "ko": "벡터 검색으로 비슷한 글의 제목과 거리를 찾으세요.",
            "ja": "ベクトル検索で近い記事の題名と距離を取得してください。",
        },
    },
    {
        "id": "graph_read", "role": "viewer", "route": "graph.neighbors",
        "fields": ("nodes",),
        "queries": {
            "en": "Find neighboring nodes in the knowledge graph.",
            "ko": "지식 그래프에서 인접한 노드를 조회해 주세요.",
            "ja": "知識グラフの隣接ノードを取得してください。",
        },
    },
    {
        "id": "invoice_pay_editor", "role": "editor", "route": "billing.payInvoice",
        "fields": ("payment_id", "status"),
        "queries": {
            "en": "Pay an outstanding invoice and return payment status.",
            "ko": "미결제 청구서를 결제하고 결제 상태를 반환해 주세요.",
            "ja": "未払い請求書を決済し、決済状態を返してください。",
        },
    },
    {
        "id": "graph_link_editor", "role": "editor", "route": "graph.link",
        "fields": ("edge_id",),
        "queries": {
            "en": "Create a link between two knowledge graph nodes.",
            "ko": "지식 그래프 노드 두 개를 연결해 주세요.",
            "ja": "知識グラフの二つのノードを接続してください。",
        },
    },
    {
        "id": "invoice_pay_forbidden", "role": "viewer", "route": None,
        "fields": (),
        "queries": {
            "en": "Pay an invoice with my read-only account.",
            "ko": "읽기 전용 계정으로 청구서를 결제해 주세요.",
            "ja": "閲覧専用アカウントで請求書を決済してください。",
        },
    },
    {
        "id": "unsupported_weather", "role": "viewer", "route": None,
        "fields": (),
        "queries": {
            "en": "Tell me tomorrow's local weather forecast.",
            "ko": "내일 이 지역의 날씨를 알려주세요.",
            "ja": "明日の天気予報を教えてください。",
        },
    },
)


def authored_tasks() -> list[dict[str, Any]]:
    rows = []
    for scenario in SCENARIOS:
        for language in LANGUAGES:
            rows.append({
                "id": f"{scenario['id']}-{language}",
                "scenario": scenario["id"],
                "language": language,
                "query": scenario["queries"][language],
                "role": scenario["role"],
                "gold_route": scenario["route"],
                "gold_fields": list(scenario["fields"]),
            })
    return rows
